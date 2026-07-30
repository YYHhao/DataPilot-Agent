from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


class UsageCollector(BaseCallbackHandler):
    """Collect token usage exposed by OpenAI-compatible model responses."""

    def __init__(self) -> None:
        self.usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        for generations in getattr(response, "generations", []):
            for generation in generations:
                message = getattr(generation, "message", None)
                metadata = getattr(message, "usage_metadata", None) or {}
                self.usage["input_tokens"] += int(metadata.get("input_tokens", 0))
                self.usage["output_tokens"] += int(metadata.get("output_tokens", 0))
                self.usage["total_tokens"] += int(metadata.get("total_tokens", 0))


def invoke_observed(model, prompt: str):
    collector = UsageCollector()
    try:
        result = model.invoke(prompt, config={"callbacks": [collector]})
    except TypeError:
        result = model.invoke(prompt)
    return result, collector.usage
