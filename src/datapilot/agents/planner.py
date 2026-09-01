from __future__ import annotations

from datapilot.llm import structured_model
from datapilot.models import AnalysisPlan, RiskLevel
from datapilot.observability import invoke_observed
from datapilot.risk import detect_risks


class PlannerAgent:
    """Uses an LLM to turn a request into a structured analysis plan."""

    def __init__(self, model=None) -> None:
        self._model = model
        self.last_usage: dict[str, int] = {}

    def run(self, question: str) -> AnalysisPlan:
        normalized = question.strip()
        if not normalized:
            raise ValueError("分析问题不能为空")
        model = self._model or structured_model(AnalysisPlan)
        plan, self.last_usage = invoke_observed(
            model,
            "你是一个受治理企业数据分析系统的规划智能体。"
            "将分析类型归类为 overview、data_quality、ranking、trend 或 correlation。"
            "返回简洁的中文目标和 2～5 个可执行的中文分析步骤，不得虚构数据库结构。"
            "请严格按照以下字段返回 JSON 对象，不要附加 Markdown 或解释："
            '{"objective":"中文目标","analysis_type":"overview|data_quality|ranking|trend|correlation",'
            '"steps":["步骤1","步骤2"],"risk_level":"low|medium|high",'
            '"requires_approval":false,"risk_reasons":[]}。'
            "风险审批由独立规则执行，不要把普通只读分析标记为高风险。"
            "除固定枚举值和技术标识外，所有文本均使用简体中文。"
            f"\n\n用户请求：{normalized}",
        )
        # Approval is a deterministic policy decision. Do not trust model-provided
        # risk reasons here: some compatible models put benign explanations such
        # as "standard read-only query" in this field, which would otherwise
        # incorrectly force an approval.
        risks = detect_risks(normalized)
        plan.risk_reasons = risks
        plan.requires_approval = bool(risks)
        if risks:
            plan.risk_level = RiskLevel.HIGH
        return plan
