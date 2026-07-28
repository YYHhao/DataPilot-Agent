from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from datapilot.config import settings


T = TypeVar("T", bound=BaseModel)


def structured_model(schema: type[T]):
    """Create the configured OpenAI-compatible model with structured output."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("Install dependencies from requirements.txt") from exc

    options = {
        "model": settings.model_name,
        "temperature": settings.model_temperature,
    }
    if settings.model_base_url:
        options["base_url"] = settings.model_base_url
    return ChatOpenAI(**options).with_structured_output(schema)
