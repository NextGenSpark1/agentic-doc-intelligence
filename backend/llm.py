"""LLM access via LiteLLM — the ONLY file that talks to a model provider directly.

Routing rule lives here, not in the agents: callers ask for "reasoning" or "fast" and
this module maps that to a concrete model string (configurable, swappable, on-prem-ready).
"""
from __future__ import annotations

from typing import Any

from .config import get_settings


def complete(messages: list[dict], tier: str = "reasoning", **kwargs: Any) -> str:
    from litellm import completion

    s = get_settings()
    model = s.llm_fast_model if tier == "fast" else s.llm_reasoning_model
    resp = completion(model=model, messages=messages, **kwargs)
    return resp["choices"][0]["message"]["content"]


def embed(texts: list[str]) -> list[list[float]]:
    from litellm import embedding

    s = get_settings()
    resp = embedding(model=s.llm_embedding_model, input=texts, dimensions=768)
    # LiteLLM normalises to OpenAI shape regardless of provider
    return [d["embedding"] for d in resp["data"]]
