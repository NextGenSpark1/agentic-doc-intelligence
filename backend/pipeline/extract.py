"""Stage 2+3 — run ADE on a document, persist the extraction, and index chunks for RAG."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .. import ade_client, db, llm
from ..schemas import schema_for_case_type


def run_extraction(document: dict, case: dict) -> dict:
    """Parse + schema-extract one document. Returns the parsed markdown (for classify).

    Persists an `extractions` row and indexes `chunks` (with embeddings) for case chat.
    """
    schema = schema_for_case_type(case.get("case_type", ""))

    # Pull the file from Supabase Storage and hand the bytes to ADE.
    bucket = db.get_client().storage.from_(db.get_settings().storage_bucket)
    content = bucket.download(document["storage_path"])

    parsed = ade_client.parse_and_extract(content, schema)

    db.insert_extraction(
        {
            "extraction_id": str(uuid.uuid4()),
            "document_id": document["document_id"],
            "schema_name": schema.__name__,
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
                "page": grounding.get("page"),
                "bbox": grounding.get("bbox") or [],
                "embedding": vectors[vi],
            }
        )
        vi += 1
    db.insert_chunks(rows)
