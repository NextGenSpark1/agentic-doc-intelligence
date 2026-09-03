"""Tendering pipeline — workspace-scoped analysis stages.

Entry points, all designed to run inside a FastAPI BackgroundTask:
  * process_workspace_document(workspace_doc_id) — per-document: ADE → chunks → embeddings.
  * run_workspace_analysis(workspace_id)          — workspace-wide: extract reqs → summarise → readiness.

Document extraction is separate from analysis so the user controls when credits are spent:
  1. Upload docs (free — just metadata + Supabase Storage).
  2. Click Extract per doc (spends ADE credit).
  3. Click Run Analysis when happy with the doc set (spends LLM credit).
"""
from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone


def process_workspace_document(workspace_doc_id: str) -> None:
    """ADE extraction for one workspace document.

    Downloads the file from Supabase Storage, runs ADE (text + chunks, no structured schema),
    stores the extraction record, and indexes chunks with workspace_id set so the requirement-
    extraction pipeline can find them via list_core_documents_for_workspace().
    """
    from backend.core import ade_client
    from backend.core import db_core as core_db
    from .. import db

    workspace_doc = db.get_workspace_document(workspace_doc_id)
    if not workspace_doc:
        return

    core_document_id = workspace_doc.get("document_id")
    if not core_document_id:
        return

    core_doc = db.get_core_document(core_document_id)
    if not core_doc:
        return

    workspace_id = core_doc.get("workspace_id")
    core_db.update_document(core_document_id, {"extraction_status": "processing"})

    try:
        bucket = core_db.get_client().storage.from_(core_db.get_settings().storage_bucket)
        content = bucket.download(core_doc["storage_path"])

        parsed = ade_client.parse_document(content)

        core_db.get_client().table("extractions").insert({
            "extraction_id": str(uuid.uuid4()),
            "document_id": core_document_id,
            "schema_name": "tender_document",
            "extracted_json": {},
            "visual_grounding_json": {"confidence": 1.0},
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        _index_workspace_chunks(workspace_id, core_document_id, parsed["chunks"])

        core_db.update_document(core_document_id, {
            "extraction_status": "done",
            "page_count": parsed.get("page_count", 0),
        })
        db.write_workspace_audit(workspace_id, "system", "document_extracted", {
            "workspace_doc_id": workspace_doc_id,
            "document_id": core_document_id,
            "page_count": parsed.get("page_count", 0),
        })
    except Exception as exc:
        traceback.print_exc()
        core_db.update_document(core_document_id, {"extraction_status": "failed"})
        if workspace_id:
            db.write_workspace_audit(workspace_id, "system", "document_extraction_failed", {
                "workspace_doc_id": workspace_doc_id,
                "error": str(exc)[:500],
            })


def _index_workspace_chunks(workspace_id: str, document_id: str, chunks: list[dict]) -> None:
    """Embed chunk text and store with workspace_id for workspace-scoped vector search."""
    from backend.core import llm
    from backend.core.db_core import insert_chunks

    texts = [chunk["text"] for chunk in chunks if chunk.get("text")]
    if not texts:
        return

    vectors: list = []
    batch_size = 100
    for index in range(0, len(texts), batch_size):
        try:
            vectors.extend(llm.embed(texts[index:index + batch_size]))
        except Exception:
            vectors.extend([None] * len(texts[index:index + batch_size]))

    rows = []
    vector_index = 0
    for chunk in chunks:
        if not chunk.get("text"):
            continue
        grounding = (chunk.get("grounding") or [{}])[0]
        rows.append({
            "case_id": None,
            "workspace_id": workspace_id,
            "document_id": document_id,
            "chunk_id": chunk.get("chunk_id") or str(uuid.uuid4()),
            "text": chunk["text"],
            "type": chunk.get("type") or "text",
            "page": grounding.get("page"),
            "bbox": grounding.get("bbox") or [],
            "embedding": vectors[vector_index],
        })
        vector_index += 1

    insert_chunks(rows)


def run_workspace_analysis(workspace_id: str) -> dict:
    """Full pipeline for a workspace: extract requirements → summarise → readiness review.

    Order matters: evidence matching needs requirements, and the summary reports on both.
    A stage that fails is audited and the run continues.
    """
    from .. import db
    from . import extract_requirements, readiness_review, summarise_tender

    db.write_workspace_audit(workspace_id, "system", "analysis_started", {})
    try:
        requirements_result = extract_requirements.extract(workspace_id)

        summary_result = summarise_tender.summarise(workspace_id)

        try:
            readiness_result = readiness_review.review(workspace_id)
        except Exception as exc:
            traceback.print_exc()
            db.write_workspace_audit(workspace_id, "system", "readiness_review_failed",
                                     {"error": str(exc)[:500]})
            readiness_result = {}

        result = {
            "stages_run": ["extract_requirements", "summarise_tender", "readiness_review"],
            **requirements_result,
            "days_until_closing": summary_result.get("days_until_closing"),
            "readiness_score": readiness_result.get("score"),
            "submission_blocked": readiness_result.get("submission_blocked"),
            "blockers": readiness_result.get("blockers"),
        }
        db.write_workspace_audit(workspace_id, "system", "analysis_completed", result)
        return result
    except Exception as exc:
        traceback.print_exc()
        db.write_workspace_audit(workspace_id, "system", "analysis_failed",
                                 {"error": str(exc)[:500]})
        return {"error": str(exc)}
