"""Startup recovery for work interrupted by a restart.

Analysis and extraction run in FastAPI BackgroundTasks — inside the API process. A deploy or a
container restart kills them mid-flight and nothing on the row records that: the workspace stays
`analysing` and the document stays `queued` for good. The pipeline's own error handling does not
help here, because the process is gone before any `except` block can run.

That leaves the tender unusable rather than merely stale: the UI disables both the Analyse button
and the stage dropdown while a workspace is `analysing`, so nobody can retry it or move it on
without an edit straight to the database.

This does not resume the work — that needs a real job queue (the next step if analyses get long
enough to matter). It marks the work as stopped so a person can press the button again.

Assumes a SINGLE API instance, which is how this deploys today. With several replicas, one
booting would reset work another replica is still running.
"""
from __future__ import annotations

import traceback


def recover_interrupted_work() -> dict:
    """Mark work left mid-flight by the previous process as stopped. Never raises.

    Boot must not depend on the database being reachable, and one failing step must not skip the
    others — so each step is isolated and errors are reported in the returned summary.
    """
    from backend.apps.tendering import db as tendering_db
    from backend.core import db_core

    summary: dict = {"workspaces_reset": 0, "documents_failed": 0, "vault_documents_failed": 0}
    errors: list[str] = []

    try:
        workspaces = tendering_db.reset_stuck_analyses()
        summary["workspaces_reset"] = len(workspaces)
        for workspace in workspaces:
            workspace_id = workspace.get("id")
            if not workspace_id:
                continue
            # Audited per workspace: from the user's side the analysis simply produced nothing,
            # and the audit trail is the only place that says why.
            try:
                tendering_db.write_workspace_audit(
                    workspace_id, "system", "analysis_interrupted",
                    {"reason": "server restarted mid-analysis", "stage_reset_to": "new"},
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"audit {workspace_id}: {type(exc).__name__}: {exc}"[:200])
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        errors.append(f"workspaces: {type(exc).__name__}: {exc}"[:200])

    try:
        summary["documents_failed"] = len(db_core.reset_stuck_extractions())
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        errors.append(f"documents: {type(exc).__name__}: {exc}"[:200])

    try:
        summary["vault_documents_failed"] = len(tendering_db.reset_stuck_supplier_extractions())
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        errors.append(f"vault documents: {type(exc).__name__}: {exc}"[:200])

    if errors:
        summary["errors"] = errors
    return summary
