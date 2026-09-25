"""What happens to a rule-found obligation the model does not carry forward.

The rule pass no longer lands as-is: its rows go to the LLM as drafts and the model returns one
deduplicated set, which is how section-header noise stops reaching the matrix. The cost is that a
genuine obligation the model leaves behind is simply not inserted, and there was no trace of it
anywhere — the result counted rule drafts in and unified rows out, never the difference.

These tests pin the accounting, not a restoration: dropping noise is the point of the design, so
the fix is that a disappearance is visible in the audit row rather than silent.
"""
import pytest

from backend.apps.tendering import db
from backend.apps.tendering.pipeline import extract_requirements
from backend.core import llm_reasoning

OBLIGATION = "The bidder shall hold a valid CIDB G7 licence for the duration of the contract."


@pytest.fixture
def run(monkeypatch):
    """Run extract() over one document with one obligation, capturing the audit detail."""
    state = {"answer": {"requirements": []}}
    inserted: list[dict] = []
    audits: list[dict] = []

    monkeypatch.setattr(db, "get_tendering_workspace", lambda ws: {"id": ws, "org_id": "org-1"})
    monkeypatch.setattr(db, "delete_workspace_requirements", lambda ws, pending_only=False: None)
    monkeypatch.setattr(db, "list_workspace_requirements_raw", lambda ws: [])
    monkeypatch.setattr(db, "list_core_documents_for_workspace", lambda ws: [
        {"document_id": "D1", "filename": "itt.pdf", "extraction_status": "done"}])
    monkeypatch.setattr(db, "list_chunks", lambda doc_id: [
        {"chunk_id": "c1", "text": OBLIGATION, "page": 4}])
    monkeypatch.setattr(db, "insert_workspace_requirement",
                        lambda row: inserted.append(row) or row)
    monkeypatch.setattr(db, "write_workspace_audit",
                        lambda ws, actor, action, detail=None: audits.append(detail or {}))
    monkeypatch.setattr(llm_reasoning, "ask", lambda *a, **k: state["answer"])
    return state, inserted, audits


def test_a_draft_the_model_answers_for_is_not_counted_as_dropped(run):
    state, inserted, audits = run
    state["answer"] = {"requirements": [
        {"description": "Hold a valid CIDB G7 licence", "chunk_id": "c1",
         "category": "certification", "is_mandatory": True, "confidence": 0.9},
    ]}

    result = extract_requirements.extract("ws-1")

    assert result["rule_drafts_dropped"] == 0
    assert result["requirements_inserted"] == 1
    assert "rule_drafts_dropped_samples" not in result


def test_a_draft_the_model_ignores_is_counted_and_sampled(run):
    """The silent case: the model returned nothing for that excerpt, so the obligation is gone."""
    state, inserted, audits = run
    state["answer"] = {"requirements": []}

    result = extract_requirements.extract("ws-1")

    assert result["rule_drafts_dropped"] == 1
    assert result["requirements_inserted"] == 0
    assert OBLIGATION[:40] in result["rule_drafts_dropped_samples"][0]
    # The audit row carries it too — that is where someone looks when a requirement is missing.
    assert audits[0]["rule_drafts_dropped"] == 1


def test_an_answer_about_a_different_excerpt_does_not_cover_the_draft(run):
    state, inserted, audits = run
    state["answer"] = {"requirements": [
        {"description": "Something from elsewhere", "chunk_id": "c-other"},
    ]}

    result = extract_requirements.extract("ws-1")

    assert result["rule_drafts_dropped"] == 1
    assert result["ungrounded_dropped"] == 1      # and the answer itself was ungrounded


def test_an_llm_outage_falls_back_rather_than_reporting_drops(run):
    """Nothing was dropped — the rule rows landed, which is the existing fallback."""
    state, inserted, audits = run
    state["answer"] = None

    result = extract_requirements.extract("ws-1")

    assert result["rule_drafts_dropped"] == 0
    assert result["requirements_inserted"] == 1
    assert inserted[0]["source"] == "rule"
