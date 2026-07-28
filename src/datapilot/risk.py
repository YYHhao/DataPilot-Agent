from __future__ import annotations


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


def detect_risks(question: str) -> list[str]:
    lowered = question.lower()
    return sorted({reason for term, reason in RISK_TERMS.items() if term in lowered})
