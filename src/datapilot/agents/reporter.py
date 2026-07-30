from __future__ import annotations

import json

from datapilot.models import AnalysisPlan, RetrievedSemantic, ReviewResult, SchemaProfile


class ReporterAgent:
    def run(
        self,
        plan: AnalysisPlan,
        profile: SchemaProfile,
        analysis: dict,
        query_results: list[dict],
        review: ReviewResult,
        semantics: list[RetrievedSemantic] | None = None,
    ) -> str:
        schema_lines = "\n".join(
            f"- `{table.name}`: "
            + ", ".join(f"`{column.name}` ({column.data_type})" for column in table.columns)
            for table in profile.tables
        )
        evidence_blocks = []
        for result in query_results:
            query_id = result["query_id"]
            if result["status"] != "ok":
                evidence_blocks.append(
                    f"### [{query_id}] {result['purpose']}\n\n"
                    f"- Status: **{result['status']}**\n"
                    f"- Error: `{result.get('error', 'unknown')}`"
                )
                continue
            preview = json.dumps(result["rows"][:20], ensure_ascii=False, default=str)
            evidence_blocks.append(
                f"### [{query_id}] {result['purpose']}\n\n"
                f"```sql\n{result['sql']}\n```\n\n"
                f"- Columns: `{', '.join(result['columns'])}`\n"
                f"- Returned rows: **{result['row_count']}**\n"
                f"- Truncated: **{result['truncated']}**\n"
                f"- Evidence preview: `{preview}`"
            )
        evidence_text = "\n\n".join(evidence_blocks)
        findings = (
            "\n".join(f"- {item}" for item in analysis.get("findings", []))
            or "- No verified finding was produced"
        )
        issues = "\n".join(f"- {item}" for item in review.issues) or "- No blocking issue"
        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(plan.steps, 1))
        recommendations = "\n".join(f"- {item}" for item in review.recommendations) or "- None"
        semantic_lines = "\n".join(
            f"- **{item.document.name}** (`{item.document.id}`): "
            f"{item.document.description}"
            + (f" Formula: `{item.document.formula}`" if item.document.formula else "")
            for item in semantics or []
        ) or "- No governed business definition matched the request"
        return f"""# Enterprise Data Analysis Report

## Objective

{plan.objective}

## Governed data source

- Dataset: **{profile.dataset_name}** (`{profile.dataset_id}`)
- Driver: **{profile.driver}**
- Catalog description: {profile.description or "Not provided"}

{schema_lines}

## Retrieved business definitions

{semantic_lines}

## Execution plan

- Analysis type: **{plan.analysis_type.value}**
- Risk level: **{plan.risk_level.value}**
- Approval required: **{plan.requires_approval}**

{steps}

## SQL evidence

{evidence_text}

## Evidence-linked findings

{findings}

## Independent review

- Gate: **{"PASS" if review.passed else "FAIL"}**
- Score: **{review.score:.2f}**
- Verified evidence: **{", ".join(review.checked_evidence) or "None"}**

{issues}

### Recommendations

{recommendations}

## Decision boundary

Every result above is linked to an executed read-only query. The report does not establish
causality, and business definitions must be confirmed by a data owner. Exports, external side
effects, and data-changing actions require a separately approved workflow.
"""
