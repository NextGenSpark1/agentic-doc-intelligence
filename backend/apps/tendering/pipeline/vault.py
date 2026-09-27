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

    # Step 1: ADE parsing — failure here means nothing was extracted; mark failed.
    try:
        bucket = db_core.get_client().storage.from_("library-documents")
        content = bucket.download(document["storage_path"])
        parsed = ade_client.parse_document(content)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        db.update_supplier_document(supplier_document_id, {"extraction_status": "failed"})
        try:
            db_core.get_client().table("audit_log").insert({
                "actor": "system", "action": "vault_extraction_failed",
                "detail": {"supplier_document_id": supplier_document_id,
                           "org_id": org_id, "error": str(exc)[:500]},
            }).execute()
        except Exception:
            pass
        return

    # Step 2: chunk indexing (embed + store) — failure degrades to no vector search
    # but text was extracted, so mark done regardless so users can view it.
    try:
        _index_vault_chunks(org_id, supplier_document_id, parsed["chunks"])
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        try:
            db_core.get_client().table("audit_log").insert({
                "actor": "system", "action": "vault_indexing_failed",
                "detail": {"supplier_document_id": supplier_document_id,
                           "org_id": org_id, "error": str(exc)[:500]},
            }).execute()
        except Exception:
            pass

    # Step 3: read the dates off the document, for the fields nobody filled in. Never fatal —
    # a document with no readable dates is the normal case for a CV or a project reference.
    try:
        _backfill_dates(document, parsed, supplier_document_id, org_id)
    except Exception:  # noqa: BLE001
        traceback.print_exc()

    db.update_supplier_document(supplier_document_id, {
        "extraction_status": "done",
        "page_count": parsed.get("page_count") or 0,
    })


def _document_text(parsed: dict) -> str:
    """The document's text, whichever shape ADE returned it in."""
    markdown = (parsed.get("markdown") or "").strip()
    if markdown:
        return markdown
    return "\n".join(chunk.get("text") or "" for chunk in (parsed.get("chunks") or []))


def _backfill_dates(document: dict, parsed: dict, supplier_document_id: str, org_id: str) -> None:
    """Fill blank issue/expiry dates from the document's own text.

    Expiry dates only ever came from the upload form, so a certificate uploaded without one
    looked permanent: the score caps could not hold it below `met`, readiness raised no expiry
    gap, and a registration lapsing before the closing date read as proof. The date is printed
    on the document — this reads it.

    Two rules keep it honest. It never overwrites a date a person entered: a blank field is the
    only thing it touches. And what it writes is marked `expiry_source="document"`, meaning
    read-but-not-confirmed, so the UI can ask someone to ratify it before it is treated as
    settled (Rule 3 — the platform surfaces, a human decides).

    The dates go to both tables: library_documents drives the library UI and the readiness
    report, supplier_documents drives evidence matching, and the two disagreeing is its own bug.
    """
    from .. import db
    from ..validity import SOURCE_DOCUMENT, extract_dates

    wanted = {
        field: value
        for field, value in extract_dates(_document_text(parsed)).items()
        if not document.get(field)          # a person's entry always wins
    }
    if not wanted:
        return

    patch = dict(wanted)
    if "expiry_date" in patch:
        patch["expiry_source"] = SOURCE_DOCUMENT
    db.update_supplier_document(supplier_document_id, patch)

    library_doc_id = document.get("library_doc_id")
    if library_doc_id:
        db.update_library_document(str(library_doc_id), patch)

    # The vault is org-scoped, so there is no case or workspace to hang this on — the detail
    # carries the document ids instead, matching how the other vault audit rows are written.
    from backend.core import db_core

    db_core.write_audit(None, "system", "vault_dates_read_from_document", {
        "org_id": org_id,
        "supplier_document_id": supplier_document_id,
        "library_doc_id": str(library_doc_id) if library_doc_id else None,
        "title": document.get("title"),
        **wanted,
    })


def _index_vault_chunks(org_id: str, supplier_document_id: str, chunks: list[dict]) -> None:
    """Embed and store vault chunks. Every row carries org_id — the isolation key.

    Replaces rather than appends. Extract can be clicked more than once, and without clearing
    the previous index each run doubled the document's rows — skewing retrieval toward
    re-extracted documents (more chunks, more chances to land in top-k), and on a fresh
    database colliding with the chunk_id primary key whenever ADE reissues the same ids.

    The old chunks are deleted only after the new ones have been embedded, so a parse or
    embedding failure leaves the previous working index in place rather than an empty one.
    """
    from .. import db

    texts = [c["text"] for c in chunks if c.get("text")]
    if not texts:
        return
    # case_id is None: the vault is org-scoped, not case-scoped. Passing org_id here (as this
    # used to) wrote an org id into audit_log.case_id. The failure row still links back to the
    # vault document, because _embed_in_batches records it as `document_id` in the detail.
    vectors = _embed_in_batches(texts, None, supplier_document_id)

    rows, vector_index = [], 0
    for c in chunks:
        if not c.get("text"):
            continue
        grounding = (c.get("grounding") or [{}])[0]
        row: dict = {
            "org_id": org_id,
            "supplier_document_id": supplier_document_id,
            "chunk_id": c.get("chunk_id") or str(uuid.uuid4()),
            "text": c["text"],
            "page": grounding.get("page"),
            "bbox": grounding.get("bbox") or [],
        }
        # Omit embedding key entirely when None so PostgREST uses the column default (NULL)
        # rather than receiving an explicit null for a vector column, which some versions reject.
        if vectors[vector_index] is not None:
            row["embedding"] = vectors[vector_index]
        rows.append(row)
        vector_index += 1
    db.delete_supplier_chunks(supplier_document_id)
    db.insert_supplier_chunks(rows)
