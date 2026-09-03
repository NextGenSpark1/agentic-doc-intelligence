"""Shared case-reasoning helper for the LLM-augmented stages.

`resolve_entities`, `build_relationships`, `reconstruct_timeline`, and `detect_anomalies`
each run their deterministic rule pass first, then call `ask()` for a second pass that reasons
across the whole case. `ask()` never raises — any failure (no key, provider error, bad JSON)
returns None, and the caller just keeps its rule-based results. Callers are responsible for
validating that anything the model returns is grounded in data actually sent to it; nothing
here should be trusted at face value in a forensic pipeline.

Every failure is logged to the case's audit_log (action="case_reasoning_failed") — a silent
"tier=case_reasoning always raises, always falls back" bug (bad model name, exhausted quota,
missing key) previously looked identical to "nothing anomalous to report" from the UI. Logging
is what makes that distinguishable without re-deriving it by hand.
"""
from __future__ import annotations

import json
from typing import Any

from . import llm


def ask(system_prompt: str, payload: dict, case_id: str | None = None,
        tender_id: str | None = None) -> Any | None:
    """Run one grounded reasoning pass. Never raises — see the module docstring.

    Pass `case_id` for an investigation workspace or `tender_id` for a tender one; the failure
    audit is written against whichever is given, so a dead LLM tier is diagnosable from either
    product's audit trail.
    """
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
    except Exception as exc:
        try:
            # `backend.core.db_core`, not `backend.db` — the latter has not existed since the
            # core/apps split, and importing it here raised ImportError out of ask(), breaking
            # the "never raises" contract every LLM-augmented stage depends on for its
            # rule-only fallback. Kept inside the try so audit logging can still never break
            # that fallback.
            from . import db_core

            db_core.write_audit(case_id, "system", "case_reasoning_failed",
                                {"error": str(exc)[:500]}, tender_id=tender_id)
        except Exception:
            pass  # audit logging must never break the graceful rule-only fallback
        return None


def clamp_confidence(value: Any, default: float = 0.6) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def clamp_severity(value: Any, default: str = "medium") -> str:
    v = str(value or "").strip().lower()
    return v if v in ("high", "medium", "low") else default
