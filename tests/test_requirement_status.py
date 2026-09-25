"""How evidence becomes a requirement status — the rules, and the two callers that apply them.

Statuses under the current model:
  * met       — evidence proves the requirement. Set by a human confirming, or by AI matching
                when a pending proposal scores at/above MET_SCORE_THRESHOLD and the underlying
                document is valid at the tender closing date.
  * partial   — evidence proposed and worth reviewing, but does not conclusively prove it.
  * gap       — nothing was proposed at all.
  * rejected  — proposals existed but every one was dismissed by a reviewer. Distinct from gap.
  * unchecked — starting point before matching runs.

Matching may not overwrite a status a person has settled: confirmed evidence, a manual met, or
a rejected requirement is left alone.
"""
import pytest

from backend.apps.tendering import db
from backend.apps.tendering.pipeline import evidence_matching
from backend.apps.tendering.status_rules import (
    MET_SCORE_THRESHOLD,
    MIN_PROPOSAL_SCORE,
    status_after_matching,
    status_from_evidence,
)


def _link(status="pending", score=0.65):
    """Default score sits between the partial threshold (0.60) and the met threshold (0.75),
    so a default pending link means `partial` — matching most tests' intent."""
    return {"human_review_status": status, "score": score}


# ── the rules ──────────────────────────────────────────────────────────────────

def test_a_confirmed_partial_link_stays_partial():
    """Behaviour change: confirming a link is the reviewer saying "I agree with the AI
    assessment" — it does NOT upgrade the status. A confirmed link with a partial-score
    (below MET_SCORE_THRESHOLD) keeps the requirement partial. Only manual override
    changes the actual status."""
    assert status_from_evidence([_link("confirmed", 0.65)]) == "partial"


def test_a_confirmed_high_score_link_is_met_because_of_the_score():
    """Same threshold rule as for pending: score at/above MET_SCORE_THRESHOLD → met.
    Confirmation records the reviewer's agreement; the score is what determines status."""
    assert status_from_evidence([_link("confirmed", 0.9)]) == "met"


def test_work_marked_complete_means_met_whatever_the_evidence_says():
    assert status_from_evidence([], completion_status="complete") == "met"


def test_a_medium_score_pending_proposal_means_partial():
    assert status_from_evidence([_link("pending", 0.65)]) == "partial"


def test_a_high_score_pending_proposal_means_met():
    """The AI can propose `met` directly when a match is confident enough — a human confirmation
    still stamps who agreed, but the readiness view no longer stalls at zero until then."""
    assert status_from_evidence([_link("pending", MET_SCORE_THRESHOLD)]) == "met"
    assert status_from_evidence([_link("pending", 0.9)]) == "met"


def test_a_weak_proposal_does_not_count_as_partial():
    """A matrix that looks half-covered on weak guesses is worse than one that looks empty."""
    assert status_from_evidence([_link("pending", MIN_PROPOSAL_SCORE - 0.01)]) == "gap"


def test_all_evidence_dismissed_means_rejected_not_gap():
    """The distinction: gap says nothing was found. rejected says a reviewer looked and said no."""
    assert status_from_evidence([_link("dismissed")]) == "rejected"
    assert status_from_evidence([_link("dismissed"), _link("dismissed")]) == "rejected"


def test_no_evidence_at_all_is_a_gap():
    assert status_from_evidence([]) == "gap"


def test_a_high_score_confirmed_link_wins_over_dismissed_ones():
    """The reviewer confirmed a strong AI proposal and dismissed weaker candidates — the
    requirement is met on the strength of the confirmed link's score."""
    links = [_link("dismissed"), _link("confirmed", 0.9), _link("pending", 0.5)]
    assert status_from_evidence(links) == "met"


def test_a_pending_proposal_survives_a_dismissal_of_a_different_document():
    assert status_from_evidence([_link("dismissed"), _link("pending", 0.65)]) == "partial"


@pytest.mark.parametrize("score", [None, "", "not a number", -1])
def test_an_unreadable_score_is_treated_as_no_evidence(score):
    assert status_from_evidence([{"human_review_status": "pending", "score": score}]) == "gap"


# ── what matching itself may write ─────────────────────────────────────────────

def test_matching_fills_in_partial_for_a_fresh_medium_score_match():
    assert status_after_matching([_link("pending", 0.65)], "unchecked") == "partial"


def test_matching_may_write_met_for_a_high_score_match():
    """The behaviour change: matching is no longer artificially capped at partial — a
    confident, valid-through-closing match now shows as met immediately."""
    assert status_after_matching([_link("pending", 0.9)], "unchecked") == "met"


def test_matching_marks_a_requirement_with_nothing_found_as_a_gap():
    assert status_after_matching([], "unchecked") == "gap"


def test_matching_leaves_confirmed_evidence_alone():
    """Rule 3: a confirmed link is a person's decision — matching does not second-guess it."""
    assert status_after_matching([_link("confirmed")], "unchecked") is None


def test_matching_never_overwrites_a_met_requirement():
    assert status_after_matching([], "met") is None


def test_matching_never_overwrites_a_rejected_requirement():
    """A reviewer has already dismissed every candidate here — matching must not reset that."""
    assert status_after_matching([_link("dismissed")], "rejected") is None


def test_matching_leaves_completed_work_alone():
    assert status_after_matching([], "gap", completion_status="complete") is None


def test_matching_writes_nothing_when_the_status_already_matches():
    assert status_after_matching([_link("pending", 0.65)], "partial") is None
    assert status_after_matching([], "gap") is None


def test_matching_can_move_a_gap_back_to_partial_when_evidence_turns_up():
    assert status_after_matching([_link("pending", 0.65)], "gap") == "partial"


# ── the confirm / dismiss path ─────────────────────────────────────────────────

def _recalc(monkeypatch, links, requirement, actor_email=""):
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
    db.recalculate_requirement_status_from_evidence("REQ-1", actor_email)
    return written


def test_confirming_a_high_score_link_marks_the_requirement_met(monkeypatch):
    """A confirmed link whose score meets the MET threshold takes the requirement to met.
    (The confirmation itself doesn't upgrade — the score does, whether pending or confirmed.)"""
    written = _recalc(monkeypatch, [_link("confirmed", 0.9)], {"status": "partial"})
    assert len(written) == 1
    assert written[0]["status"] == "met"


def test_confirming_a_partial_score_link_keeps_the_requirement_partial(monkeypatch):
    """Behaviour change: confirming is agreement, not an upgrade. A partial-scored link
    stays partial after confirmation. The reviewer's action is captured on the link's
    human_review_status field; the requirement status only follows the score."""
    written = _recalc(monkeypatch, [_link("confirmed", 0.65)], {"status": "partial"})
    assert written == []  # already partial, no status change needed


def test_dismissing_the_last_confirmed_link_leaves_a_rejected(monkeypatch):
    """The reviewer looked and dismissed everything — that's rejected, not unchecked or gap."""
    written = _recalc(monkeypatch, [_link("dismissed")], {"status": "met"})
    assert len(written) == 1
    assert written[0]["status"] == "rejected"


def test_dismissing_one_of_two_proposals_still_updates_the_status(monkeypatch):
    """Nothing confirmed and nothing `met` used to return without writing anything at all."""
    written = _recalc(monkeypatch, [_link("dismissed"), _link("pending", 0.65)],
                      {"status": "unchecked"})
    assert len(written) == 1
    assert written[0]["status"] == "partial"


def test_no_write_when_the_status_is_already_right_and_no_reviewer_stamp(monkeypatch):
    """Idempotent for pipeline retriggers, which have no actor email to stamp."""
    written = _recalc(monkeypatch, [_link("confirmed", 0.9)], {"status": "met"})
    assert written == []


def test_reviewer_email_is_stamped_even_when_status_does_not_change(monkeypatch):
    """The compliance matrix wants to show who reconfirmed a met status, even mid-review."""
    written = _recalc(monkeypatch, [_link("confirmed", 0.9)], {"status": "met"},
                      actor_email="reviewer@example.com")
    assert len(written) == 1
    assert written[0]["status_updated_by"] == "reviewer@example.com"


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
             "match_score": 0.65}
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


def test_a_medium_score_proposed_match_sets_the_requirement_to_partial(matching):
    state, updates = matching

    result = evidence_matching.match("ws-1")

    # status_source marks this as the AI's reading, which is what keeps a later review
    # recompute from overwriting a status a person set by hand.
    assert updates == [("REQ-1", {"status": "partial", "status_source": "ai"})]
    assert result["statuses_set"] == 1


def test_a_high_score_proposed_match_sets_the_requirement_to_met(matching):
    """A confident LLM match with a valid document is now sufficient for `met`. The reviewer
    can still dismiss it — the confirm path still runs."""
    state, updates = matching
    state["match_score"] = 0.9

    evidence_matching.match("ws-1")

    # status_source marks this as the AI's reading, which is what keeps a later review
    # recompute from overwriting a status a person set by hand.
    assert updates == [("REQ-1", {"status": "met", "status_source": "ai"})]


def test_a_requirement_with_nothing_in_the_vault_becomes_a_gap(matching):
    state, updates = matching
    state["candidates"] = []

    evidence_matching.match("ws-1")

    # status_source marks this as the AI's reading, which is what keeps a later review
    # recompute from overwriting a status a person set by hand.
    assert updates == [("REQ-1", {"status": "gap", "status_source": "ai"})]


def test_a_weak_match_leaves_a_gap_rather_than_claiming_partial_cover(matching):
    state, updates = matching
    state["match_score"] = MIN_PROPOSAL_SCORE - 0.1

    evidence_matching.match("ws-1")

    # status_source marks this as the AI's reading, which is what keeps a later review
    # recompute from overwriting a status a person set by hand.
    assert updates == [("REQ-1", {"status": "gap", "status_source": "ai"})]


def test_a_failing_status_write_does_not_lose_the_matching_run(matching, monkeypatch):
    """The evidence link is already saved; the status is not worth the whole run."""
    state, _updates = matching

    def boom(req_id, patch):
        raise RuntimeError("postgrest unreachable")

    monkeypatch.setattr(db, "update_requirement", boom)

    result = evidence_matching.match("ws-1")

    assert result["proposed"] == 1
    assert result["statuses_set"] == 0
