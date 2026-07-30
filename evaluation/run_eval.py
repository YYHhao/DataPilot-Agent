from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from pathlib import Path

from datapilot.catalog import DatasetCatalog
from datapilot.storage import JsonRunStore
from datapilot.workflow import DataPilotWorkflow


def _references(sql: str, candidates: list[str]) -> set[str]:
    lowered = sql.lower()
    return {candidate for candidate in candidates if re.search(rf"\b{candidate.lower()}\b", lowered)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the live DataPilot agent")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default="evaluation/results.json")
    args = parser.parse_args()

    root = Path(__file__).parents[1]
    if not (root / "data" / "demo.sqlite").is_file():
        raise SystemExit("Run `python scripts/seed_demo.py` before evaluation.")
    cases = [
        json.loads(line)
        for line in (root / "evaluation" / "dataset.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ][: args.limit]

    totals = {
        "cases": len(cases),
        "status_correct": 0,
        "execution_success_cases": 0,
        "table_correct": 0,
        "column_correct": 0,
        "semantic_hit": 0,
        "security_cases": 0,
        "security_correct": 0,
        "analytical_cases": 0,
        "latency_ms": 0.0,
    }
    details = []
    with tempfile.TemporaryDirectory() as temporary:
        workflow = DataPilotWorkflow(
            DatasetCatalog(root / "data" / "catalog.json"),
            JsonRunStore(Path(temporary) / "runs"),
        )
        for case in cases:
            started = time.perf_counter()
            state = workflow.run(case["dataset_id"], case["question"])
            latency_ms = (time.perf_counter() - started) * 1000
            results = state.get("query_results", [])
            sql_text = "\n".join(result["sql"] for result in results)
            expected_tables = case.get("expected_tables", [])
            expected_columns = case.get("expected_columns", [])
            retrieved_ids = {
                item["document"]["id"] for item in state.get("semantic_context", [])
            }

            status_correct = state["status"] == case["expected_status"]
            execution_success = bool(results) and all(
                result["status"] == "ok" for result in results
            )
            table_correct = (
                not expected_tables
                or _references(sql_text, expected_tables) == set(expected_tables)
            )
            column_correct = (
                not expected_columns
                or set(expected_columns).issubset(_references(sql_text, expected_columns))
            )
            semantic_hit = (
                not case.get("expected_semantic_ids")
                or bool(retrieved_ids & set(case["expected_semantic_ids"]))
            )
            security_correct = (
                not case.get("security_case")
                or state["status"] == "awaiting_approval"
                or any(result["status"] == "rejected" for result in results)
            )

            totals["status_correct"] += int(status_correct)
            if case.get("security_case"):
                totals["security_cases"] += 1
                totals["security_correct"] += int(security_correct)
            else:
                totals["analytical_cases"] += 1
                totals["execution_success_cases"] += int(execution_success)
            totals["table_correct"] += int(table_correct)
            totals["column_correct"] += int(column_correct)
            totals["semantic_hit"] += int(semantic_hit)
            totals["latency_ms"] += latency_ms
            passed = all(
                [
                    status_correct,
                    table_correct,
                    column_correct,
                    semantic_hit,
                    security_correct,
                    execution_success or case.get("security_case", False),
                ]
            )
            details.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "status": state["status"],
                    "latency_ms": round(latency_ms, 2),
                    "sql_attempts": state.get("sql_attempt", 0),
                    "retrieved_ids": sorted(retrieved_ids),
                }
            )
            print(f"{'PASS' if passed else 'FAIL'} {case['id']}")

    count = totals["cases"] or 1
    report = {
        "case_count": totals["cases"],
        "task_success_rate": sum(item["passed"] for item in details) / count,
        "status_accuracy": totals["status_correct"] / count,
        "sql_execution_success_rate": totals["execution_success_cases"]
        / (totals["analytical_cases"] or 1),
        "table_selection_accuracy": totals["table_correct"] / count,
        "column_selection_accuracy": totals["column_correct"] / count,
        "semantic_retrieval_hit_rate": totals["semantic_hit"] / count,
        "security_interception_rate": totals["security_correct"]
        / (totals["security_cases"] or 1),
        "average_latency_ms": totals["latency_ms"] / count,
        "details": details,
    }
    output = root / args.output
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, indent=2))
    print(f"saved={output}")


if __name__ == "__main__":
    main()
