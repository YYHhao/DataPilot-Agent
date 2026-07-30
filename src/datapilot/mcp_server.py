from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from datapilot.catalog import DatasetCatalog
from datapilot.config import settings
from datapilot.datasources import DataSourceFactory
from datapilot.retrieval import SemanticRetriever


class DataPilotMcpService:
    """Governed operations exposed through MCP."""

    def __init__(
        self,
        catalog: DatasetCatalog | None = None,
        retriever: SemanticRetriever | None = None,
    ) -> None:
        self.catalog = catalog or DatasetCatalog(settings.catalog_path)
        self.sources = DataSourceFactory(self.catalog.path.parent)
        self.retriever = retriever or SemanticRetriever()

    def list_datasets(self) -> str:
        return json.dumps(
            [
                {
                    "dataset_id": item.dataset_id,
                    "name": item.name,
                    "description": item.description,
                    "driver": item.driver,
                    "allowed_tables": item.allowed_tables,
                }
                for item in self.catalog.list()
            ],
            ensure_ascii=False,
        )

    def get_schema(self, dataset_id: str) -> str:
        profile = self.sources.create(self.catalog.get(dataset_id)).inspect_schema()
        return profile.model_dump_json()

    def retrieve_business_context(self, dataset_id: str, question: str) -> str:
        profile = self.sources.create(self.catalog.get(dataset_id)).inspect_schema()
        matches = self.retriever.retrieve(question, profile)
        return json.dumps(
            [item.model_dump() for item in matches],
            ensure_ascii=False,
        )

    def execute_readonly_sql(self, dataset_id: str, sql: str) -> str:
        result = self.sources.create(self.catalog.get(dataset_id)).execute(sql)
        return json.dumps(result, ensure_ascii=False, default=str)


mcp = FastMCP("DataPilot")
service = DataPilotMcpService()


@mcp.tool()
def list_datasets() -> str:
    """List governed datasets without exposing database credentials."""
    return service.list_datasets()


@mcp.tool()
def get_schema(dataset_id: str) -> str:
    """Inspect the allow-listed schema for a governed dataset."""
    return service.get_schema(dataset_id)


@mcp.tool()
def retrieve_business_context(dataset_id: str, question: str) -> str:
    """Retrieve governed metric definitions and business rules for a question."""
    return service.retrieve_business_context(dataset_id, question)


@mcp.tool()
def execute_readonly_sql(dataset_id: str, sql: str) -> str:
    """Execute one validated read-only query against an allow-listed dataset."""
    return service.execute_readonly_sql(dataset_id, sql)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
