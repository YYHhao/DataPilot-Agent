from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DATAPILOT_", extra="ignore")

    model_name: str = "gpt-4.1-mini"
    model_base_url: str | None = None
    model_temperature: float = 0
    sql_max_retries: int = 2
    execution_timeout_seconds: int = 20
    max_result_rows: int = 1_000
    catalog_path: Path = Path("data/catalog.json")
    run_dir: Path = Path("data/runs")


settings = Settings()
