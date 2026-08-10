from __future__ import annotations

import json

from datapilot.config import settings
from datapilot.llm import structured_model
from datapilot.models import AnalysisPlan, RetrievedSemantic, SchemaProfile, SqlQueryPlan
from datapilot.observability import invoke_observed


class SqlAgent:
    """Generates and repairs bounded analytical SQL through an LLM."""

    def __init__(self, model=None) -> None:
        self._model = model
        self.last_usage: dict[str, int] = {}

    def run(
        self,
        profile: SchemaProfile,
        plan: AnalysisPlan,
        semantics: list[RetrievedSemantic] | None = None,
        question: str = "",
    ) -> SqlQueryPlan:
        return self._invoke(self._prompt(profile, plan, semantics or [], question))

    def repair(
        self,
        profile: SchemaProfile,
        plan: AnalysisPlan,
        previous: SqlQueryPlan,
        failures: list[dict],
        semantics: list[RetrievedSemantic] | None = None,
        question: str = "",
    ) -> SqlQueryPlan:
        return self._invoke(
            self._prompt(profile, plan, semantics or [], question)
            + "\n\n上一次查询计划执行失败，请返回一份完整的修正计划。\n"
            + "上一次计划：\n"
            + previous.model_dump_json()
            + "\n失败信息：\n"
            + json.dumps(failures, ensure_ascii=False)
        )

    def _invoke(self, prompt: str) -> SqlQueryPlan:
        model = self._model or structured_model(SqlQueryPlan)
        result, self.last_usage = invoke_observed(model, prompt)
        return result

    @staticmethod
    def _prompt(
        profile: SchemaProfile,
        plan: AnalysisPlan,
        semantics: list[RetrievedSemantic],
        question: str = "",
    ) -> str:
        schema = "\n".join(
            f"{table.name}: "
            + ", ".join(f"{column.name} {column.data_type}" for column in table.columns)
            for table in profile.tables
        )
        semantic_context = "\n".join(
            f"- [{item.document.kind}] {item.document.name}: "
            f"{item.document.description} Formula: {item.document.formula or 'N/A'} "
            f"(table={item.document.table}, columns={item.document.columns}, "
            f"retrieval_score={item.score})"
            for item in semantics
        )
        return (
            "你是 Text-to-SQL 智能体，请生成 1～5 条只读分析查询。"
            f"数据库方言：{profile.driver}。只能使用下方给出的结构。严禁 SELECT *、"
            "写操作、系统表、SQL 注释或多语句。purpose 字段必须使用简体中文。"
            "必须严格遵守用户明确给出的时间范围；如果用户没有指定时间范围，"
            "不得擅自添加最近若干月、当前年份、CURRENT_DATE、NOW() 等时间过滤。"
            f"明细查询必须限制范围，结果最多返回 {settings.max_result_rows} 行。"
            "查询 ID 必须依次为 Q1、Q2……\n\n"
            f"用户原始问题：{question or '未提供'}\n"
            f"分析目标：{plan.objective}\n分析类型：{plan.analysis_type.value}\n"
            f"分析计划：{plan.steps}\n数据库结构：\n{schema}\n\n"
            "检索到的受治理业务语义（优先采用这些定义和公式，不得另行虚构）：\n"
            f"{semantic_context or '未找到匹配的受治理业务定义。'}"
        )
