"""LLM access via LiteLLM — the ONLY file that talks to a model provider directly.

Routing rule lives here, not in the agents: callers ask for "reasoning" or "fast" and
this module maps that to a concrete model string (configurable, swappable, on-prem-ready).
"""
from __future__ import annotations

import time
from typing import Any

from .config import get_settings

# Groq closes idle HTTP/2 connections on Railway after ~30s; large prompts (80k-char batches
# for requirements extraction) take longer than that, causing "Server disconnected" errors.
# 120s covers even the heaviest requirement-extraction batch with room to spare.
_LLM_TIMEOUT = 120
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BACKOFF = (10, 20)  # seconds between attempt 0→1 and attempt 1→2


def complete(messages: list[dict], tier: str = "reasoning", **kwargs: Any) -> str:
    from litellm import completion

    s = get_settings()
    models = {
        "fast": s.llm_fast_model,
        "reasoning": s.llm_reasoning_model,
        "case_reasoning": s.llm_case_reasoning_model,
    }
    model = models.get(tier, s.llm_reasoning_model)
    kwargs.setdefault("timeout", _LLM_TIMEOUT)

    for attempt in range(_LLM_MAX_RETRIES):
        try:
            resp = completion(model=model, messages=messages, **kwargs)
            return resp["choices"][0]["message"]["content"]
        except Exception as exc:
            if attempt == _LLM_MAX_RETRIES - 1 or not _is_retryable(exc):
                raise
            time.sleep(_LLM_RETRY_BACKOFF[attempt])
    raise RuntimeError("unreachable")


def _is_retryable(exc: Exception) -> bool:
    """True for transient network/server errors worth retrying; False for auth/bad-request."""
    try:
        from litellm import RateLimitError, APIConnectionError, ServiceUnavailableError
        if isinstance(exc, (RateLimitError, APIConnectionError, ServiceUnavailableError)):
            return True
    except ImportError:
        pass
    error_lower = str(exc).lower()
    return any(term in error_lower for term in (
        "server disconnected", "connection reset", "remote protocol",
        "rate limit", "503", "502", "529",
    ))


def embed(texts: list[str]) -> list[list[float]]:
    from litellm import embedding

    s = get_settings()
    # dimensions=1536 matches the vector(1536) DB column. LiteLLM maps this to
    # output_dimensionality for Gemini (supported values: 256, 768, 1536, 3072).
    resp = embedding(model=s.llm_embedding_model, input=texts, dimensions=1536)
    # LiteLLM normalises to OpenAI shape regardless of provider
    return [d["embedding"] for d in resp["data"]]
