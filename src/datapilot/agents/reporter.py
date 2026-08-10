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
                    f"- 状态：**{result['status']}**\n"
                    f"- 错误：`{result.get('error', '未知错误')}`"
                )
                continue
            preview = json.dumps(result["rows"][:20], ensure_ascii=False, default=str)
            evidence_blocks.append(
                f"### [{query_id}] {result['purpose']}\n\n"
                f"```sql\n{result['sql']}\n```\n\n"
                f"- 返回字段：`{', '.join(result['columns'])}`\n"
                f"- 返回行数：**{result['row_count']}**\n"
                f"- 是否截断：**{'是' if result['truncated'] else '否'}**\n"
                f"- 证据预览：`{preview}`"
            )
        evidence_text = "\n\n".join(evidence_blocks)
        findings = (
            "\n".join(f"- {item}" for item in analysis.get("findings", []))
            or "- 未生成经过验证的发现"
        )
        issues = "\n".join(f"- {item}" for item in review.issues) or "- 未发现阻塞性问题"
        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(plan.steps, 1))
        recommendations = "\n".join(f"- {item}" for item in review.recommendations) or "- 无"
        semantic_lines = "\n".join(
            f"- **{item.document.name}** (`{item.document.id}`): "
            f"{item.document.description}"
            + (f"；公式：`{item.document.formula}`" if item.document.formula else "")
            for item in semantics or []
        ) or "- 未找到与请求匹配的受治理业务定义"
        return f"""# 企业数据分析报告

## 分析目标

{plan.objective}

## 受治理数据源

- 数据集：**{profile.dataset_name}**（`{profile.dataset_id}`）
- 数据库类型：**{profile.driver}**
- 目录说明：{profile.description or "未提供"}

{schema_lines}

## 检索到的业务定义

{semantic_lines}

## 执行计划

- 分析类型：**{plan.analysis_type.value}**
- 风险等级：**{plan.risk_level.value}**
- 是否需要审批：**{'是' if plan.requires_approval else '否'}**

{steps}

## SQL 证据

{evidence_text}

## 基于证据的分析发现

{findings}

## 独立复核

- 质量门禁：**{"通过" if review.passed else "未通过"}**
- 评分：**{review.score:.2f}**
- 已验证证据：**{", ".join(review.checked_evidence) or "无"}**

{issues}

### 建议

{recommendations}

## 结论边界

以上每项结果均关联到实际执行的只读查询。本报告不能证明因果关系，业务定义仍需由
数据负责人确认。数据导出、外部副作用和数据修改操作必须通过单独审批的工作流执行。
"""
