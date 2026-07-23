from datapilot.agents.planner import PlannerAgent
from datapilot.agents.sql_agent import SqlAgent
from datapilot.models import (
    AnalysisPlan,
    AnalysisType,
    ColumnSchema,
    SchemaProfile,
    TableSchema,
)


def test_planner_routes_high_risk_request_to_approval():
    plan = PlannerAgent().run("Delete source data and generate a summary")
    assert plan.requires_approval
    assert plan.risk_level == "high"
    assert plan.risk_reasons


def test_planner_classifies_trend_request():
    plan = PlannerAgent().run("分析每月销售趋势")
    assert plan.analysis_type == AnalysisType.TREND


def test_planner_requires_approval_for_bulk_export():
    assert PlannerAgent().run("Export all customer records").requires_approval


def test_sql_agent_uses_only_profiled_table():
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
    queries = SqlAgent().run(profile, plan).queries
    assert any('"orders"' in query.sql for query in queries)
    assert any("GROUP BY" in query.sql for query in queries)
