"""LandingAI ADE wrapper — the ONLY file that knows which ADE SDK we use.

We currently target the `agentic-doc` library (stable, well-documented). LandingAI now
recommends the newer `landingai-ade` library for new projects; because every ADE call in
the whole system goes through this wrapper, migrating later is a one-file change. Do not
import agentic_doc anywhere else.

Two operations matter to us:
  * parse_document  -> Phase 2: full parse to markdown + grounded chunks (for RAG + viewer)
  * extract_fields  -> Phase 3: schema-driven field extraction (our investigation schemas)
"""
from __future__ import annotations

from typing import Any, Type, Union

from pydantic import BaseModel

from .config import get_settings

Source = Union[str, bytes]  # local path, URL, or raw bytes (e.g. an uploaded file)


def _ensure_key() -> None:
    # get_settings() bridges LANDINGAI_API_KEY -> VISION_AGENT_API_KEY that the SDK reads.
    get_settings()


def _grounding_to_dict(g: Any) -> dict:
    """Normalise a grounding object into a plain dict.

    NOTE: confirm the exact attribute names against a live ADE response when you have a
    key — the SDK exposes a bounding box and page index per grounding, but field names
    have shifted across versions. The getattr fallbacks keep us from crashing meanwhile.
    """
    box = getattr(g, "box", None) or getattr(g, "bbox", None)
    bbox: list[float] = []
    if box is not None:
        if isinstance(box, (list, tuple)):
            bbox = list(box)
        else:  # object with .l/.t/.r/.b or .x1.. style
            for a, b in (("l", "t"), ("x1", "y1")):
                if hasattr(box, a):
                    bbox = [getattr(box, a), getattr(box, b),
                            getattr(box, "r", getattr(box, "x2", 0)),
                            getattr(box, "b", getattr(box, "y2", 0))]
                    break
    return {"page": getattr(g, "page", getattr(g, "page_index", None)), "bbox": bbox}


def parse_document(source: Source) -> dict:
    """Phase 2. Returns markdown, grounded chunks, and page_count."""
    _ensure_key()
    from agentic_doc.parse import parse

    result = parse(source)[0]
    chunks: list[dict] = []
    max_page = 0
    for c in result.chunks:
        groundings = [_grounding_to_dict(g) for g in (getattr(c, "grounding", None) or [])]
        for g in groundings:
            if isinstance(g.get("page"), int):
                max_page = max(max_page, g["page"] + 1)
        chunks.append(
            {
                "chunk_id": getattr(c, "chunk_id", None),
                "type": str(getattr(c, "chunk_type", "text")),
                "text": getattr(c, "text", "") or "",
                "grounding": groundings,
            }
        )
    return {"markdown": result.markdown, "chunks": chunks, "page_count": max_page or 1}


def extract_fields(source: Source, model: Type[BaseModel]) -> dict:
    """Phase 3. Schema-driven extraction. `model` is one of our investigation schemas.

    Returns the extracted fields plus per-field confidence from ADE. We keep both: the
    confidence drives which findings get auto-flagged for human review (Phase 5).
    """
    _ensure_key()
    from agentic_doc.parse import parse

    result = parse(source, extraction_model=model)[0]
    fields = result.extraction.model_dump() if getattr(result, "extraction", None) else {}

    confidence: dict[str, float] = {}
    meta = getattr(result, "extraction_metadata", None)
    if meta:
        for field_name in fields:
            fm = getattr(meta, field_name, None)
            if fm is not None and hasattr(fm, "confidence"):
                confidence[field_name] = fm.confidence
    return {"fields": fields, "confidence": confidence}


def parse_and_extract(source: Source, model: Type[BaseModel]) -> dict:
    """Phase 2 + 3 in a SINGLE ADE call (cheaper than calling parse twice).

    `parse(..., extraction_model=...)` returns the full parse (markdown + grounded chunks)
    AND the schema extraction together. Returns one dict with everything downstream needs.
    """
    _ensure_key()
    from agentic_doc.parse import parse

    result = parse(source, extraction_model=model)[0]

    chunks: list[dict] = []
    max_page = 0
    for c in result.chunks:
        groundings = [_grounding_to_dict(g) for g in (getattr(c, "grounding", None) or [])]
        for g in groundings:
            if isinstance(g.get("page"), int):
                max_page = max(max_page, g["page"] + 1)
        chunks.append(
            {
                "chunk_id": getattr(c, "chunk_id", None),
                "type": str(getattr(c, "chunk_type", "text")),
                "text": getattr(c, "text", "") or "",
                "grounding": groundings,
            }
        )

    fields = result.extraction.model_dump() if getattr(result, "extraction", None) else {}
    confidence: dict[str, float] = {}
    meta = getattr(result, "extraction_metadata", None)
    if meta:
        for field_name in fields:
            fm = getattr(meta, field_name, None)
            if fm is not None and hasattr(fm, "confidence"):
                confidence[field_name] = fm.confidence

    return {
        "markdown": result.markdown,
        "chunks": chunks,
        "page_count": max_page or 1,
        "fields": fields,
        "confidence": confidence,
    }
