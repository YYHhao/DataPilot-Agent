from datapilot.agents.planner import PlannerAgent
from datapilot.agents.sql_agent import SqlAgent
from datapilot.models import (
    AnalysisPlan,
    AnalysisType,
    ColumnSchema,
    RiskLevel,
    SchemaProfile,
    SqlQuery,
    SqlQueryPlan,
    TableSchema,
)


class StubModel:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.response


def test_planner_uses_llm_and_enforces_independent_risk_policy():
    response = AnalysisPlan(
        objective="summarize",
        analysis_type=AnalysisType.OVERVIEW,
        steps=["query"],
    )
    model = StubModel(response)
    plan = PlannerAgent(model).run("Delete source data and generate a summary")
    assert model.prompts
    assert plan.requires_approval
    assert plan.risk_level == RiskLevel.HIGH
    assert plan.risk_reasons


def test_sql_agent_uses_structured_llm_output():
    expected = SqlQueryPlan(
        dialect="sqlite",
        queries=[
            SqlQuery(
                query_id="Q1",
                purpose="rank regions",
                sql='SELECT region, SUM(revenue) FROM "orders" GROUP BY region',
            )
        ],
    )
    model = StubModel(expected)
    profile = SchemaProfile(
        dataset_id="sales",
        dataset_name="Sales",
        description="",
        driver="sqlite",
        tables=[
            TableSchema(
                name="orders",
                columns=[
                    ColumnSchema(name="region", data_type="TEXT"),
                    ColumnSchema(name="revenue", data_type="REAL"),
                ],
            )
        ],
    )
    plan = AnalysisPlan(
        objective="Rank regions by revenue",
        analysis_type=AnalysisType.RANKING,
        steps=["rank"],
    )
    result = SqlAgent(model).run(profile, plan)
    assert result == expected
    assert "orders" in model.prompts[0]
