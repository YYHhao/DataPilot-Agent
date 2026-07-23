from __future__ import annotations

import os
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from datapilot.config import settings
from datapilot.models import ColumnSchema, DatasetDefinition, SchemaProfile, TableSchema
from datapilot.security import validate_readonly_sql


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


class DataSource(ABC):
    def __init__(self, definition: DatasetDefinition):
        self.definition = definition

    @abstractmethod
    def inspect_schema(self) -> SchemaProfile: ...

    @abstractmethod
    def execute(self, sql: str) -> dict[str, Any]: ...


class SQLiteDataSource(DataSource):
    def __init__(self, definition: DatasetDefinition, catalog_dir: Path):
        super().__init__(definition)
        if not definition.database:
            raise ValueError(f"SQLite dataset {definition.dataset_id} requires 'database'")
        path = Path(definition.database)
        self.path = path if path.is_absolute() else (catalog_dir / path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"SQLite database not found: {self.path}")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)

    def inspect_schema(self) -> SchemaProfile:
        tables: list[TableSchema] = []
        connection = self._connect()
        try:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            for table in self.definition.allowed_tables:
                if table not in existing:
                    raise ValueError(f"Allowed table does not exist: {table}")
                columns = [
                    ColumnSchema(
                        name=row[1],
                        data_type=row[2] or "TEXT",
                        nullable=not bool(row[3]),
                        primary_key=bool(row[5]),
                    )
                    for row in connection.execute(
                        f"PRAGMA table_info({quote_identifier(table)})"
                    ).fetchall()
                ]
                tables.append(TableSchema(name=table, columns=columns))
        finally:
            connection.close()
        return SchemaProfile(
            dataset_id=self.definition.dataset_id,
            dataset_name=self.definition.name,
            description=self.definition.description,
            driver=self.definition.driver,
            tables=tables,
        )

    def execute(self, sql: str) -> dict[str, Any]:
        validate_readonly_sql(sql, self.definition.allowed_tables)
        deadline = time.monotonic() + settings.execution_timeout_seconds
        connection = self._connect()
        try:
            connection.set_authorizer(_sqlite_readonly_authorizer)
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
            bounded = f"SELECT * FROM ({sql.rstrip(';')}) AS _datapilot_result LIMIT ?"
            cursor = connection.execute(bounded, (settings.max_result_rows + 1,))
            rows = cursor.fetchall()
            truncated = len(rows) > settings.max_result_rows
            rows = rows[: settings.max_result_rows]
            return {
                "columns": [item[0] for item in cursor.description or []],
                "rows": [_normalize_row(row) for row in rows],
                "row_count": len(rows),
                "truncated": truncated,
            }
        finally:
            connection.close()


class PostgresDataSource(DataSource):
    def __init__(self, definition: DatasetDefinition):
        super().__init__(definition)
        if not definition.connection_env:
            raise ValueError(
                f"PostgreSQL dataset {definition.dataset_id} requires 'connection_env'"
            )
        self.dsn = os.getenv(definition.connection_env)
        if not self.dsn:
            raise RuntimeError(
                f"Required database environment variable is missing: {definition.connection_env}"
            )

    @staticmethod
    def _driver():
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install the 'postgres' extra for PostgreSQL datasets") from exc
        return psycopg

    def inspect_schema(self) -> SchemaProfile:
        psycopg = self._driver()
        tables: list[TableSchema] = []
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                for table in self.definition.allowed_tables:
                    cursor.execute(
                        """
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s
                        ORDER BY ordinal_position
                        """,
                        (table,),
                    )
                    columns = [
                        ColumnSchema(name=row[0], data_type=row[1], nullable=row[2] == "YES")
                        for row in cursor.fetchall()
                    ]
                    if not columns:
                        raise ValueError(f"Allowed table does not exist: {table}")
                    tables.append(TableSchema(name=table, columns=columns))
        return SchemaProfile(
            dataset_id=self.definition.dataset_id,
            dataset_name=self.definition.name,
            description=self.definition.description,
            driver=self.definition.driver,
            tables=tables,
        )

    def execute(self, sql: str) -> dict[str, Any]:
        validate_readonly_sql(sql, self.definition.allowed_tables)
        psycopg = self._driver()
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    f"SET LOCAL statement_timeout = {settings.execution_timeout_seconds * 1000}"
                )
                bounded = (
                    f"SELECT * FROM ({sql.rstrip(';')}) AS _datapilot_result "
                    f"LIMIT {settings.max_result_rows + 1}"
                )
                cursor.execute(bounded)
                rows = cursor.fetchall()
                truncated = len(rows) > settings.max_result_rows
                rows = rows[: settings.max_result_rows]
                return {
                    "columns": [item.name for item in cursor.description or []],
                    "rows": [_normalize_row(row) for row in rows],
                    "row_count": len(rows),
                    "truncated": truncated,
                }


class DataSourceFactory:
    def __init__(self, catalog_dir: Path):
        self.catalog_dir = catalog_dir

    def create(self, definition: DatasetDefinition) -> DataSource:
        if definition.driver == "sqlite":
            return SQLiteDataSource(definition, self.catalog_dir)
        if definition.driver == "postgresql":
            return PostgresDataSource(definition)
        raise ValueError(f"Unsupported data source driver: {definition.driver}")


def _sqlite_readonly_authorizer(
    action: int,
    _arg1: str | None,
    arg2: str | None,
    _database: str | None,
    _trigger: str | None,
) -> int:
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in {
        "load_extension",
        "readfile",
        "writefile",
    }:
        return sqlite3.SQLITE_DENY
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


def _normalize_row(row: tuple[Any, ...]) -> list[Any]:
    normalized = []
    for value in row:
        if hasattr(value, "isoformat"):
            normalized.append(value.isoformat())
        elif isinstance(value, bytes):
            normalized.append(f"<{len(value)} bytes>")
        else:
            normalized.append(value)
    return normalized
