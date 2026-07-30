from datapilot.models import SqlQuery, SqlQueryPlan


def test_workflow_executes_governed_sql_and_persists(enterprise_runtime):
    _, store, workflow = enterprise_runtime
    state = workflow.run("test_sales", "Rank regions by revenue")
    assert state["status"] == "completed"
    assert "Enterprise Data Analysis Report" in state["report"]
    assert state["query_results"][0]["rows"] == [[12]]
    assert {event["node"] for event in state["trace"]} >= {
        "planner",
        "schema_agent",
        "semantic_retriever",
        "sql_agent",
        "sql_runtime",
        "analyst",
        "reviewer",
        "reporter",
        "persistence",
    }
    assert store.load(state["run_id"])["run_id"] == state["run_id"]
    assert store.report_path(state["run_id"]).is_file()


def test_high_risk_workflow_pauses_before_schema_access(enterprise_runtime):
    _, _, workflow = enterprise_runtime
    state = workflow.run("test_sales", "Delete the source table and summarize it")
    assert state["status"] == "awaiting_approval"
    assert "schema_profile" not in state
    assert [event["node"] for event in state["trace"]] == [
        "planner",
        "approval_gate",
        "persistence",
    ]


def test_paused_run_resumes_with_same_identity(enterprise_runtime):
    _, _, workflow = enterprise_runtime
    paused = workflow.run("test_sales", "Delete the source table and summarize it")
    resumed = workflow.approve(paused["run_id"])
    assert resumed["run_id"] == paused["run_id"]
    assert resumed["status"] == "completed"


def test_unsafe_model_sql_is_rejected_and_fails_quality_gate(enterprise_runtime):
    _, _, workflow = enterprise_runtime
    unsafe_plan = SqlQueryPlan(
        dialect="sqlite",
        queries=[SqlQuery(query_id="Q1", purpose="unsafe query", sql="DELETE FROM sales")],
    )
    workflow.sql_agent.run = lambda *_: unsafe_plan
    workflow.sql_agent.repair = lambda *_: unsafe_plan
    state = workflow.run("test_sales", "Summarize revenue")
    assert state["query_results"][0]["status"] == "rejected"
    assert state["status"] == "quality_gate_failed"
    assert sum(event["node"] == "sql_repair_agent" for event in state["trace"]) == 2


def test_failed_sql_is_repaired_and_reexecuted(enterprise_runtime):
    _, _, workflow = enterprise_runtime
    workflow.sql_agent.run = lambda *_: SqlQueryPlan(
        dialect="sqlite",
        queries=[SqlQuery(query_id="Q1", purpose="broken query", sql="SELECT missing FROM sales")],
    )
    workflow.sql_agent.repair = lambda *_: SqlQueryPlan(
        dialect="sqlite",
        queries=[
            SqlQuery(
                query_id="Q1",
                purpose="repaired query",
                sql="SELECT COUNT(*) AS record_count FROM sales",
            )
        ],
    )
    state = workflow.run("test_sales", "Summarize revenue")
    assert state["status"] == "completed"
    assert state["sql_attempt"] == 2
    assert state["query_results"][0]["rows"] == [[12]]
    assert any(event["node"] == "sql_repair_agent" for event in state["trace"])


def test_unknown_dataset_is_rejected(enterprise_runtime):
    _, _, workflow = enterprise_runtime
    try:
        workflow.run("unknown", "Summarize revenue")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown dataset should be rejected")
