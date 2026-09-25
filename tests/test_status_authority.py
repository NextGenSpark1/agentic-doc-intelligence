"""Who gets the last word on a requirement's status, and when expiry is allowed to stay quiet.

Three defects found reviewing the AI-sets-status work, all of them cases where the system and a
reviewer disagreed and the wrong one won:

  1. A requirement `met` from a PENDING proposal produced no expiry gap at all, because the gap
     loop only looked at confirmed links. Matching runs before summarise fills in the closing
     date, so the score cap that would have prevented that `met` usually cannot apply — the
     workspace read 100% ready on a certificate that lapses before evaluation.
  2. Confirming a proposal scored below the partial floor set the requirement to `gap`: the
     reviewer's positive action left the matrix reading as if no evidence existed.
  3. The same recompute overwrote a status a person had set by hand, because a review stamps
     `status_updated_by` too and nothing distinguished the two.
"""
from datetime import date

import pytest

from backend.apps.tendering import db
from backend.apps.tendering.pipeline.readiness_review import compute_gaps
from backend.apps.tendering.status_rules import status_from_evidence

TODAY = date(2026, 9, 25)


def _requirement(status="met", **overrides):
    requirement = {"req_id": "REQ-1", "description": "Hold a valid CIDB G7 licence",
                   "mandatory": True, "status": status, "completion_status": "not_started",
                   "owner": "u-1"}
    requirement.update(overrides)
    return requirement


def _link(status="pending", score=0.82, doc="LIB-1"):
    return {"req_id": "REQ-1", "doc_id": doc, "human_review_status": status, "score": score}


def _library(expiry):
    return [{"doc_id": "LIB-1", "title": "CIDB G7 certificate", "expiry_date": expiry}]


def _documents():
    return [{"document_id": "D1", "filename": "itt.pdf", "extraction_status": "done"}]


def _gaps(requirement, links, library, closing="2026-12-01"):
    workspace = {"id": "ws-1", "org_id": "org-1", "closing_date": closing}
    return compute_gaps(workspace, [requirement], links, _documents(), library, TODAY)


def _types(gaps):
    return {gap["gap_type"] for gap in gaps}


def _blockers(gaps):
    return [gap["gap_type"] for gap in gaps if gap["severity"] == "blocker"]


# ── 1. expiry on the evidence a `met` actually rests on ────────────────────────

def test_a_met_requirement_on_a_pending_link_still_raises_the_expiry_blocker():
    """The headline bug: satisfied, scored, and silent about a certificate that lapses first."""
    gaps = _gaps(_requirement("met"), [_link("pending")], _library("2026-10-15"))

    assert "evidence_expires_before_closing" in _types(gaps)
    assert _blockers(gaps) == ["evidence_expires_before_closing"]


def test_a_confirmed_link_still_raises_it_too():
    gaps = _gaps(_requirement("met"), [_link("confirmed")], _library("2026-10-15"))

    assert "evidence_expires_before_closing" in _blockers(gaps)


def test_an_already_expired_document_behind_a_met_requirement_blocks():
    gaps = _gaps(_requirement("met"), [_link("pending")], _library("2026-01-01"))

    assert "evidence_expired" in _types(gaps)


def test_a_stale_proposal_on_an_unmet_requirement_warns_rather_than_blocks():
    """The requirement already has its own gap; a rejected-looking proposal must not add a
    second blocker on top, or every workspace with old suggestions reads as unsubmittable."""
    gaps = _gaps(_requirement("gap", mandatory=False), [_link("pending", score=0.5)],
                 _library("2026-01-01"))

    assert "evidence_expired" in _types(gaps)
    assert "evidence_expired" not in _blockers(gaps)


def test_a_dismissed_link_is_still_ignored():
    """A reviewer rejected this document — its expiry is no longer anybody's problem."""
    gaps = _gaps(_requirement("gap"), [_link("dismissed")], _library("2026-01-01"))

    assert "evidence_expired" not in _types(gaps)


def test_evidence_valid_past_the_closing_date_raises_nothing():
    gaps = _gaps(_requirement("met"), [_link("pending")], _library("2027-06-01"))

    assert not _types(gaps) & {"evidence_expired", "evidence_expires_before_closing",
                               "evidence_expiring_soon"}


# ── 2. confirming evidence must never downgrade ────────────────────────────────

@pytest.mark.parametrize("score", [0.41, 0.55, 0.59])
def test_confirming_a_weak_proposal_makes_it_partial_not_a_gap(score):
    """A person vouched for the document. Whatever the model scored it, that is not `gap`."""
    assert status_from_evidence([{"human_review_status": "confirmed", "score": score}]) == "partial"


def test_confirming_a_strong_proposal_still_reaches_met():
    assert status_from_evidence([{"human_review_status": "confirmed", "score": 0.9}]) == "met"


def test_a_confirmed_weak_link_outranks_a_dismissed_strong_one():
    links = [{"human_review_status": "dismissed", "score": 0.95},
             {"human_review_status": "confirmed", "score": 0.5}]
    assert status_from_evidence(links) == "partial"


def test_a_pending_weak_proposal_is_still_only_a_gap():
    """Nobody has vouched for it yet, so nothing has changed for the unreviewed case."""
    assert status_from_evidence([{"human_review_status": "pending", "score": 0.5}]) == "gap"


def test_all_dismissed_is_still_rejected():
    assert status_from_evidence([{"human_review_status": "dismissed", "score": 0.9}]) == "rejected"


# ── 3. a status a person set is not recomputed ─────────────────────────────────

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


def test_a_manually_set_status_survives_a_review_of_its_links(monkeypatch):
    """Reviewing a link says something about the link, not about someone's own decision."""
    written = _recalc(
        monkeypatch,
        [{"human_review_status": "confirmed", "score": 0.5}],
        {"status": "met", "status_source": "manual"},
        actor_email="reviewer@x.com",
    )

    assert written == []


def test_a_manual_gap_is_not_upgraded_by_a_strong_proposal(monkeypatch):
    written = _recalc(
        monkeypatch,
        [{"human_review_status": "confirmed", "score": 0.95}],
        {"status": "gap", "status_source": "manual"},
    )

    assert written == []


def test_an_ai_set_status_is_still_recomputed(monkeypatch):
    written = _recalc(
        monkeypatch,
        [{"human_review_status": "dismissed", "score": 0.9}],
        {"status": "met", "status_source": "ai"},
        actor_email="reviewer@x.com",
    )

    assert written[0]["status"] == "rejected"
    assert written[0]["status_source"] == "review"
    assert written[0]["status_updated_by"] == "reviewer@x.com"


def test_a_status_with_no_recorded_source_is_still_recomputed(monkeypatch):
    """Rows that predate the column must keep working rather than freezing in place."""
    written = _recalc(monkeypatch, [{"human_review_status": "confirmed", "score": 0.9}],
                      {"status": "partial"})

    assert written[0]["status"] == "met"


def test_matching_leaves_a_manually_set_status_alone(monkeypatch):
    """The other writer of statuses has to respect the same boundary."""
    from backend.apps.tendering.pipeline import evidence_matching

    updates: list[tuple] = []
    monkeypatch.setattr(db, "update_requirement",
                        lambda req_id, patch: updates.append((req_id, patch)))

    written = evidence_matching._apply_status(
        _requirement("gap", status_source="manual"),
        [{"human_review_status": "pending", "score": 0.95}],
    )

    assert (written, updates) == (0, [])


def test_matching_tags_its_own_writes_as_ai(monkeypatch):
    from backend.apps.tendering.pipeline import evidence_matching

    updates: list[tuple] = []
    monkeypatch.setattr(db, "update_requirement",
                        lambda req_id, patch: updates.append((req_id, patch)))

    evidence_matching._apply_status(_requirement("unchecked"),
                                    [{"human_review_status": "pending", "score": 0.95}])

    assert updates == [("REQ-1", {"status": "met", "status_source": "ai"})]
