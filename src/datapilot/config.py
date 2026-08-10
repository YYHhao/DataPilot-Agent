from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DATAPILOT_", extra="ignore")

    model_name: str = "gpt-4.1-mini"
    model_base_url: str | None = None
    model_temperature: float = 0
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    sql_max_retries: int = 2
    semantic_catalog_path: Path = Path("data/semantic_catalog.json")
    embedding_model: str = "text-embedding-3-small"
    retrieval_top_k: int = 5
    retrieval_vector_weight: float = 0.55
    execution_timeout_seconds: int = 20
    max_result_rows: int = 1_000
    catalog_path: Path = Path("data/catalog.json")
    run_dir: Path = Path("data/runs")


settings = Settings()
