"""Evidence matching — slice 3's retrieval and adjudication logic.

Pure logic only: no Supabase, no LLM, no embeddings. These are the highest-stakes tests in the
tendering product — a wrong evidence match means a company submits the wrong certificate and is
disqualified — so the grounding and conservatism tests carry the weight here.
"""
from datetime import date

import pytest

from backend.apps.tendering.pipeline.evidence_matching import (
    _match_query,
    is_expired,
    shortlist_candidates,
    validate_matches,
)


def _candidate(doc_id="SUP-1", similarity=0.8, chunk_id="vc-1", title="CIDB Certificate",
               text="CIDB Grade G7 registration, valid until 2027."):
    return {
        "supplier_document_id": doc_id,
        "chunk_id": chunk_id,
        "text": text,
        "title": title,
        "doc_type": "certificate",
        "similarity": similarity,
    }


# --------------------------- shortlisting ---------------------------
def test_weak_matches_are_dropped_before_the_llm_is_asked():
    rows = [_candidate("SUP-1", 0.9), _candidate("SUP-2", 0.1)]
    kept = shortlist_candidates(rows)

    assert [c["supplier_document_id"] for c in kept] == ["SUP-1"]


def test_candidates_are_ranked_by_similarity():
    rows = [_candidate("SUP-1", 0.5), _candidate("SUP-2", 0.9), _candidate("SUP-3", 0.7)]
    assert [c["supplier_document_id"] for c in shortlist_candidates(rows)] == \
        ["SUP-2", "SUP-3", "SUP-1"]


def test_only_the_best_excerpt_per_document_survives():
    """Five excerpts from one certificate is one piece of evidence, not five."""
    rows = [
        _candidate("SUP-1", 0.6, chunk_id="vc-1"),
        _candidate("SUP-1", 0.9, chunk_id="vc-2"),
        _candidate("SUP-1", 0.7, chunk_id="vc-3"),
        _candidate("SUP-2", 0.5, chunk_id="vc-9"),
    ]
    kept = shortlist_candidates(rows)

    assert len(kept) == 2
    best = next(c for c in kept if c["supplier_document_id"] == "SUP-1")
    assert best["chunk_id"] == "vc-2"   # the strongest excerpt represents the document


def test_shortlist_is_capped():
    rows = [_candidate(f"SUP-{i}", 0.9) for i in range(20)]
    assert len(shortlist_candidates(rows)) <= 6


def test_malformed_similarity_is_skipped_not_crashed():
    rows = [_candidate("SUP-1", "not a number"), _candidate("SUP-2", 0.9)]
    assert [c["supplier_document_id"] for c in shortlist_candidates(rows)] == ["SUP-2"]


def test_candidate_without_a_document_id_is_skipped():
    assert shortlist_candidates([{**_candidate(), "supplier_document_id": ""}]) == []


def test_empty_retrieval_yields_empty_shortlist():
    assert shortlist_candidates([]) == []


# ------------------- grounding guardrail (the critical one) -------------------
def test_match_citing_an_unoffered_document_is_dropped():
    """The model named a vault document that was never a candidate."""
    index = {"SUP-1": _candidate("SUP-1")}
    raw = {"matches": [{"supplier_document_id": "SUP-INVENTED", "match_score": 0.95,
                        "rationale": "looks right"}]}
    assert validate_matches(raw, index) == []


def test_grounded_match_is_kept_with_our_chunk_id():
    index = {"SUP-1": _candidate("SUP-1", chunk_id="vc-7")}
    raw = {"matches": [{"supplier_document_id": "SUP-1", "match_score": 0.9,
                        "rationale": "Certificate states Grade G7, requirement asks for G7."}]}
    kept = validate_matches(raw, index)

    assert len(kept) == 1
    assert kept[0]["matched_chunk_id"] == "vc-7"   # from OUR candidate row
    assert kept[0]["source"] == "llm"


def test_match_without_a_rationale_is_dropped():
    """Rule 2 for matching: a proposal a bidder cannot justify must not be persisted."""
    index = {"SUP-1": _candidate("SUP-1")}
    raw = {"matches": [{"supplier_document_id": "SUP-1", "match_score": 0.9, "rationale": "   "}]}
    assert validate_matches(raw, index) == []


def test_low_confidence_match_is_dropped():
    index = {"SUP-1": _candidate("SUP-1")}
    raw = {"matches": [{"supplier_document_id": "SUP-1", "match_score": 0.1,
                        "rationale": "vaguely related"}]}
    assert validate_matches(raw, index) == []


def test_match_score_is_clamped():
    index = {"SUP-1": _candidate("SUP-1")}
    raw = {"matches": [{"supplier_document_id": "SUP-1", "match_score": 3.0,
                        "rationale": "exact match"}]}
    assert validate_matches(raw, index)[0]["match_score"] == 1.0


def test_unparseable_score_is_dropped_not_defaulted():
    """A score we cannot read must not become a confident-looking default."""
    index = {"SUP-1": _candidate("SUP-1")}
    raw = {"matches": [{"supplier_document_id": "SUP-1", "match_score": "very high",
                        "rationale": "exact match"}]}
    assert validate_matches(raw, index) == []


def test_duplicate_document_proposals_collapse_to_one():
    index = {"SUP-1": _candidate("SUP-1")}
    raw = {"matches": [
        {"supplier_document_id": "SUP-1", "match_score": 0.9, "rationale": "first"},
        {"supplier_document_id": "SUP-1", "match_score": 0.8, "rationale": "second"},
    ]}
    kept = validate_matches(raw, index)
    assert len(kept) == 1
    assert kept[0]["rationale"] == "first"


def test_empty_matches_is_a_valid_answer():
    """'You have a gap' is correct and useful — it must not be treated as a failure."""
    assert validate_matches({"matches": []}, {"SUP-1": _candidate()}) == []


@pytest.mark.parametrize("raw", [None, [], "text", {}, {"matches": "not a list"},
                                 {"matches": [None, 3]}])
def test_malformed_llm_output_yields_nothing(raw):
    assert validate_matches(raw, {"SUP-1": _candidate()}) == []


# ----------------------------- expiry -----------------------------
def test_expired_document_is_detected():
    assert is_expired({"expiry_date": "2026-01-01"}, today=date(2026, 9, 3)) is True


def test_valid_document_is_not_expired():
    assert is_expired({"expiry_date": "2027-01-01"}, today=date(2026, 9, 3)) is False


def test_document_with_no_expiry_never_expires():
    assert is_expired({}, today=date(2026, 9, 3)) is False
    assert is_expired({"expiry_date": None}, today=date(2026, 9, 3)) is False


def test_expiry_on_the_day_itself_is_still_valid():
    assert is_expired({"expiry_date": "2026-09-03"}, today=date(2026, 9, 3)) is False


def test_unparseable_expiry_is_treated_as_not_expired():
    """Fail open here: the SQL layer already excludes expired documents, and wrongly hiding a
    valid certificate is a worse failure than showing one a human will check."""
    assert is_expired({"expiry_date": "whenever"}, today=date(2026, 9, 3)) is False


def test_timestamp_expiry_is_parsed():
    assert is_expired({"expiry_date": "2026-01-01T00:00:00+00:00"}, today=date(2026, 9, 3)) is True


# --------------------------- the match query ---------------------------
def test_required_evidence_leads_the_query():
    """`required_evidence` names the document sought; `description` states the obligation.
    When the tender gives the former it is the far better retrieval query."""
    query = _match_query({
        "description": "The bidder shall be registered with CIDB at the appropriate grade.",
        "required_evidence": "Valid CIDB G7 registration certificate",
    })
    assert query.startswith("Valid CIDB G7 registration certificate")
    assert "registered with CIDB" in query


def test_query_falls_back_to_description_alone():
    query = _match_query({"description": "Provide audited accounts", "required_evidence": None})
    assert query == "Provide audited accounts"


def test_empty_requirement_yields_empty_query():
    assert _match_query({}) == ""
