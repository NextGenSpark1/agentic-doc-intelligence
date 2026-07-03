"""Stage 2+3 — run ADE on a document, persist the extraction, and index chunks for RAG."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .. import ade_client, db, llm
from ..schemas import schema_for_case_type


def run_extraction(document: dict, case: dict) -> dict:
    """Parse + schema-extract one document. Returns the parsed markdown (for classify).

    If the case has schema_fields stored (custom or preset), builds a raw JSON Schema
    dict and uses parse_and_extract_raw(). Otherwise falls back to the Pydantic path.
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
        schema = schema_for_case_type(case.get("case_type", ""))
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


def _index_chunks(case_id: str, document_id: str, chunks: list[dict]) -> None:
    """Embed chunk text and store for retrieval. Degrades silently if embeddings fail."""
    texts = [c["text"] for c in chunks if c.get("text")]
    if not texts:
        return
    try:
        vectors = llm.embed(texts)
    except Exception:
        vectors = [None] * len(texts)  # store text only; chat falls back to keyword search

    rows, vi = [], 0
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
                "embedding": vectors[vi],
            }
        )
        vi += 1
    db.insert_chunks(rows)
