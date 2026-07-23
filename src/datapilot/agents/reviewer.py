from __future__ import annotations

from datapilot.models import ReviewResult, SchemaProfile


class ReviewerAgent:
    """Checks execution status, evidence lineage, and result boundaries."""

    def run(
        self,
        analysis: dict,
        profile: SchemaProfile,
        query_results: list[dict],
    ) -> ReviewResult:
        issues: list[str] = []
        checked: list[str] = []
        allowed_tables = {table.name for table in profile.tables}
        if set(analysis.get("tables_used", [])) - allowed_tables:
            issues.append("Analysis references a table outside the approved schema")
        for result in query_results:
            query_id = result["query_id"]
            if result["status"] != "ok":
                issues.append(f"{query_id} did not execute successfully: {result['status']}")
            else:
                checked.append(query_id)
                if result.get("truncated"):
                    issues.append(f"{query_id} was truncated; conclusions must note the limit")
        evidence_ids = {item["evidence_id"] for item in analysis.get("evidence", [])}
        if evidence_ids != set(checked):
            issues.append("Analysis evidence lineage is incomplete")
        if not checked:
            issues.append("No executable evidence is available")

        blocking = any(
            marker in issue
            for issue in issues
            for marker in ("outside", "did not execute", "incomplete", "No executable")
        )
        score = max(0.0, 1.0 - 0.18 * len(issues))
        return ReviewResult(
            passed=not blocking,
            score=round(score, 2),
            issues=issues,
            recommendations=[
                "Confirm business metric definitions with the data owner",
                "Treat model-generated interpretations as hypotheses until validated",
                "Use an approved workflow for exports or data-changing actions",
            ],
            checked_evidence=checked,
        )
