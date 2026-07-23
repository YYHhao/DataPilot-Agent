from __future__ import annotations

from datapilot.datasources import DataSource
from datapilot.models import SchemaProfile


class SchemaAgent:
    """Inspects only catalog-approved tables and exposes no sample records."""

    def run(self, source: DataSource) -> SchemaProfile:
        return source.inspect_schema()
