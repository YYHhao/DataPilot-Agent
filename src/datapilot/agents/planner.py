from __future__ import annotations

from datapilot.llm import structured_model
from datapilot.models import AnalysisPlan, RiskLevel
from datapilot.risk import detect_risks


class PlannerAgent:
    """Uses an LLM to turn a request into a structured analysis plan."""

    def __init__(self, model=None) -> None:
        self._model = model

    def run(self, question: str) -> AnalysisPlan:
        normalized = question.strip()
        if not normalized:
            raise ValueError("Question cannot be empty")
        model = self._model or structured_model(AnalysisPlan)
        plan = model.invoke(
            "You are the planning agent of a governed enterprise analytics system. "
            "Classify the analysis as overview, data_quality, ranking, trend, or correlation. "
            "Return a concise objective and 2-5 executable analysis steps. Do not invent schema. "
            "Risk approval is enforced separately, so do not mark ordinary read-only analytics "
            f"as risky.\n\nUser request: {normalized}"
        )
        risks = sorted(set(plan.risk_reasons + detect_risks(normalized)))
        plan.risk_reasons = risks
        plan.requires_approval = bool(risks)
        if risks:
            plan.risk_level = RiskLevel.HIGH
        return plan
