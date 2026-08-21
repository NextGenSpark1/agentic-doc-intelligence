"""Document classification engine (core, app-agnostic).

Cheap LLM call on the first slice of parsed text, with a keyword heuristic fallback so the
pipeline still works without an LLM key during early development. The set of document types is
NOT hardcoded here — each product passes its own `known_types` + `heuristics`, so the same
engine classifies fraud documents for Investigation and tender documents for Tendering.
"""
from __future__ import annotations

from . import llm


def heuristic(text: str, heuristics: dict[str, list[str]]) -> str:
    """Best-guess type from keyword hits. `heuristics` maps a type label to trigger keywords."""
    text_lower = text.lower()
    best_type, hit_count = "other", 0
    for doc_type, keywords in heuristics.items():
        hits = sum(1 for k in keywords if k in text_lower)
        if hits > hit_count:
            best_type, hit_count = doc_type, hits
    return best_type


def classify(markdown: str, known_types: list[str], heuristics: dict[str, list[str]]) -> str:
    """Classify a document into one of `known_types`. Falls back to the keyword heuristic when
    the LLM is unavailable or returns an unknown label."""
    snippet = (markdown or "")[:1500]
    if not snippet.strip():
        return "other"
    try:
        answer = llm.complete(
            tier="fast",
            messages=[
                {"role": "system", "content": "Classify the document. Reply with ONE label only, "
                 "from: " + ", ".join(known_types) + ". No other text."},
                {"role": "user", "content": snippet},
            ],
        ).strip().lower()
        return answer if answer in known_types else heuristic(snippet, heuristics)
    except Exception:
        # No LLM key / provider down -> degrade gracefully to heuristic
        return heuristic(snippet, heuristics)
