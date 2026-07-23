"""Pipeline orchestrator.

External dependencies (db, the stage modules) are imported lazily INSIDE the functions, so
importing this package is cheap and side-effect-free — that keeps the pure stage logic
unit-testable without Supabase/LandingAI/LLM installed.

Two entry points, both designed to run inside a FastAPI BackgroundTask:
  * process_document(document_id) — per document: extract (ADE) then classify.
  * run_case_analysis(case_id)    — case-wide: resolve entities -> build relationships ->
        reconstruct timeline -> detect anomalies -> summarise.

Upgrade triggers: lift run_case_analysis into LangGraph when reasoning needs to branch/loop;
put it behind Temporal when a run must survive process restarts. Neither is needed yet.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone


def process_document(document_id: str) -> None:
    from .. import db
    from . import classify, extract

    document = db.get_document(document_id)
    if not document:
        return
    case = db.get_case(document["case_id"]) or {}
    db.update_document(document_id, {"extraction_status": "processing"})
    try:
        result = extract.run_extraction(document, case)
        doc_type = classify.classify(result["markdown"])
        db.update_document(document_id, {"document_type": doc_type, "extraction_status": "done"})
        db.write_audit(case["case_id"], "system", "document_extracted",
                       {"document_id": document_id, "type": doc_type})
    except Exception as exc:  # noqa: BLE001 — record failure, don't crash the worker
        traceback.print_exc()
        db.update_document(document_id, {"extraction_status": "failed"})
        db.write_audit(document.get("case_id", ""), "system", "extraction_failed",
                       {"document_id": document_id, "error": str(exc)})


def run_case_analysis(case_id: str) -> dict:
    from .. import db
    from . import (
        build_relationships,
        detect_anomalies,
        reconstruct_timeline,
        resolve_entities,
        summarise,
    )

    db.write_audit(case_id, "system", "analysis_started", {})
    try:
        resolve_entities.resolve(case_id)
        build_relationships.build(case_id)
        reconstruct_timeline.build_timeline(case_id)
        detect_anomalies.detect(case_id)
        result = summarise.summarise(case_id)
        db.update_case(case_id, {"last_analysed_at": datetime.now(timezone.utc).isoformat()})
        db.write_audit(case_id, "system", "analysis_completed", result)
        return result
    except Exception as exc:  # noqa: BLE001 — record failure, don't let the worker die silently
        # Without this the BackgroundTask dies with no trace: no analysis_completed, no
        # last_analysed_at, and any UI polling for completion hangs forever. Log it so a failed
        # run is diagnosable (mirrors process_document's failure handling).
        traceback.print_exc()
        db.write_audit(case_id, "system", "analysis_failed", {"error": str(exc)[:500]})
        return {"error": str(exc)}
