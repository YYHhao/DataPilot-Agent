from __future__ import annotations

import re

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|"
    r"reindex|grant|revoke|truncate|copy|call|execute)\b",
    re.IGNORECASE,
)

RELATIVE_TIME_SQL = re.compile(
    r"\b(current_date|current_timestamp|localtimestamp|now\s*\()", re.IGNORECASE
)
RELATIVE_TIME_REQUEST = re.compile(
    r"最近|过去|近\s*\d+|当前|今天|本月|今年|去年|"
    r"\b(last|past|recent|current|today|yesterday|this\s+(month|year))\b",
    re.IGNORECASE,
)
FORBIDDEN_FUNCTIONS = re.compile(
    r"\b(load_extension|readfile|writefile|pg_sleep|pg_read_file|pg_ls_dir|"
    r"lo_import|lo_export|dblink|current_setting)\s*\(",
    re.IGNORECASE,
)


def validate_readonly_sql(sql: str, allowed_tables: list[str]) -> None:
    compact = sql.strip()
    if not compact:
        raise ValueError("SQL 查询不能为空")
    if compact.count(";") > int(compact.endswith(";")):
        raise ValueError("禁止执行多条 SQL 语句")
    if not re.match(r"^(select|with)\b", compact, re.IGNORECASE):
        raise ValueError("只允许执行 SELECT 或 WITH 查询")
    if FORBIDDEN_SQL.search(compact):
        raise ValueError("SQL 包含被禁止的操作")
    if "--" in compact or "/*" in compact or "*/" in compact:
        raise ValueError("SQL 中禁止使用注释")
    if FORBIDDEN_FUNCTIONS.search(compact):
        raise ValueError("SQL 包含被禁止的函数")
    referenced = {
        match.group(1).strip('"').lower()
        for match in re.finditer(
            r"\b(?:from|join)\s+([A-Za-z_][\w]*|\"[^\"]+\")", compact, re.IGNORECASE
        )
    }
    cte_names = {
        match.group(1).lower()
        for match in re.finditer(
            r"(?:\bwith\b|,)\s*([A-Za-z_][\w]*)\s+as\s*\(",
            compact,
            re.IGNORECASE,
        )
    }
    allowed = {table.lower() for table in allowed_tables}
    unauthorized = referenced - allowed - cte_names
    if unauthorized:
        raise ValueError(f"SQL 引用了未授权的数据表：{sorted(unauthorized)}")


def validate_question_scope(sql: str, question: str) -> None:
    """Reject model-invented relative date windows absent from the user request."""
    if RELATIVE_TIME_SQL.search(sql) and not RELATIVE_TIME_REQUEST.search(question):
        raise ValueError("SQL 使用了相对当前时间的筛选条件，但用户没有指定该时间范围")
