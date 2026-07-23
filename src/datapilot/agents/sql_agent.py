from __future__ import annotations

from datapilot.config import settings
from datapilot.datasources import quote_identifier
from datapilot.models import (
    AnalysisPlan,
    AnalysisType,
    SchemaProfile,
    SqlQuery,
    SqlQueryPlan,
)


NUMERIC_TYPES = ("int", "real", "double", "float", "numeric", "decimal")
DATE_TYPES = ("date", "time")


class SqlAgent:
    """Creates bounded analytical queries; the runtime independently validates them."""

    def __init__(self) -> None:
        self._model = None
        if settings.model_provider.lower() == "openai":
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "Install the 'openai' extra to use DATAPILOT_MODEL_PROVIDER=openai"
                ) from exc
            self._model = ChatOpenAI(
                model=settings.model_name, temperature=0
            ).with_structured_output(SqlQueryPlan)

    def run(self, profile: SchemaProfile, plan: AnalysisPlan) -> SqlQueryPlan:
        if self._model is not None:
            return self._model.invoke(self._prompt(profile, plan))
        return self._deterministic_plan(profile, plan)

    @staticmethod
    def _prompt(profile: SchemaProfile, plan: AnalysisPlan) -> str:
        schema = "\n".join(
            f"{table.name}: "
            + ", ".join(f"{column.name} {column.data_type}" for column in table.columns)
            for table in profile.tables
        )
        return (
            f"Generate 1-5 read-only {profile.driver} analytical queries. "
            "Use only the schema below. Never use SELECT *, write operations, system tables, "
            "comments, multiple statements, or unbounded detail queries. Every query must "
            f"have a query ID Q1..Q5 and return at most {settings.max_result_rows} rows.\n"
            f"Objective: {plan.objective}\nSchema:\n{schema}"
        )

    @staticmethod
    def _deterministic_plan(profile: SchemaProfile, plan: AnalysisPlan) -> SqlQueryPlan:
        table = profile.tables[0]
        table_name = quote_identifier(table.name)
        numeric = [
            column
            for column in table.columns
            if any(kind in column.data_type.lower() for kind in NUMERIC_TYPES)
            and not column.primary_key
        ]
        dimensions = [
            column
            for column in table.columns
            if column not in numeric
            and not any(kind in column.data_type.lower() for kind in DATE_TYPES)
            and not column.primary_key
        ]
        dates = [
            column
            for column in table.columns
            if any(kind in column.data_type.lower() for kind in DATE_TYPES)
            or any(term in column.name.lower() for term in ("date", "time", "month", "日期"))
        ]
        queries = [
            SqlQuery(
                query_id="Q1",
                purpose=f"count records in {table.name}",
                sql=f"SELECT COUNT(*) AS record_count FROM {table_name}",
            )
        ]
        if plan.analysis_type == AnalysisType.DATA_QUALITY:
            null_terms = ", ".join(
                f"SUM(CASE WHEN {quote_identifier(column.name)} IS NULL THEN 1 ELSE 0 END) "
                f"AS {quote_identifier(column.name + '_nulls')}"
                for column in table.columns[:20]
            )
            queries.append(
                SqlQuery(
                    query_id="Q2",
                    purpose=f"measure null values in {table.name}",
                    sql=f"SELECT COUNT(*) AS total_rows, {null_terms} FROM {table_name}",
                )
            )
        if (
            numeric
            and dimensions
            and plan.analysis_type
            in {
                AnalysisType.OVERVIEW,
                AnalysisType.RANKING,
            }
        ):
            measure, dimension = numeric[0], dimensions[0]
            queries.append(
                SqlQuery(
                    query_id="Q2",
                    purpose=f"rank {dimension.name} by {measure.name}",
                    sql=(
                        f"SELECT {quote_identifier(dimension.name)} AS dimension, "
                        f"COUNT(*) AS records, "
                        f"SUM({quote_identifier(measure.name)}) AS metric "
                        f"FROM {table_name} "
                        f"WHERE {quote_identifier(dimension.name)} IS NOT NULL "
                        f"GROUP BY {quote_identifier(dimension.name)} "
                        "ORDER BY metric DESC LIMIT 10"
                    ),
                )
            )
        if len(numeric) >= 2 and plan.analysis_type == AnalysisType.CORRELATION:
            left, right = numeric[:2]
            x, y = quote_identifier(left.name), quote_identifier(right.name)
            queries.append(
                SqlQuery(
                    query_id=f"Q{len(queries) + 1}",
                    purpose=f"calculate correlation between {left.name} and {right.name}",
                    sql=(
                        "WITH stats AS (SELECT "
                        f"COUNT(*) AS n, SUM({x}) AS sx, SUM({y}) AS sy, "
                        f"SUM({x} * {y}) AS sxy, SUM({x} * {x}) AS sx2, "
                        f"SUM({y} * {y}) AS sy2 FROM {table_name} "
                        f"WHERE {x} IS NOT NULL AND {y} IS NOT NULL) "
                        "SELECT (n * sxy - sx * sy) / "
                        "NULLIF(SQRT((n * sx2 - sx * sx) * (n * sy2 - sy * sy)), 0) "
                        "AS correlation FROM stats"
                    ),
                )
            )
        if numeric:
            measure = numeric[0]
            queries.append(
                SqlQuery(
                    query_id=f"Q{len(queries) + 1}",
                    purpose=f"summarize {measure.name}",
                    sql=(
                        f"SELECT COUNT({quote_identifier(measure.name)}) AS non_null_count, "
                        f"AVG({quote_identifier(measure.name)}) AS mean, "
                        f"MIN({quote_identifier(measure.name)}) AS minimum, "
                        f"MAX({quote_identifier(measure.name)}) AS maximum "
                        f"FROM {table_name}"
                    ),
                )
            )
        if numeric and dates and plan.analysis_type == AnalysisType.TREND:
            measure, date = numeric[0], dates[0]
            period = (
                f"strftime('%Y-%m', {quote_identifier(date.name)})"
                if profile.driver == "sqlite"
                else f"to_char({quote_identifier(date.name)}, 'YYYY-MM')"
            )
            queries.append(
                SqlQuery(
                    query_id=f"Q{len(queries) + 1}",
                    purpose=f"analyze monthly {measure.name} trend",
                    sql=(
                        f"SELECT {period} AS period, "
                        f"SUM({quote_identifier(measure.name)}) AS metric "
                        f"FROM {table_name} GROUP BY period ORDER BY period LIMIT 120"
                    ),
                )
            )
        return SqlQueryPlan(dialect=profile.driver, queries=queries)
