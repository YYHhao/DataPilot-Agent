from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DATAPILOT_", extra="ignore")

    model_provider: str = "mock"
    model_name: str = "gpt-4.1-mini"
    execution_timeout_seconds: int = 20
    max_result_rows: int = 1_000
    catalog_path: Path = Path("data/catalog.json")
    run_dir: Path = Path("data/runs")


settings = Settings()
