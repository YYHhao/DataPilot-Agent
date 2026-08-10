from __future__ import annotations


RISK_TERMS = {
    "删除": "请求涉及删除数据",
    "覆盖": "请求涉及覆盖数据",
    "发送邮件": "请求涉及外部副作用",
    "导出全部": "请求涉及批量导出",
    "个人信贷": "请求涉及个人信贷决策",
    "医疗诊断": "请求涉及医疗诊断",
    "delete": "请求涉及删除数据",
    "overwrite": "请求涉及覆盖数据",
    "export all": "请求涉及批量导出",
    "send email": "请求涉及外部副作用",
    "credit decision": "请求涉及个人信贷决策",
}


def detect_risks(question: str) -> list[str]:
    lowered = question.lower()
    return sorted({reason for term, reason in RISK_TERMS.items() if term in lowered})
