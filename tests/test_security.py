import pytest

from datapilot.security import validate_question_scope, validate_readonly_sql


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM sales",
        "SELECT * FROM sales; DROP TABLE sales",
        "PRAGMA table_info(sales)",
        "SELECT * FROM secrets",
    ],
)
def test_rejects_unsafe_or_unauthorized_sql(sql):
    with pytest.raises(ValueError):
        validate_readonly_sql(sql, ["sales"])


def test_accepts_readonly_query_and_cte():
    validate_readonly_sql("SELECT region, SUM(revenue) FROM sales GROUP BY region", ["sales"])
    validate_readonly_sql(
        "WITH totals AS (SELECT SUM(revenue) AS x FROM sales) SELECT x FROM totals",
        ["sales"],
    )


def test_rejects_model_invented_relative_time_filter():
    sql = "SELECT COUNT(*) FROM orders WHERE created_at >= CURRENT_DATE - INTERVAL '24 months'"
    with pytest.raises(ValueError, match="用户没有指定"):
        validate_question_scope(sql, "分析每个月的订单数量")


def test_allows_relative_time_filter_when_user_requests_it():
    sql = "SELECT COUNT(*) FROM orders WHERE created_at >= CURRENT_DATE - INTERVAL '24 months'"
    validate_question_scope(sql, "分析最近24个月的订单数量")
