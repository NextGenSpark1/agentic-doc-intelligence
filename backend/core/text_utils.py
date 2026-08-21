"""Small text helpers shared across product routers (core, dependency-free)."""
from __future__ import annotations

import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s{2,}")

# Common words to ignore when building the chat keyword fallback, so a question doesn't match
# every chunk on filler like "what" or "there".
_STOPWORDS = {
    "what", "when", "where", "which", "whom", "whose", "that", "this", "these", "those",
    "with", "from", "have", "has", "had", "does", "did", "was", "were", "are", "is",
    "the", "and", "for", "you", "your", "about", "into", "over", "them", "they", "there",
    "would", "could", "should", "please", "tell", "show", "give", "find", "list", "any",
}


def strip_html(text: str) -> str:
    """Remove HTML tags left by ADE and collapse whitespace."""
    cleaned = _HTML_TAG_RE.sub(" ", text or "")
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def keyword_or_filter(message: str) -> str | None:
    """Build a PostgREST or-filter matching ANY salient word from the question, used as the
    keyword fallback when vector search is unavailable. Far better than matching the literal
    first 40 chars of the question (which rarely appears verbatim in a document). Returns None
    if the question has no usable words, so the caller can fall back to a substring match."""
    seen: set[str] = set()
    picked: list[str] = []
    for w in re.findall(r"[A-Za-z0-9]{4,}", message or ""):
        wl = w.lower()
        if wl in _STOPWORDS or wl in seen:
            continue
        seen.add(wl)
        picked.append(wl)
        if len(picked) == 6:
            break
    if not picked:
        return None
    return ",".join(f"text.ilike.%{w}%" for w in picked)
