"""How evidence becomes a requirement status — the rules, and the two callers that apply them.

Two things were wrong before, and they pulled in opposite directions:

  * matching left every requirement `unchecked` however much evidence it proposed, so a finished
    analysis produced an empty status column;
  * dismissing the last confirmed link reset the requirement to `unchecked` — "nobody has looked
    at this" — when someone had just looked at it and rejected the evidence. Readiness counts a
    mandatory `gap` as a blocker and an `unchecked` as a warning, so the distinction decides
    whether a workspace reads as submittable.
"""
import pytest

from backend.apps.tendering import db
from backend.apps.tendering.pipeline import evidence_matching
from backend.apps.tendering.status_rules import (
    MIN_PROPOSAL_SCORE,
    status_after_matching,
    status_from_evidence,
)


def _link(status="pending", score=0.9):
    return {"human_review_status": status, "score": score}


# ── the rules ──────────────────────────────────────────────────────────────────

def test_confirmed_evidence_means_met():
    assert status_from_evidence([_link("confirmed")]) == "met"


def test_work_marked_complete_means_met_whatever_the_evidence_says():
    assert status_from_evidence([], completion_status="complete") == "met"


def test_a_proposal_awaiting_review_means_partial():
    assert status_from_evidence([_link("pending", 0.9)]) == "partial"


def test_a_weak_proposal_does_not_count_as_partial():
    """A matrix that looks half-covered on weak guesses is worse than one that looks empty."""
    assert status_from_evidence([_link("pending", MIN_PROPOSAL_SCORE - 0.01)]) == "gap"


def test_dismissing_the_last_evidence_leaves_a_gap_not_an_unchecked():
    assert status_from_evidence([_link("dismissed")]) == "gap"


def test_no_evidence_at_all_is_a_gap():
    assert status_from_evidence([]) == "gap"


def test_one_confirmed_link_outweighs_dismissed_ones():
    links = [_link("dismissed"), _link("confirmed"), _link("pending")]
    assert status_from_evidence(links) == "met"


def test_a_pending_proposal_survives_a_dismissal_of_a_different_document():
    assert status_from_evidence([_link("dismissed"), _link("pending", 0.8)]) == "partial"


@pytest.mark.parametrize("score", [None, "", "not a number", -1])
def test_an_unreadable_score_is_treated_as_no_evidence(score):
    assert status_from_evidence([{"human_review_status": "pending", "score": score}]) == "gap"


# ── what matching itself may write ─────────────────────────────────────────────

def test_matching_fills_in_partial_for_a_fresh_requirement():
    assert status_after_matching([_link("pending", 0.9)], "unchecked") == "partial"


def test_matching_marks_a_requirement_with_nothing_found_as_a_gap():
    assert status_after_matching([], "unchecked") == "gap"


def test_matching_never_writes_met():
    """Rule 3: the AI proposes, a person decides. A confirmed link is that person's decision."""
    assert status_after_matching([_link("confirmed")], "unchecked") is None


def test_matching_never_overwrites_a_met_requirement():
    assert status_after_matching([], "met") is None


def test_matching_leaves_completed_work_alone():
    assert status_after_matching([], "gap", completion_status="complete") is None


def test_matching_writes_nothing_when_the_status_already_matches():
    assert status_after_matching([_link("pending", 0.9)], "partial") is None
    assert status_after_matching([], "gap") is None


def test_matching_can_move_a_gap_back_to_partial_when_evidence_turns_up():
    assert status_after_matching([_link("pending", 0.9)], "gap") == "partial"


# ── the confirm / dismiss path ─────────────────────────────────────────────────

def _recalc(monkeypatch, links, requirement):
    """Run recalculate_requirement_status_from_evidence against fake tables."""
    written: list[dict] = []

    class _Query:
        def __init__(self, table):
            self.table_name = table

        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def update(self, patch):
            written.append(patch)
            return self

        def execute(self):
            data = links if self.table_name == "evidence_links" else [requirement]
            return type("R", (), {"data": data})()

    monkeypatch.setattr(db, "get_client", lambda: type("C", (), {"table": staticmethod(_Query)})())
    db.recalculate_requirement_status_from_evidence("REQ-1")
    return written


def test_confirming_evidence_marks_the_requirement_met(monkeypatch):
    written = _recalc(monkeypatch, [_link("confirmed")], {"status": "partial"})
    assert written == [{"status": "met"}]


def test_dismissing_the_last_confirmed_link_leaves_a_gap(monkeypatch):
    """The bug: this used to write `unchecked`, downgrading a blocker to a warning."""
    written = _recalc(monkeypatch, [_link("dismissed")], {"status": "met"})
    assert written == [{"status": "gap"}]


def test_dismissing_one_of_two_proposals_still_updates_the_status(monkeypatch):
    """Nothing confirmed and nothing `met` used to return without writing anything at all."""
    written = _recalc(monkeypatch, [_link("dismissed"), _link("pending", 0.9)],
                      {"status": "unchecked"})
    assert written == [{"status": "partial"}]


def test_no_write_when_the_status_is_already_right(monkeypatch):
    written = _recalc(monkeypatch, [_link("confirmed")], {"status": "met"})
    assert written == []


def test_completed_work_stays_met_even_if_its_evidence_is_dismissed(monkeypatch):
    written = _recalc(monkeypatch, [_link("dismissed")],
                      {"status": "met", "completion_status": "complete"})
    assert written == []


# ── matching applies the status as part of the run ─────────────────────────────

@pytest.fixture
def matching(monkeypatch):
    """Run match() over one requirement, capturing the status it writes."""
    state = {"requirement": {"req_id": "REQ-1", "description": "Hold a CIDB G7 licence",
                             "status": "unchecked"},
             "candidates": [{"supplier_document_id": "SUP-1", "library_doc_id": "LIB-1",
                             "chunk_id": "c1", "text": "CIDB G7", "similarity": 0.9}],
             "match_score": 0.9}
    updates: list[tuple] = []

    monkeypatch.setattr(db, "get_tendering_workspace", lambda tid: {"id": tid, "org_id": "org-1"})
    monkeypatch.setattr(db, "list_workspace_requirements_raw", lambda tid: [state["requirement"]])
    monkeypatch.setattr(db, "list_evidence_links", lambda tid: [])
    monkeypatch.setattr(db, "write_workspace_audit", lambda *a, **k: None)
    monkeypatch.setattr(db, "match_supplier_docs", lambda *a, **k: state["candidates"])
    monkeypatch.setattr(db, "upsert_evidence_link", lambda row: row)
    monkeypatch.setattr(db, "update_requirement",
                        lambda req_id, patch: updates.append((req_id, patch)))

    from backend.core import llm, llm_reasoning
    monkeypatch.setattr(llm, "embed", lambda texts: [[0.1] * 4 for _ in texts])
    monkeypatch.setattr(llm_reasoning, "ask", lambda *a, **k: {"matches": [
        {"supplier_document_id": "SUP-1", "match_score": state["match_score"],
         "rationale": "The certificate names CIDB G7."}]})
    return state, updates


def test_a_proposed_match_sets_the_requirement_to_partial(matching):
    state, updates = matching

    result = evidence_matching.match("ws-1")

    assert updates == [("REQ-1", {"status": "partial"})]
    assert result["statuses_set"] == 1


def test_a_requirement_with_nothing_in_the_vault_becomes_a_gap(matching):
    state, updates = matching
    state["candidates"] = []

    evidence_matching.match("ws-1")

    assert updates == [("REQ-1", {"status": "gap"})]


def test_a_weak_match_leaves_a_gap_rather_than_claiming_partial_cover(matching):
    state, updates = matching
    state["match_score"] = MIN_PROPOSAL_SCORE - 0.1

    evidence_matching.match("ws-1")

    assert updates == [("REQ-1", {"status": "gap"})]


def test_a_failing_status_write_does_not_lose_the_matching_run(matching, monkeypatch):
    """The evidence link is already saved; the status is not worth the whole run."""
    state, _updates = matching

    def boom(req_id, patch):
        raise RuntimeError("postgrest unreachable")

    monkeypatch.setattr(db, "update_requirement", boom)

    result = evidence_matching.match("ws-1")

    assert result["proposed"] == 1
    assert result["statuses_set"] == 0
