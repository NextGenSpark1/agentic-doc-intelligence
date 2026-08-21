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
import uuid
from pathlib import Path
from typing import Any, Type, Union, get_args, get_origin

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


# ---------------------------------------------------------------------------
# Mock helpers — used when MOCK_ADE=true in .env
# ---------------------------------------------------------------------------

_MOCK_MARKDOWN = """\
# INVOICE

**Vendor:** Apex Consulting Sdn Bhd
**Invoice No:** INV-2026-00841
**Date:** 2026-03-15
**PO Number:** PO-2026-1102

## Description of Services

Professional advisory services rendered for Q1 2026 in relation to the procurement
of IT infrastructure for the Ministry of Finance digital transformation programme.

| Item | Qty | Unit Price (MYR) | Total (MYR) |
|------|-----|-----------------|-------------|
| Advisory — Strategic Planning | 5 days | 2,000.00 | 10,000.00 |
| Advisory — Vendor Evaluation  | 1 day  | 2,500.00 |  2,500.00 |

**Subtotal:** MYR 12,500.00
**GST (0%):** MYR 0.00
**Total Due:** MYR 12,500.00

## Payment Instructions

Please remit to: Bank Islam Malaysia — Account No. 1234567890
Approved by: Ahmad Zulkifli bin Hassan (Director of Procurement)

---

*This invoice is generated for testing purposes under MOCK_ADE=true.*
"""

_FIELD_STUBS: dict[str, Any] = {
    "vendor_name":        "Apex Consulting Sdn Bhd",
    "amount":             12500.0,
    "currency":           "MYR",
    "bank_account":       "1234567890",
    "approval_officer":   "Ahmad Zulkifli bin Hassan",
    "invoice_number":     "INV-2026-00841",
    "payment_date":       "2026-03-15",
    "po_number":          "PO-2026-1102",
    "tender_id":          "TENDER-2026-0042",
    "awarded_vendor":     "Apex Consulting Sdn Bhd",
    "competing_vendors":  ["Beta Solutions Bhd", "Gamma Tech Sdn Bhd"],
    "approval_timeline":  "Submitted 2026-01-10; Approved 2026-01-28",
    "budget_amount":      150000.0,
    "contract_value":     138500.0,
    "person_names":       ["Ahmad Zulkifli bin Hassan", "Lim Wei Ming"],
    "related_companies":  ["Apex Consulting Sdn Bhd", "Synergy Ventures Bhd"],
    "shareholders":       ["Ahmad Zulkifli bin Hassan (40%)"],
    "directors":          ["Lim Wei Ming"],
    "addresses":          ["No. 12, Jalan Semarak, 50100 Kuala Lumpur"],
    "phone_numbers":      ["+60 3-2162 0001"],
    "dates":              ["2026-03-15", "2026-03-20"],
    "participants":       ["Ahmad Zulkifli bin Hassan", "Lim Wei Ming"],
    "intent_indicators":  ["we need to close this by end of month"],
    "suspicious_keywords": ["off the books", "no receipt needed"],
    "commitments":        ["payment by 15 April 2026"],
    "payment_references": ["RM 12,500 via TT"],
}


def _unwrap_optional(annotation: Any) -> Any:
    """Strip Optional[X] -> X. Leaves everything else unchanged."""
    if get_origin(annotation) is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return args[0] if args else str
    return annotation


def _mock_fields(model: Type[BaseModel]) -> dict:
    """Generate plausible fake values for every field in a Pydantic schema."""
    result: dict = {}
    for name, field_info in model.model_fields.items():
        annotation = _unwrap_optional(field_info.annotation)
        origin = get_origin(annotation)

        if name in _FIELD_STUBS:
            result[name] = _FIELD_STUBS[name]
        elif origin is list or annotation is list:
            result[name] = ["mock item 1", "mock item 2"]
        elif annotation is float or annotation is int:
            result[name] = 1000.0 if annotation is float else 1
        elif annotation is bool:
            result[name] = True
        else:
            result[name] = f"[mock {name}]"
    return result


def _mock_parse_result() -> dict:
    """Return a realistic fake parse() result (same shape as the real API path)."""
    chunks = [
        {
            "chunk_id": str(uuid.uuid4()),
            "type": "text",
            "text": "INVOICE — Vendor: Apex Consulting Sdn Bhd — Invoice No: INV-2026-00841 — Date: 2026-03-15",
            "grounding": [{"page": 0, "bbox": [0.05, 0.05, 0.95, 0.18]}],
        },
        {
            "chunk_id": str(uuid.uuid4()),
            "type": "text",
            "text": "Description of Services: Professional advisory services rendered for Q1 2026. Total Due: MYR 12,500.00",
            "grounding": [{"page": 0, "bbox": [0.05, 0.20, 0.95, 0.55]}],
        },
        {
            "chunk_id": str(uuid.uuid4()),
            "type": "text",
            "text": "Payment Instructions: Bank Islam Malaysia — Account No. 1234567890. Approved by: Ahmad Zulkifli bin Hassan.",
            "grounding": [{"page": 1, "bbox": [0.05, 0.05, 0.95, 0.30]}],
        },
    ]
    return {"markdown": _MOCK_MARKDOWN, "chunks": chunks, "page_count": 2}


# ---------------------------------------------------------------------------


def parse_document(source: Source) -> dict:
    """Phase 2. Returns markdown, grounded chunks, and page_count."""
    if get_settings().mock_ade:
        return _mock_parse_result()

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


def parse_and_extract_raw(source: Source, schema_dict: dict) -> dict:
    """Phase 2 + 3 using a raw JSON Schema dict instead of a Pydantic model.

    Used when the case has custom schema_fields stored in the DB.
    The schema_dict must be a valid JSON Schema object with a 'properties' key.
    """
    if get_settings().mock_ade:
        mock = _mock_parse_result()
        # Return a stub string value for every key in the schema
        fields = {k: f"[mock {k}]" for k in schema_dict.get("properties", {})}
        return {**mock, "fields": fields, "confidence": {}}

    import json
    parsed = parse_document(source)
    schema_str = json.dumps(schema_dict)
    client = _get_client()
    result = client.extract(schema=schema_str, markdown=parsed["markdown"])
    extraction = getattr(result, "extraction", None)
    if isinstance(extraction, dict):
        fields = extraction
    elif hasattr(extraction, "model_dump"):
        fields = extraction.model_dump()
    else:
        fields = {}
    return {
        "markdown": parsed["markdown"],
        "chunks": parsed["chunks"],
        "page_count": parsed["page_count"],
        "fields": fields,
        "confidence": {},
    }


def parse_and_extract(source: Source, model: Type[BaseModel]) -> dict:
    """Phase 2 + 3. Single-source entry point used by the pipeline.

    Runs parse() once, then extract() on the resulting markdown so we don't
    re-fetch the document. More efficient than calling both phases separately.
    """
    if get_settings().mock_ade:
        mock = _mock_parse_result()
        return {**mock, "fields": _mock_fields(model), "confidence": {}}

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
