"""Submission readiness — slice 4's gap analysis and scoring.

Pure logic only: no Supabase, no LLM. The score is arithmetic over database rows, so it is
tested as arithmetic — every point of it must be traceable to a named gap, which is what makes
it defensible to a bid manager who disagrees with it.
"""
from datetime import date

import pytest

from backend.apps.tendering.pipeline.readiness_review import (
    build_report,
    compute_gaps,
    compute_score,
    deterministic_narrative,
    is_satisfied,
    summarise_gaps,
)

TODAY = date(2026, 9, 3)


def _requirement(rid="REQ-1", mandatory=True, status="confirmed", completion="not_started",
                 owner="user-1"):
    return {
        "requirement_id": rid,
        "description": "The bidder shall hold a valid CIDB G7 licence",
        "category": "certification",
        "is_mandatory": mandatory,
        "human_review_status": status,
        "completion_status": completion,
        "owner_id": owner,
    }


def _link(rid="REQ-1", doc="SUP-1", status="confirmed"):
    return {"evidence_link_id": f"EVL-{rid}-{doc}", "requirement_id": rid,
            "supplier_document_id": doc, "human_review_status": status, "match_score": 0.9}


def _vault_doc(doc="SUP-1", expiry=None, superseded=None):
    return {"supplier_document_id": doc, "title": "CIDB Certificate",
            "expiry_date": expiry, "superseded_by": superseded}


def _tender(closing="2026-10-01"):
    return {"tender_id": "TEN-2026-0001", "org_id": "org-1", "closing_date": closing}


def _document(status="done"):
    return {"document_id": "TDOC-1", "filename": "itt.pdf", "extraction_status": status}


def _gap_types(gaps):
    return {g["gap_type"] for g in gaps}


# --------------------------- satisfaction ---------------------------
def test_approved_evidence_satisfies_a_requirement():
    assert is_satisfied(_requirement(), [_link()], {"SUP-1": _vault_doc()}, TODAY) is True


def test_pending_evidence_does_not_satisfy():
    """Rule 3: the AI proposing evidence is not the same as the team having it."""
    assert is_satisfied(_requirement(), [_link(status="pending")],
                        {"SUP-1": _vault_doc()}, TODAY) is False


def test_expired_evidence_does_not_satisfy():
    assert is_satisfied(_requirement(), [_link()],
                        {"SUP-1": _vault_doc(expiry="2026-01-01")}, TODAY) is False


def test_superseded_evidence_does_not_satisfy():
    assert is_satisfied(_requirement(), [_link()],
                        {"SUP-1": _vault_doc(superseded="SUP-2")}, TODAY) is False


def test_manual_completion_satisfies_without_evidence():
    assert is_satisfied(_requirement(completion="complete"), [], {}, TODAY) is True


def test_link_to_a_missing_vault_document_does_not_satisfy():
    assert is_satisfied(_requirement(), [_link(doc="SUP-GONE")], {}, TODAY) is False


# ------------------------------ scoring ------------------------------
def test_score_is_one_when_everything_is_satisfied():
    result = compute_score([_requirement()], [_link()], [_vault_doc()], TODAY)
    assert result["score"] == 1.0
    assert result["mandatory_satisfied"] == 1


def test_score_is_zero_when_nothing_is_satisfied():
    assert compute_score([_requirement()], [], [], TODAY)["score"] == 0.0


def test_mandatory_requirements_weigh_more_than_optional():
    requirements = [_requirement("REQ-1", mandatory=True), _requirement("REQ-2", mandatory=False)]
    vault = [_vault_doc("SUP-1")]

    mandatory_met = compute_score(requirements, [_link("REQ-1")], vault, TODAY)["score"]
    optional_met = compute_score(requirements, [_link("REQ-2")], vault, TODAY)["score"]

    assert mandatory_met == 0.75      # 3 of 4 weight
    assert optional_met == 0.25       # 1 of 4 weight
    assert mandatory_met > optional_met


def test_dismissed_requirements_are_excluded_from_scoring():
    """A dismissed requirement is an explicit decision it does not apply."""
    requirements = [_requirement("REQ-1"), _requirement("REQ-2", status="dismissed")]
    result = compute_score(requirements, [_link("REQ-1")], [_vault_doc()], TODAY)

    assert result["total"] == 1
    assert result["score"] == 1.0


def test_score_of_an_empty_tender_is_zero_not_one():
    """No requirements means unknown, not perfect — an empty tender must never read as ready."""
    result = compute_score([], [], [], TODAY)
    assert result["score"] == 0.0
    assert result["total"] == 0


def test_dismissed_evidence_link_does_not_count():
    result = compute_score([_requirement()], [_link(status="dismissed")], [_vault_doc()], TODAY)
    assert result["score"] == 0.0


# ------------------------------- gaps -------------------------------
def test_unmet_mandatory_requirement_is_a_blocker():
    gaps = compute_gaps(_tender(), [_requirement()], [], [_document()], [], [], TODAY)
    blocker = next(g for g in gaps if g["gap_type"] == "mandatory_requirement_unmet")
    assert blocker["severity"] == "blocker"
    assert blocker["requirement_id"] == "REQ-1"


def test_unmet_optional_requirement_is_only_a_warning():
    gaps = compute_gaps(_tender(), [_requirement(mandatory=False)], [], [_document()], [], [], TODAY)
    gap = next(g for g in gaps if g["gap_type"] == "requirement_unmet")
    assert gap["severity"] == "warning"


def test_evidence_expiring_before_the_closing_date_is_a_blocker():
    """The trap this whole stage exists to catch: valid today, lapsed at evaluation."""
    gaps = compute_gaps(
        _tender(closing="2026-12-01"), [_requirement()], [_link()], [_document()],
        [_vault_doc(expiry="2026-11-01")], [], TODAY,
    )
    gap = next(g for g in gaps if g["gap_type"] == "evidence_expires_before_closing")
    assert gap["severity"] == "blocker"
    assert "2026-11-01" in gap["message"]


def test_evidence_valid_past_the_closing_date_is_not_flagged():
    gaps = compute_gaps(
        _tender(closing="2026-10-01"), [_requirement()], [_link()], [_document()],
        [_vault_doc(expiry="2027-01-01")], [], TODAY,
    )
    assert "evidence_expires_before_closing" not in _gap_types(gaps)
    assert "evidence_expiring_soon" not in _gap_types(gaps)


def test_already_expired_evidence_is_a_blocker():
    gaps = compute_gaps(_tender(), [_requirement()], [_link()], [_document()],
                        [_vault_doc(expiry="2026-01-01")], [], TODAY)
    assert "evidence_expired" in _gap_types(gaps)


def test_evidence_expiring_within_the_warning_window():
    gaps = compute_gaps(_tender(closing="2026-09-10"), [_requirement()], [_link()], [_document()],
                        [_vault_doc(expiry="2026-09-20")], [], TODAY)
    gap = next(g for g in gaps if g["gap_type"] == "evidence_expiring_soon")
    assert gap["severity"] == "warning"


def test_superseded_evidence_still_attached_is_flagged():
    gaps = compute_gaps(_tender(), [_requirement()], [_link()], [_document()],
                        [_vault_doc(superseded="SUP-2")], [], TODAY)
    assert "evidence_superseded" in _gap_types(gaps)


def test_pending_evidence_on_a_mandatory_requirement_blocks():
    gaps = compute_gaps(_tender(), [_requirement()], [_link(status="pending")], [_document()],
                        [_vault_doc()], [], TODAY)
    gap = next(g for g in gaps if g["gap_type"] == "evidence_pending_review")
    assert gap["severity"] == "blocker"


def test_unreviewed_requirement_is_flagged():
    gaps = compute_gaps(_tender(), [_requirement(status="pending")], [_link()], [_document()],
                        [_vault_doc()], [], TODAY)
    assert "requirement_pending_review" in _gap_types(gaps)


def test_passed_closing_date_is_a_blocker():
    gaps = compute_gaps(_tender(closing="2026-08-01"), [_requirement()], [_link()],
                        [_document()], [_vault_doc()], [], TODAY)
    gap = next(g for g in gaps if g["gap_type"] == "closing_date_passed")
    assert gap["severity"] == "blocker"


def test_imminent_closing_date_is_a_warning():
    gaps = compute_gaps(_tender(closing="2026-09-06"), [_requirement()], [_link()],
                        [_document()], [_vault_doc()], [], TODAY)
    assert "closing_date_imminent" in _gap_types(gaps)


def test_missing_closing_date_is_flagged():
    gaps = compute_gaps(_tender(closing=None), [_requirement()], [_link()], [_document()],
                        [_vault_doc()], [], TODAY)
    assert "closing_date_unknown" in _gap_types(gaps)


def test_failed_document_extraction_blocks():
    """A document we could not read may contain a mandatory requirement nobody knows about."""
    gaps = compute_gaps(_tender(), [_requirement()], [_link()], [_document(status="failed")],
                        [_vault_doc()], [], TODAY)
    gap = next(g for g in gaps if g["gap_type"] == "document_not_processed")
    assert gap["severity"] == "blocker"


def test_queued_document_is_a_warning_not_a_blocker():
    gaps = compute_gaps(_tender(), [_requirement()], [_link()], [_document(status="queued")],
                        [_vault_doc()], [], TODAY)
    gap = next(g for g in gaps if g["gap_type"] == "document_not_processed")
    assert gap["severity"] == "warning"


def test_no_documents_and_no_requirements_both_block():
    gaps = compute_gaps(_tender(), [], [], [], [], [], TODAY)
    assert {"no_documents", "no_requirements"} <= _gap_types(gaps)


def test_unassigned_requirement_is_only_informational():
    gaps = compute_gaps(_tender(), [_requirement(owner=None)], [_link()], [_document()],
                        [_vault_doc()], [], TODAY)
    gap = next(g for g in gaps if g["gap_type"] == "requirement_unassigned")
    assert gap["severity"] == "info"


def test_overdue_task_is_flagged():
    tasks = [{"task_id": "TSK-1", "title": "Get bank guarantee", "status": "open",
              "due_date": "2026-08-01"}]
    gaps = compute_gaps(_tender(), [_requirement()], [_link()], [_document()],
                        [_vault_doc()], tasks, TODAY)
    assert "task_overdue" in _gap_types(gaps)


def test_completed_task_is_not_overdue():
    tasks = [{"task_id": "TSK-1", "title": "Done thing", "status": "done",
              "due_date": "2026-08-01"}]
    gaps = compute_gaps(_tender(), [_requirement()], [_link()], [_document()],
                        [_vault_doc()], tasks, TODAY)
    assert "task_overdue" not in _gap_types(gaps)


def test_dismissed_requirement_generates_no_gaps():
    gaps = compute_gaps(_tender(), [_requirement(status="dismissed")], [], [_document()],
                        [], [], TODAY)
    assert "mandatory_requirement_unmet" not in _gap_types(gaps)


# ---------------------------- the report ----------------------------
def test_fully_ready_tender_is_not_blocked():
    report = build_report(_tender(), [_requirement()], [_link()], [_document()],
                          [_vault_doc(expiry="2027-01-01")], [], TODAY)
    assert report["score"] == 1.0
    assert report["submission_blocked"] is False
    assert report["blockers"] == 0


def test_blockers_are_listed_first():
    """The gap list is read top-down under deadline pressure."""
    report = build_report(_tender(), [_requirement(owner=None)], [], [_document()], [], [], TODAY)
    severities = [g["severity"] for g in report["gaps"]]
    assert severities == sorted(severities, key=lambda s: {"blocker": 0, "warning": 1, "info": 2}[s])
    assert report["submission_blocked"] is True


def test_a_high_score_can_still_be_blocked():
    """The central design point: a percentage must never hide a disqualifying gap."""
    requirements = [_requirement(f"REQ-{i}", mandatory=False) for i in range(9)]
    requirements.append(_requirement("REQ-BLOCK", mandatory=True))
    links = [_link(f"REQ-{i}") for i in range(9)]
    vault = [_vault_doc(f"SUP-{i}") for i in range(9)]
    links = [{**l, "supplier_document_id": f"SUP-{i}"} for i, l in enumerate(links)]

    report = build_report(_tender(), requirements, links, [_document()], vault, [], TODAY)

    assert report["score"] == pytest.approx(9 / 12)   # 9 optional of 12 total weight
    assert report["submission_blocked"] is True
    assert report["mandatory_satisfied"] == 0


def test_summarise_gaps_counts_by_severity():
    gaps = [
        {"severity": "blocker", "message": "a", "gap_type": "x"},
        {"severity": "blocker", "message": "b", "gap_type": "y"},
        {"severity": "warning", "message": "c", "gap_type": "z"},
        {"severity": "info", "message": "d", "gap_type": "w"},
    ]
    summary = summarise_gaps(gaps)
    assert (summary["blockers"], summary["warnings"], summary["info"]) == (2, 1, 1)
    assert summary["submission_blocked"] is True
    assert summary["blocking_reasons"] == ["a", "b"]


# --------------------------- the narrative ---------------------------
def test_deterministic_narrative_states_blocked_plainly():
    report = build_report(_tender(), [_requirement()], [], [_document()], [], [], TODAY)
    text = deterministic_narrative(report)

    assert "NOT READY TO SUBMIT" in text
    assert "No evidence attached" in text


def test_deterministic_narrative_does_not_declare_a_bid_ready():
    """Rule 3: no blocking issues is not the same as 'ready to send'."""
    report = build_report(_tender(), [_requirement()], [_link()], [_document()],
                          [_vault_doc(expiry="2027-01-01")], [], TODAY)
    text = deterministic_narrative(report)

    assert "No blocking issues found" in text
    assert "ready to submit" not in text.lower()


def test_narrative_reports_the_mandatory_fraction():
    report = build_report(_tender(), [_requirement()], [_link()], [_document()],
                          [_vault_doc(expiry="2027-01-01")], [], TODAY)
    assert "1 of 1 mandatory" in deterministic_narrative(report)
