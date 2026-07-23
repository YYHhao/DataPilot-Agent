from __future__ import annotations

from typing import Any

from datapilot.models import AnalysisPlan, SchemaProfile


class AnalystAgent:
    """Builds claims only from successfully executed, addressable evidence."""

    def run(
        self,
        profile: SchemaProfile,
        plan: AnalysisPlan,
        query_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        evidence = []
        findings = []
        for result in query_results:
            if result["status"] != "ok":
                continue
            evidence.append(
                {
                    "evidence_id": result["query_id"],
                    "purpose": result["purpose"],
                    "columns": result["columns"],
                    "rows": result["rows"],
                    "row_count": result["row_count"],
                    "truncated": result["truncated"],
                }
            )
            if result["rows"]:
                row = result["rows"][0]
                rendered = ", ".join(
                    f"{column}={value}"
                    for column, value in zip(result["columns"], row, strict=False)
                )
                findings.append(f"[{result['query_id']}] {result['purpose']}: {rendered}")
        return {
            "objective": plan.objective,
            "analysis_type": plan.analysis_type,
            "dataset": profile.dataset_name,
            "tables_used": [table.name for table in profile.tables],
            "evidence": evidence,
            "findings": findings,
            "failed_queries": [
                result["query_id"] for result in query_results if result["status"] != "ok"
            ],
        }
