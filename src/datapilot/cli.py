from __future__ import annotations

import argparse

from datapilot.workflow import DataPilotWorkflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Run governed enterprise analytics")
    parser.add_argument("dataset_id", help="ID from the governed dataset catalog")
    parser.add_argument("question")
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    state = DataPilotWorkflow().run(args.dataset_id, args.question, args.approved)
    print(state.get("report") or f"Run status: {state['status']} ({state['run_id']})")
