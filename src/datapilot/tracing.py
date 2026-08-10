from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from datapilot.models import AgentState


@contextmanager
def trace_node(state: AgentState, node: str) -> Iterator[dict[str, Any]]:
    started = time.perf_counter()
    event: dict[str, Any] = {"node": node, "status": "running"}
    try:
        yield event
        event["status"] = "ok"
    except Exception as exc:
        event["status"] = "error"
        event["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        event["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        state.setdefault("trace", []).append(event)
