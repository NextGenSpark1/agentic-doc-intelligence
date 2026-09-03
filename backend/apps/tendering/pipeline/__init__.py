"""Tendering pipeline orchestrator.

Mirrors `apps.investigation.pipeline`: external dependencies are imported lazily INSIDE the
functions so importing this package stays cheap and side-effect-free, which keeps the pure
stage logic unit-testable without Supabase / LandingAI / an LLM key present.

Entry points, all designed to run inside a FastAPI BackgroundTask:
  * process_document(document_id)  — per tender document: extract (ADE) then classify.
  * run_tender_analysis(tender_id) — tender-wide: requirements -> evidence -> summary.
  * vault.process_supplier_document(id) — per vault document (org-level, not tender-scoped).

The per-document extraction schema is tender-specific, so this orchestrator injects the tender
schema resolver into core's app-agnostic `run_extraction` — the same seam investigation uses,
with different values.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone


def process_document(document_id: str) -> None:
    from backend.core import extract
    from .. import classify, db
    from ..schemas import schema_for_case_type

    document = db.get_document(document_id)
    if not document:
        return
    tender_id = document.get("tender_id")
    if not tender_id:
        return  # not a tender document — investigation's pipeline owns it
    db.update_document(document_id, {"extraction_status": "processing"})
    try:
        # `run_extraction` reads `case_id` / `tender_id` off this dict to scope the chunks it
        # writes, and `case_type` to resolve the schema.
        workspace = {
            "case_id": None,
            "tender_id": tender_id,
            "case_type": "tender",
            "schema_fields": [],
        }
        result = extract.run_extraction(document, workspace, schema_for_case_type)
        doc_type = classify.classify(result["markdown"])
        db.update_document(document_id, {"document_type": doc_type, "extraction_status": "done"})
        db.write_tender_audit(tender_id, "system", "document_extracted",
                              {"document_id": document_id, "type": doc_type})
    except Exception as exc:  # noqa: BLE001 — record failure, don't crash the worker
        traceback.print_exc()
        db.update_document(document_id, {"extraction_status": "failed"})
        db.write_tender_audit(tender_id, "system", "extraction_failed",
                              {"document_id": document_id, "error": str(exc)[:500]})


def run_tender_analysis(tender_id: str) -> dict:
    """Tender-wide analysis: extract requirements, match vault evidence, then summarise.

    Order matters — evidence matching needs requirements, and the summary reports on both.
    A stage that fails is audited and the run continues: a vault outage should not cost you
    the requirements that were already extracted.
    """
    from .. import db
    from . import evidence_matching, extract_requirements, readiness_review, summarise_tender

    db.write_tender_audit(tender_id, "system", "tender_analysis_started", {})
    try:
        requirements = extract_requirements.extract(tender_id)

        try:
            evidence = evidence_matching.match(tender_id)
        except Exception as exc:  # noqa: BLE001 — matching is the newest, least proven stage
            traceback.print_exc()
            db.write_tender_audit(tender_id, "system", "evidence_matching_failed",
                                  {"error": str(exc)[:500]})
            evidence = {"proposed": 0, "error": str(exc)[:200]}

        summary = summarise_tender.summarise(tender_id)

        # Readiness runs last: it audits the output of every stage before it.
        try:
            readiness = readiness_review.review(tender_id)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            db.write_tender_audit(tender_id, "system", "readiness_review_failed",
                                  {"error": str(exc)[:500]})
            readiness = {}

        result = {
            "stages_run": ["extract_requirements", "evidence_matching", "summarise_tender",
                           "readiness_review"],
            **requirements,
            "evidence_proposed": evidence.get("proposed", 0),
            "requirements_without_evidence": evidence.get("requirements_without_candidates"),
            "days_until_closing": summary.get("days_until_closing"),
            "readiness_score": readiness.get("score"),
            "submission_blocked": readiness.get("submission_blocked"),
            "blockers": readiness.get("blockers"),
        }
        db.update_tender(tender_id, {
            "last_analysed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        db.write_tender_audit(tender_id, "system", "tender_analysis_completed", result)
        return result
    except Exception as exc:  # noqa: BLE001 — a dead BackgroundTask leaves the UI polling forever
        traceback.print_exc()
        db.write_tender_audit(tender_id, "system", "tender_analysis_failed", {"error": str(exc)[:500]})
        return {"error": str(exc)}
