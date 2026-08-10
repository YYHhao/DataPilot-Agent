from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from datapilot.models import DatasetDefinition


class DatasetCatalog:
    """Loads an allow-listed catalog; requests can reference IDs but never supply DSNs."""

    def __init__(self, path: Path):
        self.path = path
        self._datasets = self._load(path)

    @staticmethod
    def _load(path: Path) -> dict[str, DatasetDefinition]:
        if not path.is_file():
            raise FileNotFoundError(f"未找到数据集目录：{path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        definitions = TypeAdapter(list[DatasetDefinition]).validate_python(payload["datasets"])
        indexed = {item.dataset_id: item for item in definitions}
        if len(indexed) != len(definitions):
            raise ValueError("数据集 ID 必须唯一")
        return indexed

    def get(self, dataset_id: str) -> DatasetDefinition:
        try:
            return self._datasets[dataset_id]
        except KeyError as exc:
            raise KeyError(f"未知数据集：{dataset_id}") from exc

    def list(self) -> list[DatasetDefinition]:
        return sorted(self._datasets.values(), key=lambda item: item.dataset_id)
