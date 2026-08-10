from __future__ import annotations

import json
import sqlite3

import pytest

from datapilot.catalog import DatasetCatalog
from datapilot.models import (
    AnalysisPlan,
    AnalysisType,
    RiskLevel,
    SqlQuery,
    SqlQueryPlan,
)
from datapilot.risk import detect_risks
from datapilot.storage import JsonRunStore
from datapilot.workflow import DataPilotWorkflow


class FakePlanner:
    def run(self, question: str) -> AnalysisPlan:
        risks = detect_risks(question)
        return AnalysisPlan(
            objective=question,
            analysis_type=(
                AnalysisType.RANKING if "rank" in question.lower() else AnalysisType.OVERVIEW
            ),
            steps=["inspect schema", "query approved data", "review evidence"],
            risk_level=RiskLevel.HIGH if risks else RiskLevel.LOW,
            requires_approval=bool(risks),
            risk_reasons=risks,
        )


class FakeSqlAgent:
    def run(self, profile, plan, semantics=None, question="") -> SqlQueryPlan:
        return SqlQueryPlan(
            dialect=profile.driver,
            queries=[
                SqlQuery(
                    query_id="Q1",
                    purpose="count records",
                    sql='SELECT COUNT(*) AS record_count FROM "sales"',
                )
            ],
        )

    def repair(
        self, profile, plan, previous, failures, semantics=None, question=""
    ) -> SqlQueryPlan:
        return self.run(profile, plan, question=question)


class FakeRetriever:
    def retrieve(self, question, profile):
        return []


@pytest.fixture
def enterprise_runtime(tmp_path):
    database = tmp_path / "sales.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                order_date TEXT NOT NULL,
                region TEXT NOT NULL,
                revenue REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO sales (order_date, region, revenue, quantity)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("2026-01-01", "East", 100.0, 2),
                ("2026-01-02", "West", 150.0, 3),
                ("2026-02-01", "East", 180.0, 4),
                ("2026-02-02", "North", 120.0, 2),
                ("2026-03-01", "East", 220.0, 5),
                ("2026-03-02", "West", 90.0, 1),
                ("2026-04-01", "South", 130.0, 3),
                ("2026-04-02", "North", 170.0, 4),
                ("2026-05-01", "South", 210.0, 5),
                ("2026-05-02", "East", 190.0, 4),
                ("2026-06-01", "West", 160.0, 3),
                ("2026-06-02", "North", 200.0, 4),
            ],
        )
        connection.commit()
    finally:
        connection.close()
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "dataset_id": "test_sales",
                        "name": "Test Sales",
                        "description": "Integration-test dataset",
                        "driver": "sqlite",
                        "database": database.name,
                        "allowed_tables": ["sales"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog = DatasetCatalog(catalog_path)
    store = JsonRunStore(tmp_path / "runs")
    return (
        catalog,
        store,
        DataPilotWorkflow(
            catalog,
            store,
            planner=FakePlanner(),
            sql_agent=FakeSqlAgent(),
            retriever=FakeRetriever(),
        ),
    )
