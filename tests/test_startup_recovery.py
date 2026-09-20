"""Startup recovery — what happens to work the previous process was killed in the middle of.

A Railway deploy kills BackgroundTasks mid-run, leaving a workspace on `analysing` and documents
on `queued` for good. The UI disables Analyse and the stage dropdown on exactly those values, so
without this the tender is stuck until someone edits the database by hand.

Recovery runs during boot, so the rule that matters as much as the reset itself is: it must never
raise. An unreachable database at boot has to leave the API up.
"""
from backend.apps.tendering import db as tendering_db
from backend.core import db_core
from backend.core.recovery import recover_interrupted_work


def _stub(monkeypatch, *, workspaces=(), documents=(), vault=(), audits=None):
    monkeypatch.setattr(tendering_db, "reset_stuck_analyses", lambda: list(workspaces))
    monkeypatch.setattr(tendering_db, "reset_stuck_supplier_extractions", lambda: list(vault))
    monkeypatch.setattr(db_core, "reset_stuck_extractions", lambda: list(documents))
    monkeypatch.setattr(
        tendering_db, "write_workspace_audit",
        lambda workspace_id, actor, action, detail=None: (
            audits.append((workspace_id, action)) if audits is not None else None
        ),
    )


def test_counts_everything_it_reset(monkeypatch):
    _stub(monkeypatch,
          workspaces=[{"id": "w1"}, {"id": "w2"}],
          documents=[{"document_id": "d1"}],
          vault=[{"supplier_document_id": "s1"}, {"supplier_document_id": "s2"}])

    assert recover_interrupted_work() == {
        "workspaces_reset": 2, "documents_failed": 1, "vault_documents_failed": 2,
    }


def test_quiet_when_nothing_was_interrupted(monkeypatch):
    _stub(monkeypatch)

    summary = recover_interrupted_work()

    assert summary == {"workspaces_reset": 0, "documents_failed": 0, "vault_documents_failed": 0}
    assert "errors" not in summary


def test_each_reset_workspace_is_audited(monkeypatch):
    audits: list[tuple[str, str]] = []
    _stub(monkeypatch, workspaces=[{"id": "w1"}, {"id": "w2"}], audits=audits)

    recover_interrupted_work()

    # The user just sees an analysis that produced nothing; the audit row is the only record
    # of why it stopped.
    assert audits == [("w1", "analysis_interrupted"), ("w2", "analysis_interrupted")]


def test_a_failing_step_does_not_skip_the_others(monkeypatch):
    def boom():
        raise RuntimeError("postgrest unreachable")

    _stub(monkeypatch, documents=[{"document_id": "d1"}], vault=[{"supplier_document_id": "s1"}])
    monkeypatch.setattr(tendering_db, "reset_stuck_analyses", boom)

    summary = recover_interrupted_work()

    assert summary["workspaces_reset"] == 0
    assert summary["documents_failed"] == 1        # still ran
    assert summary["vault_documents_failed"] == 1  # still ran
    assert any("postgrest unreachable" in error for error in summary["errors"])


def test_a_database_that_is_down_does_not_stop_the_api_booting(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(tendering_db, "reset_stuck_analyses", boom)
    monkeypatch.setattr(tendering_db, "reset_stuck_supplier_extractions", boom)
    monkeypatch.setattr(db_core, "reset_stuck_extractions", boom)

    summary = recover_interrupted_work()  # must not raise

    assert len(summary["errors"]) == 3


def test_boot_runs_recovery(monkeypatch):
    """The wiring itself: starting the app must trigger recovery, not just define it."""
    from fastapi.testclient import TestClient

    import backend.core.recovery as recovery_module
    from backend.core.main import app

    ran: list[str] = []
    monkeypatch.setattr(recovery_module, "recover_interrupted_work",
                        lambda: ran.append("ran") or {"workspaces_reset": 0})

    with TestClient(app):  # entering the context is what runs the lifespan
        pass

    assert ran == ["ran"]


def test_the_api_still_boots_when_recovery_fails(monkeypatch):
    from fastapi.testclient import TestClient

    import backend.core.recovery as recovery_module
    from backend.core.main import app

    def boom():
        raise RuntimeError("database unreachable at boot")

    monkeypatch.setattr(recovery_module, "recover_interrupted_work", boom)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_an_audit_failure_still_leaves_the_workspace_reset(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("audit_log write failed")

    _stub(monkeypatch, workspaces=[{"id": "w1"}])
    monkeypatch.setattr(tendering_db, "write_workspace_audit", boom)

    summary = recover_interrupted_work()

    # The stage change already happened — losing the audit row must not hide that.
    assert summary["workspaces_reset"] == 1
    assert any("audit w1" in error for error in summary["errors"])
