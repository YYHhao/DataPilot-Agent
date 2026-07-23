from __future__ import annotations

from datapilot.config import settings
from datapilot.models import AnalysisPlan, AnalysisType, RiskLevel


class PlannerAgent:
    """Turns a user request into a structured plan and enforces deterministic risk policy."""

    RISK_TERMS = {
        "删除": "request asks to delete data",
        "覆盖": "request asks to overwrite data",
        "发送邮件": "request asks for an external side effect",
        "导出全部": "request asks for a bulk export",
        "个人信贷": "request involves an individual credit decision",
        "医疗诊断": "request involves medical diagnosis",
        "delete": "request asks to delete data",
        "overwrite": "request asks to overwrite data",
        "export all": "request asks for a bulk export",
        "send email": "request asks for an external side effect",
        "credit decision": "request involves an individual credit decision",
    }
    INTENT_TERMS = {
        AnalysisType.DATA_QUALITY: ("质量", "缺失", "重复", "异常值", "quality", "missing"),
        AnalysisType.CORRELATION: ("相关", "关系", "影响", "correlation", "relationship"),
        AnalysisType.TREND: ("趋势", "同比", "环比", "按月", "trend", "monthly"),
        AnalysisType.RANKING: ("排名", "最高", "最低", "top", "bottom", "rank"),
    }

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
            ).with_structured_output(AnalysisPlan)

    def run(self, question: str) -> AnalysisPlan:
        normalized = question.strip()
        if not normalized:
            raise ValueError("Question cannot be empty")
        lowered = normalized.lower()
        risk_reasons = [reason for term, reason in self.RISK_TERMS.items() if term in lowered]
        analysis_type = next(
            (
                intent
                for intent, terms in self.INTENT_TERMS.items()
                if any(term in lowered for term in terms)
            ),
            AnalysisType.OVERVIEW,
        )
        if self._model is not None:
            generated = self._model.invoke(
                "Create a concise enterprise data-analysis plan. Do not approve risky "
                "actions. Use only the requested objective. Request: " + normalized
            )
            generated.risk_reasons = sorted(set(generated.risk_reasons + risk_reasons))
            generated.requires_approval = bool(generated.risk_reasons)
            generated.risk_level = (
                RiskLevel.HIGH if generated.requires_approval else generated.risk_level
            )
            return generated
        return AnalysisPlan(
            objective=normalized,
            steps=[
                "inspect the dataset schema and data-quality risks",
                "plan and execute read-only analytical SQL",
                "compute question-specific deterministic evidence",
                "review numerical consistency and unsupported claims",
                "produce an evidence-linked report with audit artifacts",
            ],
            analysis_type=analysis_type,
            risk_level=RiskLevel.HIGH if risk_reasons else RiskLevel.LOW,
            requires_approval=bool(risk_reasons),
            risk_reasons=risk_reasons,
        )
