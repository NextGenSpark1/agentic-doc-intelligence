"""LandingAI ADE wrapper — migrated from agentic-doc to landingai-ade (v1.x).

MIGRATION SUMMARY
  Old library : agentic-doc  (import: agentic_doc.parse.parse)
  New library : landingai-ade (import: landingai_ade.LandingAIADE — class-based client)

API DIFFERENCES
  - parse() and extract() are now SEPARATE methods on the client class.
  - parse() requires an explicit model="dpt-2-latest" parameter.
  - extract() takes markdown text (output of parse) + a JSON schema dict; it does NOT
    accept a Pydantic class directly — use pydantic_to_json_schema() from landingai_ade.lib.
  - extract() does NOT document per-field confidence scores. The confidence dict returned by
    extract_fields() and parse_and_extract() will be empty until confirmed otherwise.
  - parse() accepts Path or URL; raw bytes must be written to a temp file first.

ENV VAR
  Still VISION_AGENT_API_KEY — no change to config.py needed.

UNCONFIRMED (verify with a live test call before relying on these):
  - Exact chunk attribute names for grounding (bbox vs box vs grounding object).
    The defensive getattr() patterns are kept throughout until live data confirms.
  - Whether extract() accepts a markdown string directly (rather than a file Path).
    Currently piped through a NamedTemporaryFile to be safe.
  - Whether the client constructor reads VISION_AGENT_API_KEY automatically or requires
    apikey=os.environ["VISION_AGENT_API_KEY"] explicitly. The code passes it explicitly.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Type, Union

from pydantic import BaseModel

from .config import get_settings

Source = Union[str, bytes, Path]  # local path, URL, or raw bytes


def _get_client():
    """Return a configured LandingAIADE client. Fails fast if the key is missing."""
    get_settings()  # bridges LANDINGAI_API_KEY -> VISION_AGENT_API_KEY in os.environ
    from landingai_ade import LandingAIADE
    key = os.environ.get("VISION_AGENT_API_KEY", "")
    if not key:
        raise RuntimeError(
            "VISION_AGENT_API_KEY is not set. Add LANDINGAI_API_KEY to .env."
        )
    return LandingAIADE(apikey=key)


def _source_to_path(source: Source) -> tuple[Path, bool]:
    """Normalise source to a Path. Returns (path, is_temp) — caller must clean up if temp."""
    if isinstance(source, Path):
        return source, False
    if isinstance(source, str):
        if source.startswith(("http://", "https://")):
            # URL — pass directly (landingai-ade handles remote URLs)
            return Path(source), False  # will not be used as a path; see callers
        return Path(source), False
    # bytes — write to a named temp file
    suffix = ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(source)
    tmp.flush()
    tmp.close()
    return Path(tmp.name), True


def _grounding_to_dict(chunk: Any) -> dict:
    """Extract grounding info from a chunk object into a plain dict.

    landingai-ade v1.x exposes bbox and page directly on the chunk. The old
    agentic-doc library nested them under a grounding sub-object. We try both
    layouts so the code survives either.
    """
    # Direct attributes (new layout)
    bbox = getattr(chunk, "bbox", None)
    page = getattr(chunk, "page", None)

    # Nested grounding object (old layout / fallback)
    if bbox is None:
        g = getattr(chunk, "grounding", None)
        if g:
            g0 = g[0] if isinstance(g, (list, tuple)) and g else g
            page = page if page is not None else getattr(g0, "page", getattr(g0, "page_index", None))
            box = getattr(g0, "bbox", None) or getattr(g0, "box", None)
            if box is not None:
                bbox = list(box) if isinstance(box, (list, tuple)) else [
                    getattr(box, "l", getattr(box, "x1", 0)),
                    getattr(box, "t", getattr(box, "y1", 0)),
                    getattr(box, "r", getattr(box, "x2", 0)),
                    getattr(box, "b", getattr(box, "y2", 0)),
                ]

    return {"page": page, "bbox": bbox or []}


def parse_document(source: Source) -> dict:
    """Phase 2. Returns markdown, grounded chunks, and page_count."""
    client = _get_client()
    path, is_temp = _source_to_path(source)
    try:
        result = client.parse(document=path, model="dpt-2-latest")
    finally:
        if is_temp:
            path.unlink(missing_ok=True)

    chunks: list[dict] = []
    max_page = 0
    for c in (result.chunks or []):
        g = _grounding_to_dict(c)
        if isinstance(g.get("page"), int):
            max_page = max(max_page, g["page"] + 1)
        chunks.append({
            "chunk_id": getattr(c, "chunk_id", None),
            "type": str(getattr(c, "chunk_type", getattr(c, "type", "text"))),
            "text": getattr(c, "text", "") or "",
            "grounding": [g],
        })
    return {"markdown": result.markdown, "chunks": chunks, "page_count": max_page or 1}


def extract_fields(source: Source, model: Type[BaseModel]) -> dict:
    """Phase 3. Schema-driven extraction using landingai-ade's two-step approach:
    parse() → markdown, then extract() → fields.

    NOTE: per-field confidence is not documented in landingai-ade v1.x.
    The confidence dict will be empty. Update this when/if confidence is exposed.
    """
    parsed = parse_document(source)
    fields = _extract_from_markdown(parsed["markdown"], model)
    return {"fields": fields, "confidence": {}}


def parse_and_extract(source: Source, model: Type[BaseModel]) -> dict:
    """Phase 2 + 3. Single-source entry point used by the pipeline.

    Runs parse() once, then extract() on the resulting markdown so we don't
    re-fetch the document. More efficient than calling both phases separately.
    """
    parsed = parse_document(source)
    fields = _extract_from_markdown(parsed["markdown"], model)
    return {
        "markdown": parsed["markdown"],
        "chunks": parsed["chunks"],
        "page_count": parsed["page_count"],
        "fields": fields,
        "confidence": {},  # not available in landingai-ade v1.x — see note above
    }


def _extract_from_markdown(markdown: str, model: Type[BaseModel]) -> dict:
    """Run client.extract() against a markdown string.

    extract() expects a file path; we write the markdown to a temp file.
    If a future SDK version accepts a string directly, remove the tempfile dance.
    """
    from landingai_ade.lib import pydantic_to_json_schema
    schema = pydantic_to_json_schema(model)
    client = _get_client()

    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".md", mode="w", encoding="utf-8"
    )
    tmp.write(markdown)
    tmp.flush()
    tmp.close()
    md_path = Path(tmp.name)
    try:
        result = client.extract(schema=schema, markdown=md_path)
    finally:
        md_path.unlink(missing_ok=True)

    # result is a Pydantic model; convert to plain dict
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return vars(result) if not isinstance(result, dict) else result
