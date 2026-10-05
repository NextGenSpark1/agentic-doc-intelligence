"""The adjudicator answers with a verdict; the score comes from the bands, not from the model.

The bug this closes: the prompt told the model to score partial evidence "below 0.5", while a
`partial` requirement needed 0.6 and anything under 0.4 was thrown away. Following its own
instructions the model could never produce a partial requirement — on the NexaGrid run that was
11 met / 4 partial / 32 gap, with every partial in the answer key landing as a gap. The prompt and
the thresholds had been written separately, and nothing tied them together.
"""
from datetime import date

import pytest

from backend.apps.tendering.pipeline import evidence_matching
from backend.apps.tendering.pipeline.evidence_matching import validate_matches
from backend.apps.tendering.status_rules import (
    MET_SCORE_THRESHOLD,
    MIN_EVIDENCE_SCORE,
    MIN_PROPOSAL_SCORE,
    PARTIALLY_PROVES,
    PROVES,
    RELATED_ONLY,
    VERDICT_SCORES,
    status_from_evidence,
)

CANDIDATES = {"SUP-1": {"supplier_document_id": "SUP-1", "library_doc_id": "LIB-1",
                        "chunk_id": "c1", "text": "evidence", "expiry_date": None}}


def _answer(**item):
    return {"matches": [{"supplier_document_id": "SUP-1", "rationale": "Because.", **item}]}


def _kept(item, candidates=CANDIDATES, **kwargs):
    drops: dict = {}
    kept = validate_matches(_answer(**item), candidates, drops=drops, **kwargs)
    return kept, drops


# ── every verdict lands in its band, whatever the thresholds are ──────────────

@pytest.mark.parametrize("verdict,status", [
    (PROVES, "met"),
    (PARTIALLY_PROVES, "partial"),
    (RELATED_ONLY, "gap"),
])
def test_each_verdict_produces_the_status_it_names(verdict, status):
    score = VERDICT_SCORES[verdict]
    assert status_from_evidence([{"human_review_status": "pending", "score": score}]) == status


def test_verdict_scores_sit_strictly_inside_their_bands():
    """The guard for whoever moves a threshold next: the scores are derived, so they follow."""
    assert MET_SCORE_THRESHOLD < VERDICT_SCORES[PROVES] <= 1.0
    assert MIN_PROPOSAL_SCORE < VERDICT_SCORES[PARTIALLY_PROVES] < MET_SCORE_THRESHOLD
    assert MIN_EVIDENCE_SCORE < VERDICT_SCORES[RELATED_ONLY] < MIN_PROPOSAL_SCORE


def test_partial_evidence_is_now_reachable_end_to_end():
    """The exact failure: a model saying "partially proves" must yield a partial requirement."""
    kept, drops = _kept({"verdict": "partially_proves"})

    assert drops == {}
    status = status_from_evidence([{"human_review_status": "pending", "score": kept[0]["score"]}])
    assert status == "partial"


def test_related_evidence_is_kept_for_the_reviewer_but_does_not_cover():
    kept, _ = _kept({"verdict": "related_only"})

    assert kept[0]["verdict"] == RELATED_ONLY
    assert status_from_evidence([{"human_review_status": "pending",
                                  "score": kept[0]["score"]}]) == "gap"


# ── reading the verdict ────────────────────────────────────────────────────────

@pytest.mark.parametrize("spelling,expected", [
    ("proves", PROVES),
    ("Proves", PROVES),
    ("partially proves", PARTIALLY_PROVES),
    ("partially-proves", PARTIALLY_PROVES),
    ("partial", PARTIALLY_PROVES),
    ("related", RELATED_ONLY),
])
def test_the_usual_spellings_are_understood(spelling, expected):
    kept, _ = _kept({"verdict": spelling})
    assert kept[0]["verdict"] == expected


def test_the_verdict_wins_over_a_contradicting_number():
    """The point of the change: the model's decimal no longer decides the band."""
    kept, _ = _kept({"verdict": "partially_proves", "match_score": 0.2})
    assert kept[0]["score"] == VERDICT_SCORES[PARTIALLY_PROVES]


@pytest.mark.parametrize("verdict", ["does_not_prove", "not_related", "none"])
def test_a_verdict_of_no_evidence_is_dropped_under_its_own_reason(verdict):
    kept, drops = _kept({"verdict": verdict})
    assert kept == []
    assert drops == {"judged_not_evidence": 1}


def test_an_unknown_verdict_is_dropped_and_named():
    kept, drops = _kept({"verdict": "probably"})
    assert kept == []
    assert drops == {"unknown_verdict": 1}


def test_an_answer_with_neither_verdict_nor_score_is_dropped():
    kept, drops = _kept({})
    assert kept == []
    assert drops == {"no_verdict": 1}


def test_a_bare_decimal_still_works_for_a_model_that_ignores_the_contract():
    kept, _ = _kept({"match_score": 0.9})
    assert kept[0]["score"] == 0.9
    assert kept[0]["verdict"] is None      # counted by the run as numeric_score


# ── validity caps, now in verdict terms ────────────────────────────────────────

def _candidates_expiring(expiry):
    return {"SUP-1": {**CANDIDATES["SUP-1"], "expiry_date": expiry}}


def test_a_proving_document_that_lapses_before_closing_can_only_partially_prove():
    """The CIDB case: right document, strong content, invalid at submission."""
    kept, _ = _kept({"verdict": "proves"}, candidates=_candidates_expiring("2026-11-20"),
                    closing_date=date(2026, 11, 30), today=date(2026, 10, 5))

    assert kept[0]["score"] == VERDICT_SCORES[PARTIALLY_PROVES]
    assert kept[0]["expires_before_closing"] is True


def test_a_proving_document_that_has_already_lapsed_is_only_related():
    """The insurance case: shown to the reviewer with the reason, never counted."""
    kept, _ = _kept({"verdict": "proves"}, candidates=_candidates_expiring("2026-08-31"),
                    closing_date=date(2026, 11, 30), today=date(2026, 10, 5))

    assert kept[0]["score"] == VERDICT_SCORES[RELATED_ONLY]
    assert kept[0]["already_expired"] is True


# ── the run reports how the model answered ─────────────────────────────────────

def test_the_run_counts_verdicts_and_spots_bare_decimals(monkeypatch):
    from backend.apps.tendering import db
    from backend.core import llm, llm_reasoning

    requirements = [{"req_id": f"R{i}", "description": f"requirement {i}"} for i in range(3)]
    answers = iter([
        {"matches": [{"supplier_document_id": "SUP-1", "verdict": "proves", "rationale": "a"}]},
        {"matches": [{"supplier_document_id": "SUP-1", "verdict": "partial", "rationale": "b"}]},
        {"matches": [{"supplier_document_id": "SUP-1", "match_score": 0.9, "rationale": "c"}]},
    ])
    monkeypatch.setattr(db, "get_tendering_workspace", lambda ws: {"id": ws, "org_id": "org-1"})
    monkeypatch.setattr(db, "list_workspace_requirements_raw", lambda ws: requirements)
    monkeypatch.setattr(db, "list_evidence_links", lambda ws: [])
    monkeypatch.setattr(db, "list_supplier_chunks", lambda sid: [])
    monkeypatch.setattr(db, "write_workspace_audit", lambda *a, **k: None)
    monkeypatch.setattr(db, "update_requirement", lambda *a, **k: None)
    monkeypatch.setattr(db, "upsert_evidence_link", lambda row: row)
    monkeypatch.setattr(db, "match_supplier_docs", lambda *a, **k: [
        {"supplier_document_id": "SUP-1", "library_doc_id": "LIB-1", "chunk_id": "c1",
         "text": "evidence", "similarity": 0.9}])
    monkeypatch.setattr(db, "match_supplier_docs_by_keyword", lambda *a, **k: [])
    monkeypatch.setattr(llm, "embed", lambda texts: [[0.1] * 4 for _ in texts])
    monkeypatch.setattr(llm_reasoning, "ask", lambda *a, **k: next(answers))

    result = evidence_matching.match("ws-1")

    assert result["verdicts"] == {PROVES: 1, PARTIALLY_PROVES: 1, "numeric_score": 1}
