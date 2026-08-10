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
            issues.append("分析引用了授权范围之外的数据表")
        for result in query_results:
            query_id = result["query_id"]
            if result["status"] != "ok":
                issues.append(f"{query_id} 未成功执行：{result['status']}")
            else:
                checked.append(query_id)
                if result.get("truncated"):
                    issues.append(f"{query_id} 的结果已截断，结论中必须注明该限制")
        evidence_ids = {item["evidence_id"] for item in analysis.get("evidence", [])}
        if evidence_ids != set(checked):
            issues.append("分析证据链不完整")
        if not checked:
            issues.append("没有可用的成功执行证据")

        blocking = any(
            marker in issue
            for issue in issues
            for marker in ("授权范围之外", "未成功执行", "证据链不完整", "没有可用")
        )
        score = max(0.0, 1.0 - 0.18 * len(issues))
        return ReviewResult(
            passed=not blocking,
            score=round(score, 2),
            issues=issues,
            recommendations=[
                "与数据负责人确认业务指标定义",
                "模型生成的解释在完成验证前应视为待验证假设",
                "导出或数据修改操作必须使用经过批准的工作流",
            ],
            checked_evidence=checked,
        )
