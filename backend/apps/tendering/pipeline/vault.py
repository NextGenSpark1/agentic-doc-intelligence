"""Supplier vault ingestion — parse a company document and index it for evidence matching.

Reuses core's ADE parsing and batched-embedding helpers, but writes to
`supplier_document_chunks` rather than `chunks`. That separation is deliberate and is the
vault's isolation boundary: a vault document can never surface in an investigation case's RAG,
and a case's evidence can never be proposed as bid evidence.

The vault is **org-level**, not per-tender: a company uploads its CIDB certificate once and
every tender it bids on can cite it.
"""
from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone

# Reused from core rather than reimplemented — one embedding path, one set of retry and
# degrade-to-text-only semantics, for both products.
from backend.core.extract import _embed_in_batches


def process_supplier_document(supplier_document_id: str) -> None:
    """Parse + chunk + embed one vault document. Designed to run in a BackgroundTask.

    Failures are recorded on the row and swallowed, exactly as the document pipeline does: a
    worker that dies silently leaves the UI polling for a completion that never arrives.
    """
    from backend.core import ade_client, db_core

    from .. import db

    document = db.get_supplier_document(supplier_document_id)
    if not document:
        return
    org_id = document.get("org_id")
    if not org_id:
        # No org means no isolation boundary — refuse rather than index an unscoped row.
        db.update_supplier_document(supplier_document_id, {"extraction_status": "failed"})
        return

    db.update_supplier_document(supplier_document_id, {"extraction_status": "processing"})
    try:
        bucket = db_core.get_client().storage.from_(db_core.get_settings().storage_bucket)
        content = bucket.download(document["storage_path"])

        parsed = ade_client.parse_document(content)
        _index_vault_chunks(org_id, supplier_document_id, parsed["chunks"])

        db.update_supplier_document(supplier_document_id, {
            "extraction_status": "done",
            "page_count": parsed.get("page_count") or 0,
        })
    except Exception as exc:  # noqa: BLE001 — record failure, don't crash the worker
        traceback.print_exc()
        db.update_supplier_document(supplier_document_id, {"extraction_status": "failed"})
        try:
            db_core.get_client().table("audit_log").insert({
                "actor": "system",
                "action": "vault_extraction_failed",
                "detail": {"supplier_document_id": supplier_document_id,
                           "org_id": org_id, "error": str(exc)[:500]},
            }).execute()
        except Exception:
            pass  # audit logging must never mask the original failure


def _index_vault_chunks(org_id: str, supplier_document_id: str, chunks: list[dict]) -> None:
    """Embed and store vault chunks. Every row carries org_id — the isolation key."""
    from .. import db

    texts = [c["text"] for c in chunks if c.get("text")]
    if not texts:
        return
    vectors = _embed_in_batches(texts, org_id, supplier_document_id)

    rows, vector_index = [], 0
    for c in chunks:
        if not c.get("text"):
            continue
        grounding = (c.get("grounding") or [{}])[0]
        rows.append({
            "org_id": org_id,
            "supplier_document_id": supplier_document_id,
            "chunk_id": c.get("chunk_id") or str(uuid.uuid4()),
            "text": c["text"],
            "page": grounding.get("page"),
            "bbox": grounding.get("bbox") or [],
            "embedding": vectors[vector_index],
        })
        vector_index += 1
    db.insert_supplier_chunks(rows)


def supersede(old_document_id: str, new_document_id: str) -> dict | None:
    """Mark a vault document as replaced by a newer version.

    Superseded documents are excluded from `match_supplier_docs` in SQL, so a renewed
    certificate stops the old one being proposed as evidence — without deleting it, since an
    expired certificate is still a record of what was valid at submission time.
    """
    from .. import db

    return db.update_supplier_document(old_document_id, {
        "superseded_by": new_document_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
