from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datapilot.agents import SqlAgent
from datapilot.catalog import DatasetCatalog
from datapilot.datasources import DataSourceFactory
from datapilot.models import AnalysisPlan, AnalysisType, RiskLevel, SqlQuery, SqlQueryPlan
from datapilot.retrieval import SemanticRetriever
from datapilot.security import validate_readonly_sql


def _normalized_value(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        return round(value, 6)
    return value


def results_equal(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Compare ordered result rows while ignoring model-chosen column aliases."""
    actual_rows = [[_normalized_value(value) for value in row] for row in actual["rows"]]
    expected_rows = [[_normalized_value(value) for value in row] for row in expected["rows"]]
    return actual_rows == expected_rows


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _metric_summary(details: list[dict[str, Any]], success_key: str) -> dict[str, Any]:
    latencies = [float(item["latency_ms"]) for item in details]
    successes = sum(bool(item[success_key]) for item in details)
    return {
        "cases": len(details),
        "successful_cases": successes,
        "success_rate": successes / len(details) if details else 0.0,
        "average_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "total_tokens": sum(item.get("tokens", {}).get("total_tokens", 0) for item in details),
        "details": details,
    }


def evaluate_text_to_sql(
    cases: list[dict[str, Any]], source, profile, retriever: SemanticRetriever
) -> dict[str, Any]:
    agent = SqlAgent()
    details = []
    for case in cases:
        gold = source.execute(case["gold_sql"])
        plan = AnalysisPlan(
            objective=case["question"],
            analysis_type=AnalysisType(case["analysis_type"]),
            steps=["生成只读 SQL", "执行并核对结果"],
            risk_level=RiskLevel.LOW,
        )
        semantics = retriever.retrieve(case["question"], profile)
        started = time.perf_counter()
        try:
            sql_plan = agent.run(profile, plan, semantics, case["question"])
            query_results = []
            for query in sql_plan.queries:
                try:
                    query_results.append({"sql": query.sql, "status": "ok", **source.execute(query.sql)})
                except Exception as exc:  # noqa: BLE001 - record SQL execution failure
                    query_results.append(
                        {
                            "sql": query.sql,
                            "status": "error",
                            "rows": [],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
            latency_ms = (time.perf_counter() - started) * 1000
            successful_results = [
                result for result in query_results if result["status"] == "ok"
            ]
            correct = any(results_equal(result, gold) for result in successful_results)
            execution_success = bool(successful_results) and all(
                result["status"] == "ok" for result in query_results
            )
            detail = {
                "id": case["id"],
                "correct": correct,
                "execution_success": execution_success,
                "latency_ms": round(latency_ms, 2),
                "tokens": agent.last_usage,
                "generated_sql": [result["sql"] for result in query_results],
            }
        except Exception as exc:  # noqa: BLE001 - continue after one failed online call
            detail = {
                "id": case["id"],
                "correct": False,
                "execution_success": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "tokens": agent.last_usage,
                "generated_sql": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
        details.append(detail)
        print(f"text_to_sql {'PASS' if detail['correct'] else 'FAIL'} {case['id']}")

    summary = _metric_summary(details, "correct")
    summary["execution_accuracy"] = summary.pop("success_rate")
    summary["execution_success_rate"] = (
        sum(item["execution_success"] for item in details) / len(details) if details else 0.0
    )
    return summary


def evaluate_repair(
    cases: list[dict[str, Any]], source, profile, retriever: SemanticRetriever
) -> dict[str, Any]:
    agent = SqlAgent()
    details = []
    for case in cases:
        gold = source.execute(case["gold_sql"])
        try:
            source.execute(case["broken_sql"])
            failure = "Benchmark case is invalid: broken_sql unexpectedly succeeded"
        except Exception as exc:  # noqa: BLE001 - database error becomes repair evidence
            failure = f"{type(exc).__name__}: {exc}"
        plan = AnalysisPlan(
            objective=case["question"],
            analysis_type=AnalysisType(case["analysis_type"]),
            steps=["生成只读 SQL", "执行并核对结果"],
            risk_level=RiskLevel.LOW,
        )
        previous = SqlQueryPlan(
            dialect="sqlite",
            queries=[SqlQuery(query_id="Q1", purpose="待修复查询", sql=case["broken_sql"])],
        )
        semantics = retriever.retrieve(case["question"], profile)
        started = time.perf_counter()
        try:
            repaired = agent.repair(
                profile,
                plan,
                previous,
                [{"query_id": "Q1", "status": "error", "error": failure}],
                semantics,
                case["question"],
            )
            outputs = [source.execute(query.sql) for query in repaired.queries]
            success = any(results_equal(output, gold) for output in outputs)
            detail = {
                "id": case["id"],
                "repaired_correctly": success,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "tokens": agent.last_usage,
                "broken_sql": case["broken_sql"],
                "repaired_sql": [query.sql for query in repaired.queries],
            }
        except Exception as exc:  # noqa: BLE001 - continue after one failed online call
            detail = {
                "id": case["id"],
                "repaired_correctly": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "tokens": agent.last_usage,
                "broken_sql": case["broken_sql"],
                "repaired_sql": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
        details.append(detail)
        print(f"repair {'PASS' if detail['repaired_correctly'] else 'FAIL'} {case['id']}")

    summary = _metric_summary(details, "repaired_correctly")
    summary["repair_success_rate"] = summary.pop("success_rate")
    return summary


def evaluate_security(cases: list[dict[str, Any]], allowed_tables: list[str]) -> dict[str, Any]:
    details = []
    for case in cases:
        try:
            validate_readonly_sql(case["sql"], allowed_tables)
            blocked = False
            error = None
        except ValueError as exc:
            blocked = True
            error = str(exc)
        passed = blocked == case["should_block"]
        details.append({**case, "blocked": blocked, "passed": passed, "error": error})
        print(f"security {'PASS' if passed else 'FAIL'} {case['id']}")

    attacks = [item for item in details if item["should_block"]]
    benign = [item for item in details if not item["should_block"]]
    return {
        "attack_cases": len(attacks),
        "blocked_attacks": sum(item["blocked"] for item in attacks),
        "interception_rate": (
            sum(item["blocked"] for item in attacks) / len(attacks) if attacks else 0.0
        ),
        "benign_cases": len(benign),
        "allowed_benign_queries": sum(not item["blocked"] for item in benign),
        "benign_acceptance_rate": (
            sum(not item["blocked"] for item in benign) / len(benign) if benign else 0.0
        ),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run focused DataPilot business benchmarks")
    parser.add_argument("--limit", type=int, default=None, help="Limit Text-to-SQL cases")
    parser.add_argument("--repair-limit", type=int, default=None, help="Limit repair cases")
    parser.add_argument("--output", default="evaluation/business_results.json")
    args = parser.parse_args()

    root = Path(__file__).parents[1]
    benchmark = json.loads(
        (root / "evaluation" / "business_cases.json").read_text(encoding="utf-8")
    )
    catalog = DatasetCatalog(root / "data" / "catalog.json")
    definition = catalog.get("demo_sales")
    source = DataSourceFactory(catalog.path.parent).create(definition)
    profile = source.inspect_schema()
    retriever = SemanticRetriever(root / "data" / "semantic_catalog.json")

    text_to_sql = evaluate_text_to_sql(
        benchmark["text_to_sql"][: args.limit], source, profile, retriever
    )

    repair = evaluate_repair(
        benchmark["repair"][: args.repair_limit], source, profile, retriever
    )
    security = evaluate_security(benchmark["security"], definition.allowed_tables)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_id": definition.dataset_id,
        "table_count": len(definition.allowed_tables),
        "methodology": {
            "text_to_sql": "Predicted and gold SQL are executed on the same database; ordered result rows must be equal. Column aliases are ignored.",
            "repair": "The model receives a known failing SQL statement and database error; repaired SQL must equal the gold query result.",
            "security": "Known malicious SQL must be rejected and benign read-only SQL must be accepted by the deterministic validator.",
        },
        "text_to_sql": text_to_sql,
        "sql_repair": repair,
        "security": security,
    }
    output = root / args.output
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    headline = {
        "text_to_sql_execution_accuracy": text_to_sql["execution_accuracy"],
        "sql_repair_success_rate": repair["repair_success_rate"],
        "security_interception_rate": security["interception_rate"],
        "benign_acceptance_rate": security["benign_acceptance_rate"],
        "text_to_sql_p50_latency_ms": text_to_sql["p50_latency_ms"],
        "text_to_sql_p95_latency_ms": text_to_sql["p95_latency_ms"],
    }
    print(json.dumps(headline, ensure_ascii=False, indent=2))
    print(f"saved={output}")


if __name__ == "__main__":
    main()
