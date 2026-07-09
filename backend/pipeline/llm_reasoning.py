"""Shared Gemini case-reasoning helper for the LLM-augmented stages.

`resolve_entities`, `build_relationships`, `reconstruct_timeline`, and `detect_anomalies`
each run their deterministic rule pass first, then call `ask()` for a second pass that reasons
across the whole case. `ask()` never raises — any failure (no key, provider error, bad JSON)
returns None, and the caller just keeps its rule-based results. Callers are responsible for
validating that anything the model returns is grounded in data actually sent to it; nothing
here should be trusted at face value in a forensic pipeline.
"""
from __future__ import annotations

import json
from typing import Any

from .. import llm


def ask(system_prompt: str, payload: dict) -> Any | None:
    try:
        raw = llm.complete(
            tier="case_reasoning",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, default=str)},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(raw)
    except Exception:
        return None


def clamp_confidence(value: Any, default: float = 0.6) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def clamp_severity(value: Any, default: str = "medium") -> str:
    v = str(value or "").strip().lower()
    return v if v in ("high", "medium", "low") else default
