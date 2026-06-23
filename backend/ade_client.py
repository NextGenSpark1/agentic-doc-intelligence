"""LandingAI ADE wrapper — migrated from agentic-doc to landingai-ade (v1.x).

API FACTS (verified against venv/Lib/site-packages/landingai_ade/):
  - parse(document=<Path|FileTypes>, model=<str|None>) -> ParseResponse
      ParseResponse.chunks: List[Chunk]
        Chunk.id         str
        Chunk.type       str
        Chunk.markdown   str   (the text; NOT .text)
        Chunk.grounding  ChunkGrounding(.page int, .box ParseGroundingBox)
          ParseGroundingBox.left/top/right/bottom  float
      ParseResponse.markdown  str
  - extract(schema=<json_str>, markdown=<str|FileTypes|None>) -> ExtractResponse
      ExtractResponse.extraction  object   (the extracted key-value pairs as dict)
  - pydantic_to_json_schema(model) -> str  (already JSON-encoded; pass directly to extract())
  - Constructor reads VISION_AGENT_API_KEY automatically; we pass it explicitly for clarity.
  - Per-field confidence is not exposed in v1.x.

ENV VAR
  Still VISION_AGENT_API_KEY — no change to config.py needed.
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
    """Extract grounding from a landingai-ade v1.x Chunk into a plain dict.

    ParseResponse.Chunk.grounding is a ChunkGrounding with:
      .page (int)
      .box  (ParseGroundingBox with .left/.top/.right/.bottom)
    """
    g = getattr(chunk, "grounding", None)
    if g is None:
        return {"page": None, "bbox": []}

    # grounding is a ChunkGrounding object (not a list), but tolerate list layout too
    g0 = g[0] if isinstance(g, (list, tuple)) and g else g
    page = getattr(g0, "page", None)
    box = getattr(g0, "box", None) or getattr(g0, "bbox", None)

    if box is None:
        return {"page": page, "bbox": []}

    if isinstance(box, (list, tuple)):
        bbox = list(box)
    else:
        # ParseGroundingBox uses left/top/right/bottom (not l/t/r/b or x1/y1/x2/y2)
        bbox = [
            getattr(box, "left",   getattr(box, "l", getattr(box, "x1", 0))),
            getattr(box, "top",    getattr(box, "t", getattr(box, "y1", 0))),
            getattr(box, "right",  getattr(box, "r", getattr(box, "x2", 0))),
            getattr(box, "bottom", getattr(box, "b", getattr(box, "y2", 0))),
        ]

    return {"page": page, "bbox": bbox}


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
            "chunk_id": getattr(c, "id", None),           # Chunk.id (not chunk_id)
            "type": str(getattr(c, "type", "text")),
            "text": getattr(c, "markdown", "") or "",     # Chunk.markdown (not text)
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

    extract() accepts a string directly for the markdown parameter.
    Returns only the extracted key-value pairs from ExtractResponse.extraction
    (not the full response including metadata).
    """
    from landingai_ade.lib import pydantic_to_json_schema
    schema = pydantic_to_json_schema(model)
    client = _get_client()

    result = client.extract(schema=schema, markdown=markdown)

    # ExtractResponse.extraction holds the extracted key-value pairs as a dict.
    # model_dump() would return the full structure including metadata — don't use it.
    extraction = getattr(result, "extraction", None)
    if isinstance(extraction, dict):
        return extraction
    if hasattr(extraction, "model_dump"):
        return extraction.model_dump()
    return {}
