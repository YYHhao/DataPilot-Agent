from __future__ import annotations

import sqlite3
from pathlib import Path


ROWS = [
    ("2026-01-05", "North", "Hardware", 1250.0, 5, 0.05),
    ("2026-01-12", "East", "Software", 980.0, 2, 0.00),
    ("2026-02-03", "South", "Hardware", 1430.0, 6, 0.10),
    ("2026-02-17", "East", "Services", 2100.0, 3, 0.00),
    ("2026-03-01", "West", "Software", 760.0, 2, 0.05),
    ("2026-03-14", "North", "Services", 1850.0, 4, 0.00),
    ("2026-04-02", "East", "Hardware", 1670.0, 7, 0.08),
    ("2026-04-18", "South", "Software", 890.0, 3, 0.02),
    ("2026-05-06", "West", "Services", 2320.0, 5, 0.00),
    ("2026-05-21", "North", "Hardware", 1540.0, 6, 0.07),
    ("2026-06-09", "East", "Software", 1120.0, 4, 0.03),
    ("2026-06-25", "South", "Services", 1980.0, 4, 0.00),
]


def seed(path: Path | None = None) -> Path:
    destination = path or Path(__file__).parents[1] / "data" / "demo.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(destination)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY,
                order_date TEXT NOT NULL,
                region TEXT NOT NULL,
                category TEXT NOT NULL,
                revenue REAL NOT NULL,
                quantity INTEGER NOT NULL,
                discount REAL NOT NULL
            )
            """
        )
        connection.execute("DELETE FROM sales")
        connection.executemany(
            """
            INSERT INTO sales
                (order_date, region, category, revenue, quantity, discount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ROWS,
        )
        connection.commit()
    finally:
        connection.close()
    return destination


if __name__ == "__main__":
    print(f"Seeded {seed()}")
