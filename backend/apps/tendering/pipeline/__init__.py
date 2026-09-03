"""Tendering pipeline — workspace-scoped analysis stages.

Entry points, all designed to run inside a FastAPI BackgroundTask:
  * run_workspace_analysis(workspace_id) — full pipeline: extract → summarise → readiness.

Document extraction (ADE → chunks → embeddings) is handled by the core pipeline when a
workspace document is uploaded. This package only handles the tender-intelligence stages
that run AFTER core extraction is done.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone


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
