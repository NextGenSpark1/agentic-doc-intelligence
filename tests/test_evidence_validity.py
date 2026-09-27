"""Evidence whose validity cannot be checked, and the stage order that made checking impossible.

Both come from the NexaGrid SBMS test pack, whose answer key expects two expiry blockers:

  * E2 — CIDB G7 registration, "must remain valid on the tender closing date". The certificate
    says 20 November 2026 on its face; the tender closes 30 November.
  * E9 — public liability insurance, "the policy must be valid on the tender closing date". That
    policy expired on 31 August 2026.

Neither blocker can appear unless two things are known: when the document expires, and when the
tender closes. The platform reads the first from a field somebody types at upload — never from
the document — and worked out the second only *after* matching had already run.
"""
from datetime import date

import pytest

from backend.apps.tendering.pipeline import readiness_review
from backend.apps.tendering.pipeline.readiness_review import compute_gaps, needs_proof_of_validity

TODAY = date(2026, 9, 25)
CLOSING = "2026-11-30"

CIDB = ("The bidder must hold a valid CIDB Grade G7 registration. The registration must remain "
        "valid on the tender closing date.")
INSURANCE = ("The bidder must hold public liability insurance with coverage of not less than "
             "RM 5,000,000 and the policy must be valid on the tender closing date.")
SSM = ("The bidder must be a company registered with Suruhanjaya Syarikat Malaysia (SSM) and "
       "must submit evidence of active registration.")
PM_CV = ("The proposed Project Manager must have at least seven (7) years of relevant "
         "project-management experience.")


def _requirement(description=CIDB, status="met", mandatory=True):
    return {"req_id": "REQ-1", "description": description, "mandatory": mandatory,
            "status": status, "completion_status": "not_started", "owner": "u-1"}


def _link(status="pending", score=0.85):
    return {"req_id": "REQ-1", "doc_id": "LIB-1", "human_review_status": status, "score": score}


def _library(expiry=None, title="CIDB G7 certificate"):
    return [{"doc_id": "LIB-1", "title": title, "expiry_date": expiry}]


def _gaps(requirement, links, library, closing=CLOSING):
    workspace = {"id": "ws-1", "org_id": "org-1", "closing_date": closing}
    documents = [{"document_id": "D1", "filename": "rfp.pdf", "extraction_status": "done"}]
    return compute_gaps(workspace, [requirement], links, documents, library, TODAY)


def _of_type(gaps, gap_type):
    return [gap for gap in gaps if gap["gap_type"] == gap_type]


# ── which requirements actually care about validity ────────────────────────────

@pytest.mark.parametrize("description", [CIDB, INSURANCE])
def test_a_requirement_demanding_validity_at_the_closing_date_is_recognised(description):
    assert needs_proof_of_validity({"description": description}) is True


@pytest.mark.parametrize("description", [SSM, PM_CV])
def test_a_requirement_that_just_wants_a_document_is_not(description):
    """A CV and a company registration have no expiry; nagging about one would be noise."""
    assert needs_proof_of_validity({"description": description}) is False


def test_the_wording_can_come_from_the_evidence_field_too():
    requirement = {"description": "Hold a CIDB G7 registration.",
                   "required_evidence": "CIDB certificate valid on the closing date"}
    assert needs_proof_of_validity(requirement) is True


# ── an unverifiable certificate is said out loud ───────────────────────────────

def test_a_mandatory_requirement_met_on_a_document_with_no_expiry_blocks():
    """The CIDB case as it stands today: nobody typed the date, so `met` rests on nothing."""
    gaps = _gaps(_requirement(), [_link()], _library(expiry=None))

    unknown = _of_type(gaps, "evidence_validity_unknown")
    assert len(unknown) == 1
    assert unknown[0]["severity"] == "blocker"
    assert "No expiry date recorded" in unknown[0]["message"]


def test_the_same_document_on_a_requirement_that_does_not_need_validity_says_nothing():
    gaps = _gaps(_requirement(description=PM_CV), [_link()], _library(expiry=None, title="PM CV"))

    assert _of_type(gaps, "evidence_validity_unknown") == []


def test_an_unmet_requirement_only_warns():
    """It already has its own gap; an unverifiable proposal should not block on top of that."""
    gaps = _gaps(_requirement(status="partial"), [_link()], _library(expiry=None))

    assert _of_type(gaps, "evidence_validity_unknown")[0]["severity"] == "warning"


def test_an_expired_document_on_an_unmet_mandatory_requirement_still_blocks():
    """The E9 case. The requirement is unmet either way, but "the policy expired on 31 August" is
    the line that says what to do about it, so it cannot rank below the generic gap as a warning."""
    gaps = _gaps(_requirement(description=INSURANCE, status="gap"), [_link()],
                 _library(expiry="2026-08-31", title="Public liability insurance"))

    assert _of_type(gaps, "evidence_expired")[0]["severity"] == "blocker"


def test_an_expired_document_on_an_optional_requirement_only_warns():
    """Old proposals attached to optional requirements must not block a submission."""
    gaps = _gaps(_requirement(description=INSURANCE, status="gap", mandatory=False), [_link()],
                 _library(expiry="2026-08-31", title="Public liability insurance"))

    assert _of_type(gaps, "evidence_expired")[0]["severity"] == "warning"


def test_a_recorded_expiry_reports_the_real_problem_instead():
    """Once the date is known, the specific gap replaces the "cannot confirm" one."""
    gaps = _gaps(_requirement(), [_link()], _library(expiry="2026-11-20"))

    assert _of_type(gaps, "evidence_validity_unknown") == []
    assert _of_type(gaps, "evidence_expires_before_closing")[0]["severity"] == "blocker"


def test_two_undated_documents_on_one_requirement_report_once():
    links = [_link(), {**_link(), "doc_id": "LIB-2"}]
    library = _library(expiry=None) + [{"doc_id": "LIB-2", "title": "Second cert",
                                        "expiry_date": None}]

    assert len(_of_type(_gaps(_requirement(), links, library), "evidence_validity_unknown")) == 1


def test_a_dismissed_undated_document_is_ignored():
    gaps = _gaps(_requirement(status="rejected"), [_link(status="dismissed")],
                 _library(expiry=None))

    assert _of_type(gaps, "evidence_validity_unknown") == []


# ── the stage order that made the closing date unknowable ──────────────────────

def test_matching_runs_after_the_summary_that_finds_the_closing_date(monkeypatch):
    """Matching's expiry caps compare against the workspace closing date, and summarise is what
    fills it in. Run in the old order, the caps had nothing to compare against on a first
    analysis and an expiring certificate came back looking like proof."""
    from backend.apps.tendering import db
    from backend.apps.tendering.pipeline import (
        evidence_matching, extract_requirements, readiness_review as review, summarise_tender,
    )
    import backend.apps.tendering.pipeline as pipeline

    order: list[str] = []
    monkeypatch.setattr(db, "write_workspace_audit", lambda *a, **k: None)
    monkeypatch.setattr(extract_requirements, "extract",
                        lambda ws: order.append("extract") or {})
    monkeypatch.setattr(summarise_tender, "summarise",
                        lambda ws: order.append("summarise") or {})
    monkeypatch.setattr(evidence_matching, "match", lambda ws: order.append("match") or {})
    monkeypatch.setattr(review, "review", lambda ws: order.append("readiness") or {})

    result = pipeline.run_workspace_analysis("ws-1")

    assert order == ["extract", "summarise", "match", "readiness"]
    assert result["stages_run"] == ["extract_requirements", "summarise_tender",
                                    "evidence_matching", "readiness_review"]


def test_a_failing_match_still_leaves_the_readiness_review_to_run(monkeypatch):
    from backend.apps.tendering import db
    from backend.apps.tendering.pipeline import (
        evidence_matching, extract_requirements, readiness_review as review, summarise_tender,
    )
    import backend.apps.tendering.pipeline as pipeline

    order: list[str] = []
    monkeypatch.setattr(db, "write_workspace_audit", lambda *a, **k: None)
    monkeypatch.setattr(extract_requirements, "extract", lambda ws: {})
    monkeypatch.setattr(summarise_tender, "summarise", lambda ws: order.append("summarise") or {})
    monkeypatch.setattr(review, "review", lambda ws: order.append("readiness") or {})

    def boom(_ws):
        raise RuntimeError("vault unreachable")

    monkeypatch.setattr(evidence_matching, "match", boom)

    pipeline.run_workspace_analysis("ws-1")

    assert order == ["summarise", "readiness"]
