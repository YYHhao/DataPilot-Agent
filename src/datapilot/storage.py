from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock

from datapilot.models import AgentState

RUN_ID = re.compile(r"^[a-f0-9]{32}$")


class JsonRunStore:
    """Atomic local store used by the demo; the interface is replaceable by PostgreSQL."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def save(self, state: AgentState) -> None:
        destination = self._state_path(state["run_id"])
        temporary = destination.with_suffix(".tmp")
        with self._lock:
            temporary.write_text(
                json.dumps(state, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            temporary.replace(destination)

    def save_report(self, run_id: str, report: str) -> Path:
        destination = self._report_path(run_id)
        temporary = destination.with_suffix(".tmp")
        with self._lock:
            temporary.write_text(report, encoding="utf-8")
            temporary.replace(destination)
        return destination

    def load(self, run_id: str) -> AgentState:
        path = self._state_path(run_id)
        if not path.is_file():
            raise KeyError(run_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def report_path(self, run_id: str) -> Path:
        path = self._report_path(run_id)
        if not path.is_file():
            raise KeyError(run_id)
        return path

    def _state_path(self, run_id: str) -> Path:
        self._validate_id(run_id)
        return self.root / f"{run_id}.json"

    def _report_path(self, run_id: str) -> Path:
        self._validate_id(run_id)
        return self.root / f"{run_id}.report.md"

    @staticmethod
    def _validate_id(run_id: str) -> None:
        if not RUN_ID.fullmatch(run_id):
            raise KeyError(run_id)
