import pytest

from datapilot.security import validate_readonly_sql


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
