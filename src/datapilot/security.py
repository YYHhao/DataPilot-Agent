from __future__ import annotations

import re


FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|"
    r"reindex|grant|revoke|truncate|copy|call|execute)\b",
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
        raise ValueError("SQL query cannot be empty")
    if compact.count(";") > int(compact.endswith(";")):
        raise ValueError("Multiple SQL statements are forbidden")
    if not re.match(r"^(select|with)\b", compact, re.IGNORECASE):
        raise ValueError("Only SELECT or WITH queries are allowed")
    if FORBIDDEN_SQL.search(compact):
        raise ValueError("SQL contains a forbidden operation")
    if "--" in compact or "/*" in compact or "*/" in compact:
        raise ValueError("SQL comments are forbidden")
    if FORBIDDEN_FUNCTIONS.search(compact):
        raise ValueError("SQL contains a forbidden function")
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
        raise ValueError(f"SQL references unauthorized tables: {sorted(unauthorized)}")
