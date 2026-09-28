"""The matching run itself: which requirements it spends an LLM call on.

Adjudication is one embedding plus one LLM call per requirement, so what the loop *skips* is the
difference between a re-analysis costing a few calls and costing fifty. A requirement whose
evidence a person has already confirmed is the clearest skip: the proposal would be born pending
next to a confirmed link and could not change anything.
"""
import pytest

from backend.apps.tendering import db
from backend.apps.tendering.pipeline import evidence_matching


@pytest.fixture
def run(monkeypatch):
    """Run match() against fakes, recording which requirements reached the LLM."""
    adjudicated: list[str] = []
    state = {
        "requirements": [
            {"req_id": "REQ-1", "description": "Hold a CIDB G7 licence", "mandatory": True},
            {"req_id": "REQ-2", "description": "Provide audited accounts", "mandatory": True},
        ],
        "links": [],
    }

    monkeypatch.setattr(db, "get_tendering_workspace", lambda tid: {"id": tid, "org_id": "org-1"})
    monkeypatch.setattr(db, "list_workspace_requirements_raw", lambda tid: state["requirements"])
    monkeypatch.setattr(db, "list_evidence_links", lambda tid: state["links"])
    monkeypatch.setattr(db, "write_workspace_audit", lambda *a, **k: None)
    monkeypatch.setattr(db, "match_supplier_docs", lambda org_id, vec, k: [
        {"supplier_document_id": "SUP-1", "library_doc_id": "LIB-1", "chunk_id": "c1",
         "text": "CIDB G7 certificate", "similarity": 0.9},
    ])
    monkeypatch.setattr(db, "upsert_evidence_link", lambda row: row)

    from backend.core import llm, llm_reasoning
    monkeypatch.setattr(llm, "embed", lambda texts: [[0.1] * 4 for _ in texts])

    # A test can put its own model answer in state["answer"] to exercise the validation path.
    state["answer"] = {"matches": [{"supplier_document_id": "SUP-1", "match_score": 0.9,
                                    "rationale": "The certificate names CIDB G7."}]}

    def fake_ask(system_prompt, payload, **kwargs):
        adjudicated.append(payload["requirement"]["description"])
        return state["answer"]

    monkeypatch.setattr(llm_reasoning, "ask", fake_ask)
    return state, adjudicated


def test_every_requirement_is_adjudicated_when_nothing_is_confirmed(run):
    state, adjudicated = run

    result = evidence_matching.match("ws-1")

    assert len(adjudicated) == 2
    assert result["proposed"] == 2
    assert result["already_confirmed"] == 0


def test_a_requirement_with_confirmed_evidence_costs_no_llm_call(run):
    state, adjudicated = run
    state["links"] = [{"req_id": "REQ-1", "doc_id": "LIB-1", "human_review_status": "confirmed"}]

    result = evidence_matching.match("ws-1")

    assert adjudicated == ["Provide audited accounts"]      # REQ-1 was skipped entirely
    assert result["already_confirmed"] == 1
    assert result["proposed"] == 1


def test_pending_and_dismissed_links_do_not_skip_a_requirement(run):
    """Only a person confirming evidence settles a requirement; a proposal does not."""
    state, adjudicated = run
    state["links"] = [
        {"req_id": "REQ-1", "doc_id": "LIB-1", "human_review_status": "pending"},
        {"req_id": "REQ-2", "doc_id": "LIB-9", "human_review_status": "dismissed"},
    ]

    result = evidence_matching.match("ws-1")

    assert len(adjudicated) == 2
    assert result["already_confirmed"] == 0


def test_requirement_ids_still_narrow_the_run(run):
    state, adjudicated = run

    evidence_matching.match("ws-1", requirement_ids=["REQ-2"])

    assert adjudicated == ["Provide audited accounts"]


# ── why proposals were discarded ───────────────────────────────────────────────

def test_each_drop_reason_is_counted_separately():
    """"28 dropped" cannot be acted on. A model naming documents it was never sent is a
    grounding problem; scores under the floor are a threshold problem; a missing rationale is a
    prompt problem. They are fixed in three different places."""
    from backend.apps.tendering.pipeline.evidence_matching import validate_matches

    candidates = {"SUP-1": {"supplier_document_id": "SUP-1", "library_doc_id": "LIB-1",
                            "chunk_id": "c1", "text": "CIDB G7"}}
    raw = {"matches": [
        {"supplier_document_id": "SUP-NEVER-SENT", "match_score": 0.9, "rationale": "invented"},
        {"supplier_document_id": "SUP-1", "match_score": 0.2, "rationale": "weak"},
        {"supplier_document_id": "SUP-1", "match_score": 0.9, "rationale": ""},
        "not even a dict",
    ]}
    drops: dict = {}

    kept = validate_matches(raw, candidates, drops=drops)

    assert kept == []
    assert drops == {"ungrounded": 1, "score_below_floor": 1, "duplicate_document": 1,
                     "malformed": 1}


def test_a_clean_answer_records_no_drops():
    from backend.apps.tendering.pipeline.evidence_matching import validate_matches

    candidates = {"SUP-1": {"supplier_document_id": "SUP-1", "library_doc_id": "LIB-1",
                            "chunk_id": "c1", "text": "CIDB G7"}}
    drops: dict = {}

    kept = validate_matches(
        {"matches": [{"supplier_document_id": "SUP-1", "match_score": 0.9,
                      "rationale": "The certificate names CIDB G7."}]},
        candidates, drops=drops)

    assert len(kept) == 1
    assert drops == {}


def test_the_run_reports_the_breakdown_and_silent_requirements(run):
    """A requirement the model answered with nothing is a different problem from one whose
    answer was discarded, and the audit row has to tell them apart."""
    state, _adjudicated = run
    state["answer"] = {"matches": []}

    result = evidence_matching.match("ws-1")

    assert result["no_proposal_from_model"] == 2
    assert result["proposed"] == 0
    assert result["dropped_by_reason"] == {}
