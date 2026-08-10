import json

import pytest

from datapilot.mcp_server import DataPilotMcpService


class EmptyRetriever:
    def retrieve(self, question, profile):
        return []


def test_mcp_service_exposes_governed_schema_and_query(enterprise_runtime):
    catalog, _, _ = enterprise_runtime
    service = DataPilotMcpService(catalog, EmptyRetriever())
    datasets = json.loads(service.list_datasets())
    assert datasets[0]["dataset_id"] == "test_sales"
    assert "database" not in datasets[0]
    schema = json.loads(service.get_schema("test_sales"))
    assert schema["tables"][0]["name"] == "sales"
    output = json.loads(
        service.execute_readonly_sql("test_sales", "SELECT COUNT(*) AS record_count FROM sales")
    )
    assert output["rows"] == [[12]]


def test_mcp_service_rejects_write_sql(enterprise_runtime):
    catalog, _, _ = enterprise_runtime
    service = DataPilotMcpService(catalog, EmptyRetriever())
    with pytest.raises(ValueError):
        service.execute_readonly_sql("test_sales", "DELETE FROM sales")
