from __future__ import annotations

from typing import Literal
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from datapilot.agents import (
    AnalystAgent,
    PlannerAgent,
    ReporterAgent,
    ReviewerAgent,
    SchemaAgent,
    SqlAgent,
)
from datapilot.catalog import DatasetCatalog
from datapilot.config import settings
from datapilot.datasources import DataSourceFactory
from datapilot.models import (
    AgentState,
    AnalysisPlan,
    ReviewResult,
    SchemaProfile,
    SqlQueryPlan,
    new_state,
)
from datapilot.storage import JsonRunStore
from datapilot.tracing import trace_node


class DataPilotWorkflow:
    def __init__(
        self,
        catalog: DatasetCatalog | None = None,
        store: JsonRunStore | None = None,
    ):
        self.catalog = catalog or DatasetCatalog(settings.catalog_path)
        self.sources = DataSourceFactory(self.catalog.path.parent)
        self.store = store or JsonRunStore(settings.run_dir)
        self.planner = PlannerAgent()
        self.schema_agent = SchemaAgent()
        self.sql_agent = SqlAgent()
        self.analyst = AnalystAgent()
        self.reviewer = ReviewerAgent()
        self.reporter = ReporterAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("plan", self._plan)
        builder.add_node("approval_gate", self._approval_gate)
        builder.add_node("inspect_schema", self._inspect_schema)
        builder.add_node("plan_sql", self._plan_sql)
        builder.add_node("execute_sql", self._execute_sql)
        builder.add_node("analyze", self._analyze)
        builder.add_node("review", self._review)
        builder.add_node("report", self._report)
        builder.add_node("persist", self._persist)

        builder.add_edge(START, "plan")
        builder.add_conditional_edges(
            "plan",
            self._approval_route,
            {"approval": "approval_gate", "schema": "inspect_schema"},
        )
        builder.add_conditional_edges(
            "approval_gate",
            self._gate_route,
            {"schema": "inspect_schema", "persist": "persist"},
        )
        builder.add_edge("inspect_schema", "plan_sql")
        builder.add_edge("plan_sql", "execute_sql")
        builder.add_edge("execute_sql", "analyze")
        builder.add_edge("analyze", "review")
        builder.add_edge("review", "report")
        builder.add_edge("report", "persist")
        builder.add_edge("persist", END)
        return builder.compile()

    def run(self, dataset_id: str, question: str, approved: bool = False) -> AgentState:
        self.catalog.get(dataset_id)
        state = new_state(uuid4().hex, dataset_id, question, approved)
        return self.graph.invoke(state)

    def approve(self, run_id: str) -> AgentState:
        state = self.store.load(run_id)
        if state.get("status") != "awaiting_approval":
            raise ValueError("Only an awaiting_approval run can be approved")
        state["approved"] = True
        state["status"] = "approved"
        return self.graph.invoke(state)

    def _source(self, state: AgentState):
        return self.sources.create(self.catalog.get(state["dataset_id"]))

    def _plan(self, state: AgentState) -> dict:
        with trace_node(state, "planner"):
            plan = self.planner.run(state["question"])
        return {"plan": plan.model_dump(), "trace": state["trace"], "status": "planned"}

    @staticmethod
    def _approval_route(state: AgentState) -> Literal["approval", "schema"]:
        return "approval" if state["plan"]["requires_approval"] else "schema"

    def _approval_gate(self, state: AgentState) -> dict:
        with trace_node(state, "approval_gate") as event:
            event["approved"] = state.get("approved", False)
            event["risk_reasons"] = state["plan"].get("risk_reasons", [])
            status = "approved" if state.get("approved") else "awaiting_approval"
        return {"status": status, "trace": state["trace"]}

    @staticmethod
    def _gate_route(state: AgentState) -> Literal["schema", "persist"]:
        return "schema" if state.get("approved") else "persist"

    def _inspect_schema(self, state: AgentState) -> dict:
        with trace_node(state, "schema_agent"):
            profile = self.schema_agent.run(self._source(state))
        return {
            "schema_profile": profile.model_dump(),
            "trace": state["trace"],
            "status": "schema_ready",
        }

    def _plan_sql(self, state: AgentState) -> dict:
        with trace_node(state, "sql_agent"):
            plan = self.sql_agent.run(
                SchemaProfile.model_validate(state["schema_profile"]),
                AnalysisPlan.model_validate(state["plan"]),
            )
        return {
            "sql_plan": plan.model_dump(),
            "trace": state["trace"],
            "status": "sql_planned",
        }

    def _execute_sql(self, state: AgentState) -> dict:
        source = self._source(state)
        results = []
        with trace_node(state, "sql_runtime") as event:
            for query in SqlQueryPlan.model_validate(state["sql_plan"]).queries:
                try:
                    output = source.execute(query.sql)
                    results.append(
                        {
                            "query_id": query.query_id,
                            "purpose": query.purpose,
                            "sql": query.sql,
                            "status": "ok",
                            **output,
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "query_id": query.query_id,
                            "purpose": query.purpose,
                            "sql": query.sql,
                            "status": "rejected" if isinstance(exc, ValueError) else "error",
                            "error": f"{type(exc).__name__}: {exc}",
                            "columns": [],
                            "rows": [],
                            "row_count": 0,
                            "truncated": False,
                        }
                    )
            event["query_count"] = len(results)
            event["failed_queries"] = sum(result["status"] != "ok" for result in results)
        return {
            "query_results": results,
            "trace": state["trace"],
            "status": "sql_executed",
        }

    def _analyze(self, state: AgentState) -> dict:
        with trace_node(state, "analyst"):
            analysis = self.analyst.run(
                SchemaProfile.model_validate(state["schema_profile"]),
                AnalysisPlan.model_validate(state["plan"]),
                state["query_results"],
            )
        return {"analysis": analysis, "trace": state["trace"], "status": "analyzed"}

    def _review(self, state: AgentState) -> dict:
        with trace_node(state, "reviewer"):
            review = self.reviewer.run(
                state["analysis"],
                SchemaProfile.model_validate(state["schema_profile"]),
                state["query_results"],
            )
        return {
            "review": review.model_dump(),
            "trace": state["trace"],
            "status": "reviewed",
        }

    def _report(self, state: AgentState) -> dict:
        with trace_node(state, "reporter"):
            report = self.reporter.run(
                AnalysisPlan.model_validate(state["plan"]),
                SchemaProfile.model_validate(state["schema_profile"]),
                state["analysis"],
                state["query_results"],
                ReviewResult.model_validate(state["review"]),
            )
        return {
            "report": report,
            "trace": state["trace"],
            "status": "completed" if state["review"]["passed"] else "quality_gate_failed",
        }

    def _persist(self, state: AgentState) -> dict:
        with trace_node(state, "persistence"):
            if state.get("report"):
                self.store.save_report(state["run_id"], state["report"])
                state["artifacts"]["report"] = f"/v1/runs/{state['run_id']}/artifacts/report"
        self.store.save(state)
        return {"trace": state["trace"], "artifacts": state["artifacts"]}
