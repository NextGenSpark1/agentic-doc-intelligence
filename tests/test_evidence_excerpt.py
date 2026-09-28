"""What the adjudicator is shown of a candidate document.

The bug this closes, measured on the NexaGrid pack with real embeddings: the audited financial
summary was retrieved first, at 0.800, for the turnover requirement — and the requirement still
came out as a gap. The reason was the excerpt. Retrieval picks the chunk nearest the REQUIREMENT,
which was this one:

    "designed to test a tender requirement for minimum average annual turnover of RM 5,000,000"

a restatement of the requirement carrying no figures. The chunk two away —
"Three-Year Average Annual Revenue: RM 7,166,667" — is the actual proof, and the model never saw
it. It was asked whether the wrong paragraph proved the requirement, and correctly said no.
"""
import pytest

from backend.apps.tendering.pipeline.evidence_matching import (
    _MAX_EXCERPT_CHARS,
    _payload,
    build_excerpt,
)

# The financial summary as the vault holds it, in page order.
FINANCIAL_CHUNKS = [
    {"chunk_id": "f0", "text": "NEXAGRID SYSTEMS SDN. BHD."},
    {"chunk_id": "f1", "text": "SUMMARY OF AUDITED FINANCIAL INFORMATION"},
    {"chunk_id": "f2", "text": "AUDITED REVENUE"},
    {"chunk_id": "f3", "text": "Financial Year 2023: RM 6,100,000"},
    {"chunk_id": "f4", "text": "Three-Year Average Annual Revenue: RM 7,166,667"},
    {"chunk_id": "f5", "text": "DIRECTORS' TEST STATEMENT"},
    {"chunk_id": "f6", "text": "designed to test a tender requirement for minimum average "
                               "annual turnover of RM 5,000,000 over the latest three years"},
    {"chunk_id": "f7", "text": "This is not an audited financial statement."},
]


def test_the_matched_passage_arrives_with_the_proof_beside_it():
    """The whole point: the chunk retrieval picked, plus the figures it sits near."""
    excerpt = build_excerpt(FINANCIAL_CHUNKS, "f6")

    assert "minimum average annual turnover of RM 5,000,000" in excerpt   # what was matched
    assert "RM 7,166,667" in excerpt                                       # what proves it


def test_the_matched_passage_is_always_included():
    for chunk in FINANCIAL_CHUNKS:
        assert chunk["text"][:30] in build_excerpt(FINANCIAL_CHUNKS, chunk["chunk_id"])


def test_context_is_taken_from_both_sides():
    excerpt = build_excerpt(FINANCIAL_CHUNKS, "f4")

    assert "AUDITED REVENUE" in excerpt          # before
    assert "DIRECTORS' TEST STATEMENT" in excerpt  # after


def test_the_budget_is_respected():
    chunks = [{"chunk_id": f"c{i}", "text": "x" * 400} for i in range(20)]

    excerpt = build_excerpt(chunks, "c10", budget=1000)

    assert len(excerpt) <= 1000


def test_a_tight_budget_still_returns_the_match():
    chunks = [{"chunk_id": f"c{i}", "text": "x" * 400} for i in range(5)]

    excerpt = build_excerpt(chunks, "c2", budget=100)

    assert excerpt == "x" * 100      # truncated, but it is the matched chunk


def test_an_unknown_chunk_id_falls_back_to_the_start():
    excerpt = build_excerpt(FINANCIAL_CHUNKS, "not-a-chunk")

    assert excerpt.startswith("NEXAGRID SYSTEMS SDN. BHD.")


@pytest.mark.parametrize("chunks", [[], [{"chunk_id": "c1", "text": "   "}]])
def test_a_document_with_no_text_yields_nothing(chunks):
    assert build_excerpt(chunks, "c1") == ""


def test_blank_chunks_do_not_break_the_ordering():
    chunks = [
        {"chunk_id": "a", "text": "first"},
        {"chunk_id": "b", "text": "   "},
        {"chunk_id": "c", "text": "matched"},
        {"chunk_id": "d", "text": "last"},
    ]

    excerpt = build_excerpt(chunks, "c")

    assert excerpt == "first\nmatched\nlast"


# ── what reaches the prompt ────────────────────────────────────────────────────

def test_the_prompt_uses_the_expanded_excerpt_when_there_is_one():
    candidate = {"supplier_document_id": "SUP-1", "title": "Audited financials",
                 "text": "one lonely chunk", "excerpt": "the passage with its context"}

    payload = _payload({"description": "turnover"}, [candidate])

    assert payload["candidate_documents"][0]["excerpt"] == "the passage with its context"


def test_the_prompt_falls_back_to_the_chunk_when_context_could_not_be_read():
    """A failed chunk read degrades to the old behaviour rather than sending nothing."""
    candidate = {"supplier_document_id": "SUP-1", "title": "Audited financials",
                 "text": "one lonely chunk"}

    payload = _payload({"description": "turnover"}, [candidate])

    assert payload["candidate_documents"][0]["excerpt"] == "one lonely chunk"


def test_the_prompt_excerpt_is_capped():
    candidate = {"supplier_document_id": "SUP-1", "title": "T", "excerpt": "y" * 9_000}

    payload = _payload({"description": "x"}, [candidate])

    assert len(payload["candidate_documents"][0]["excerpt"]) == _MAX_EXCERPT_CHARS
