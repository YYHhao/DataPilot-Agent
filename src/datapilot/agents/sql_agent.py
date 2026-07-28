from __future__ import annotations

import json

from datapilot.config import settings
from datapilot.llm import structured_model
from datapilot.models import AnalysisPlan, SchemaProfile, SqlQueryPlan


class SqlAgent:
    """Generates and repairs bounded analytical SQL through an LLM."""

    def __init__(self, model=None) -> None:
        self._model = model

    def run(self, profile: SchemaProfile, plan: AnalysisPlan) -> SqlQueryPlan:
        return self._invoke(self._prompt(profile, plan))

    def repair(
        self,
        profile: SchemaProfile,
        plan: AnalysisPlan,
        previous: SqlQueryPlan,
        failures: list[dict],
    ) -> SqlQueryPlan:
        return self._invoke(
            self._prompt(profile, plan)
            + "\n\nThe previous query plan failed. Return a complete corrected plan.\n"
            + "Previous plan:\n"
            + previous.model_dump_json()
            + "\nFailures:\n"
            + json.dumps(failures, ensure_ascii=False)
        )

    def _invoke(self, prompt: str) -> SqlQueryPlan:
        model = self._model or structured_model(SqlQueryPlan)
        return model.invoke(prompt)

    @staticmethod
    def _prompt(profile: SchemaProfile, plan: AnalysisPlan) -> str:
        schema = "\n".join(
            f"{table.name}: "
            + ", ".join(f"{column.name} {column.data_type}" for column in table.columns)
            for table in profile.tables
        )
        return (
            "You are a Text-to-SQL agent. Generate 1-5 read-only analytical queries. "
            f"Dialect: {profile.driver}. Use only the schema below. Never use SELECT *, "
            "write operations, system tables, comments, or multiple statements. "
            f"Every detail query must be bounded and results are capped at "
            f"{settings.max_result_rows} rows. Query IDs must be Q1, Q2, ...\n\n"
            f"Objective: {plan.objective}\nAnalysis type: {plan.analysis_type.value}\n"
            f"Plan: {plan.steps}\nSchema:\n{schema}"
        )
