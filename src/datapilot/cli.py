from __future__ import annotations

import argparse

from datapilot.workflow import DataPilotWorkflow


def main() -> None:
    parser = argparse.ArgumentParser(description="运行受治理的企业数据分析任务")
    parser.add_argument("dataset_id", help="数据目录中登记的数据集 ID")
    parser.add_argument("question", help="要分析的自然语言问题")
    parser.add_argument("--approved", action="store_true", help="批准需要人工确认的高风险任务")
    args = parser.parse_args()
    state = DataPilotWorkflow().run(args.dataset_id, args.question, args.approved)
    print(state.get("report") or f"任务状态：{state['status']}（任务 ID：{state['run_id']}）")
