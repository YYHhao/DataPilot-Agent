from __future__ import annotations

import json
import tempfile
from pathlib import Path

from datapilot.catalog import DatasetCatalog
from datapilot.storage import JsonRunStore
from datapilot.workflow import DataPilotWorkflow


def main() -> None:
    root = Path(__file__).parents[1]
    database = root / "data" / "demo.sqlite"
    if not database.is_file():
        raise SystemExit("Run `python scripts/seed_demo.py` before evaluation.")
    cases = [
        json.loads(line)
        for line in (root / "evaluation" / "dataset.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    passed = 0
    with tempfile.TemporaryDirectory() as temporary:
        workflow = DataPilotWorkflow(
            DatasetCatalog(root / "data" / "catalog.json"),
            JsonRunStore(Path(temporary) / "runs"),
        )
        for case in cases:
            state = workflow.run(case["dataset_id"], case["question"])
            nodes = {event["node"] for event in state["trace"]}
            ok = state["status"] == case["expected_status"]
            ok = ok and set(case.get("required_nodes", [])).issubset(nodes)
            if "required_purpose" in case:
                ok = ok and any(
                    case["required_purpose"] in result["purpose"]
                    for result in state.get("query_results", [])
                )
            passed += int(ok)
            print(f"{'PASS' if ok else 'FAIL'} {case['id']}")
    print(f"task_success_rate={passed / len(cases):.3f} ({passed}/{len(cases)})")


if __name__ == "__main__":
    main()
