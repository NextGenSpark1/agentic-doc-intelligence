"""Stage 2+3 — run ADE on a document, persist the extraction, and index chunks for RAG.

Core (app-agnostic). The per-case-type extraction schema is not known here — each product
injects a `schema_resolver(case_type) -> pydantic model` so core never depends on an app's
schemas. Investigation passes its fraud registry; Tendering will pass its tender registry.
"""
from __future__ import annotations

import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Callable

from . import ade_client, db_core as db, llm

# Gemini's batch embedding API rejects requests with more than 100 inputs, AND the free tier
# caps embed requests at 100/minute — so long documents (hundreds of chunks) must be embedded
# in slices, with a backoff pause if a slice gets rate-limited.
_EMBED_BATCH_SIZE = 100
_EMBED_RATE_LIMIT_RETRIES = 3
_EMBED_RATE_LIMIT_BACKOFF_SECONDS = 20


def run_extraction(document: dict, case: dict, schema_resolver: Callable[[str], type]) -> dict:
    """Parse + schema-extract one document. Returns the parsed markdown (for classify).

    If the case has schema_fields stored (custom or preset), builds a raw JSON Schema
    dict and uses parse_and_extract_raw(). Otherwise falls back to the Pydantic path, using
    `schema_resolver(case_type)` — injected by the app so core stays schema-agnostic.
    Persists an `extractions` row and indexes `chunks` (with embeddings) for case chat.
    """
    # Pull the file from Supabase Storage and hand the bytes to ADE.
    bucket = db.get_client().storage.from_(db.get_settings().storage_bucket)
    content = bucket.download(document["storage_path"])

    schema_fields: list[dict] = case.get("schema_fields") or []

    if schema_fields:
        # Build a JSON Schema dict from stored field definitions
        properties: dict = {}
        for field in schema_fields:
            name = field.get("name", "")
            if not name:
                continue
            if field.get("is_array"):
                properties[name] = {
                    "description": field.get("description", ""),
                    "type": "array",
                    "items": {"type": "string"},
                }
            else:
                properties[name] = {
                    "description": field.get("description", ""),
                    "type": "string",
                }
        schema_dict = {"type": "object", "properties": properties}
        parsed = ade_client.parse_and_extract_raw(content, schema_dict)
        schema_name = "custom"
    else:
        schema = schema_resolver(case.get("case_type", ""))
        parsed = ade_client.parse_and_extract(content, schema)
        schema_name = schema.__name__

    db.insert_extraction(
        {
            "extraction_id": str(uuid.uuid4()),
            "document_id": document["document_id"],
            "schema_name": schema_name,
            "extracted_json": parsed["fields"],
            "visual_grounding_json": {"confidence": parsed["confidence"]},
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    _index_chunks(case["case_id"], document["document_id"], parsed["chunks"])

    db.update_document(document["document_id"], {"page_count": parsed["page_count"]})
    return {"markdown": parsed["markdown"]}


def _embed_batch_with_retry(batch: list[str]) -> list[list[float]]:
    """Embed one slice, retrying with a fixed backoff on rate-limit errors (the free tier caps
    embed requests at 100/minute, so consecutive slices routinely get 429'd)."""
    from litellm import RateLimitError

    for attempt in range(_EMBED_RATE_LIMIT_RETRIES + 1):
        try:
            return llm.embed(batch)
        except RateLimitError:
            if attempt == _EMBED_RATE_LIMIT_RETRIES:
                raise
            time.sleep(_EMBED_RATE_LIMIT_BACKOFF_SECONDS)
    raise AssertionError("unreachable")  # loop always returns or raises


def _embed_in_batches(texts: list[str], case_id: str, document_id: str) -> list[list[float] | None]:
    """Embed texts in slices of _EMBED_BATCH_SIZE (the provider's per-request cap). A slice
    that still fails to embed after retries degrades to text-only storage for just that
    slice — one bad or oversized slice no longer silently kills embeddings for an entire
    document. Failures are logged (stdout + audit_log) so a broken case is diagnosable
    instead of invisible."""
    vectors: list[list[float] | None] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i:i + _EMBED_BATCH_SIZE]
        try:
            vectors.extend(_embed_batch_with_retry(batch))
        except Exception as exc:
            traceback.print_exc()
            db.write_audit(case_id, "system", "chunk_embedding_failed", {
                "document_id": document_id, "batch_start": i, "batch_size": len(batch),
                "error": str(exc),
            })
            vectors.extend([None] * len(batch))  # store text only; chat falls back to keyword search
    return vectors


def _index_chunks(case_id: str, document_id: str, chunks: list[dict]) -> None:
    """Embed chunk text and store for retrieval. Degrades to text-only storage per-batch if
    embedding fails (see `_embed_in_batches`)."""
    texts = [c["text"] for c in chunks if c.get("text")]
    if not texts:
        return
    vectors = _embed_in_batches(texts, case_id, document_id)

    rows, vector_index = [], 0
    for c in chunks:
        if not c.get("text"):
            continue
        grounding = (c.get("grounding") or [{}])[0]
        rows.append(
            {
                "case_id": case_id,
                "document_id": document_id,
                "chunk_id": c.get("chunk_id") or str(uuid.uuid4()),
                "text": c["text"],
                "type": c.get("type") or "text",
                "page": grounding.get("page"),
                "bbox": grounding.get("bbox") or [],
                "embedding": vectors[vector_index],
            }
        )
        vector_index += 1
    db.insert_chunks(rows)
