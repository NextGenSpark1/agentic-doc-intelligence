"""Evidence matching — slice 3's retrieval and adjudication logic.

Pure logic only: no Supabase, no LLM, no embeddings. These are the highest-stakes tests in the
tendering product — a wrong evidence match means a company submits the wrong certificate and is
disqualified — so the grounding and conservatism tests carry the weight here.
"""
from datetime import date

import pytest

from backend.apps.tendering.pipeline.evidence_matching import (
    _match_query,
    extract_keywords,
    is_expired,
    merge_candidates,
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
    assert validate_matches(raw, index)[0]["score"] == 1.0


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


# ------------------- keyword extraction (the second retrieval pass) -------------------
def test_acronyms_and_grade_codes_are_picked_up_as_keywords():
    """The failure mode this pass exists for: 'SSM' and 'CIDB G7' embed nowhere near
    a capability statement that contains those exact strings."""
    keywords = extract_keywords({
        "description": "The bidder shall be a Malaysian company with SSM registration.",
        "required_evidence": "Valid CIDB G7 registration certificate",
    })

    assert "SSM" in keywords
    assert "CIDB" in keywords
    assert "G7" in keywords


def test_quoted_phrases_win_over_word_frequency():
    keywords = extract_keywords({
        "description": 'The bidder must hold a valid "ISO/IEC 27001" certification.',
    })
    assert "ISO/IEC 27001" in keywords[:2]


def test_common_english_words_are_dropped():
    """`the`, `shall`, `certificate` and other high-frequency vault-noise words are stopwords —
    otherwise the keyword pass returns every document in the vault."""
    keywords = extract_keywords({
        "description": "The bidder shall provide a certificate.",
        "required_evidence": "",
    })
    assert "shall" not in [k.lower() for k in keywords]
    assert "certificate" not in [k.lower() for k in keywords]


def test_keyword_extraction_is_capped():
    """Long requirement descriptions can produce a huge keyword list; the SQL RPC uses
    ILIKE per keyword so an unbounded list would be a performance foot-gun."""
    text = " ".join([f"KEYWORD{i}" for i in range(50)])
    keywords = extract_keywords({"description": text})
    assert len(keywords) <= 8


def test_empty_requirement_yields_no_keywords():
    assert extract_keywords({}) == []


# ------------------- merging vector + keyword retrieval passes -------------------
def test_documents_unique_to_one_pass_are_kept():
    vector = [_candidate("SUP-1", similarity=0.6)]
    keyword = [_candidate("SUP-2", similarity=0.5)]
    merged = merge_candidates(vector, keyword)

    assert {c["supplier_document_id"] for c in merged} == {"SUP-1", "SUP-2"}


def test_documents_hit_by_both_passes_get_a_boost():
    """A document that shows up in both retrieval passes is stronger evidence — the vault
    knows about it and the requirement's keywords hit it. The merged score reflects that so
    it survives shortlisting."""
    vector = [_candidate("SUP-1", similarity=0.4)]
    keyword = [_candidate("SUP-1", similarity=0.7)]
    merged = merge_candidates(vector, keyword)

    assert len(merged) == 1
    assert merged[0]["similarity"] > 0.7  # boost above the higher of the two


def test_merge_survives_malformed_similarity_values():
    vector = [{**_candidate("SUP-1"), "similarity": "not a number"}]
    keyword = [_candidate("SUP-1", similarity=0.6)]
    merged = merge_candidates(vector, keyword)

    assert len(merged) == 1


def test_keyword_only_hits_survive_the_similarity_floor():
    """The regression this test guards: keyword-pass rows were filtered by the same 0.35
    cosine cutoff as vector rows, but keyword score = matched/total keywords. A document that
    contains the exact SSM registration number could score 2/8 = 0.25 and be dropped before
    the LLM ever saw it. Now, rows tagged as coming from the keyword pass bypass the floor."""
    keyword_only = _candidate("SUP-1", similarity=0.25)
    merged = merge_candidates([], [keyword_only])
    kept = shortlist_candidates(merged, min_similarity=0.35)

    assert [c["supplier_document_id"] for c in kept] == ["SUP-1"]


def test_vector_only_hit_still_respects_similarity_floor():
    """Complement of the previous test: for vector-only hits a low cosine really is a signal
    that the document is not relevant, so the floor still applies."""
    vector_only = _candidate("SUP-1", similarity=0.25)
    merged = merge_candidates([vector_only], [])
    kept = shortlist_candidates(merged, min_similarity=0.35)

    assert kept == []


def test_merge_keeps_the_best_chunk_when_a_doc_has_many():
    """The regression this test guards: the old merge did `merged[doc_id] = row` in a loop, so
    a document's LAST chunk overwrote its best chunk. Vector search returns best-first, so we
    were systematically feeding the adjudicator the worst excerpt from each document — that
    caused false "cert found but excerpt doesn't show scope"-style negatives on documents we
    had actually retrieved correctly."""
    vector = [
        _candidate("SUP-1", similarity=0.82, chunk_id="scope-chunk",
                   text="Scope of certification: design, supply, installation of BMS."),
        _candidate("SUP-1", similarity=0.69, chunk_id="dates-chunk",
                   text="Certificate issued 2024-01-15, valid until 2027-01-14."),
        _candidate("SUP-1", similarity=0.48, chunk_id="header-chunk",
                   text="ISO 9001 Certificate — Registration No. 12345."),
    ]
    merged = merge_candidates(vector, [])

    assert len(merged) == 1
    assert merged[0]["chunk_id"] == "scope-chunk"
