from pathlib import Path

from datapilot.models import ColumnSchema, SchemaProfile, TableSchema
from datapilot.retrieval import SemanticRetriever


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[float("revenue" in text.lower()), float("region" in text.lower())] for text in texts]

    def embed_query(self, text):
        return [float("revenue" in text.lower()), float("region" in text.lower())]


def test_hybrid_retrieval_returns_governed_metric():
    profile = SchemaProfile(
        dataset_id="demo_sales",
        dataset_name="Demo",
        description="",
        driver="sqlite",
        tables=[
            TableSchema(
                name="sales",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER"),
                    ColumnSchema(name="revenue", data_type="REAL"),
                    ColumnSchema(name="region", data_type="TEXT"),
                    ColumnSchema(name="order_date", data_type="TEXT"),
                ],
            )
        ],
    )
    path = Path(__file__).parents[1] / "data" / "semantic_catalog.json"
    results = SemanticRetriever(path, FakeEmbeddings()).retrieve(
        "total revenue by region", profile, top_k=3
    )
    assert results
    assert results[0].document.id == "metric.revenue"
    assert all(result.document.table == "sales" for result in results)
    assert all(result.score >= 0 for result in results)


def test_retrieval_excludes_documents_with_unavailable_columns():
    profile = SchemaProfile(
        dataset_id="minimal",
        dataset_name="Minimal",
        description="",
        driver="sqlite",
        tables=[
            TableSchema(
                name="sales",
                columns=[ColumnSchema(name="region", data_type="TEXT")],
            )
        ],
    )
    path = Path(__file__).parents[1] / "data" / "semantic_catalog.json"
    results = SemanticRetriever(path, FakeEmbeddings()).retrieve("revenue", profile)
    assert all("revenue" not in result.document.columns for result in results)
