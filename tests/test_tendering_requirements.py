"""Requirement extraction + tender summary — the slice-2 stages.

Pure logic only: no Supabase, no LLM. The grounding tests are the important ones — they check
that an ungrounded requirement is discarded before persistence rather than merely discouraged
by the prompt.
"""
import pytest

from backend.apps.tendering.pipeline.extract_requirements import (
    _BATCH_CHAR_BUDGET,
    _MAX_CHUNK_CHARS,
    _batch,
    _categorise,
    compute_rule_requirements,
    merge,
    validate_llm_requirements,
)
from backend.apps.tendering.pipeline.summarise_tender import (
    _backfill_from_llm_meta,
    _deterministic_summary,
    compute_facts,
    days_until,
)

from datetime import date


def _chunk(chunk_id="ch-1", text="", page=1, document_id="doc-1"):
    return {"chunk_id": chunk_id, "text": text, "page": page, "document_id": document_id}


# --------------------------- rule pass ---------------------------
def test_rule_pass_extracts_bidder_obligations():
    chunks = [_chunk(text="The bidder shall submit a bid bond of 2.5% of the tender sum.")]
    rows = compute_rule_requirements(chunks)

    assert len(rows) == 1
    assert rows[0]["source"] == "rule"
    assert rows[0]["mandatory"] is True
    assert rows[0]["source_doc"] == "doc-1"
    assert rows[0]["source_page"] == 1


def test_rule_pass_ignores_buyer_obligations():
    """Only the bidder's obligations are requirements — what the buyer will do is not."""
    chunks = [_chunk(text="The Employer shall notify all bidders of the outcome within 30 days.")]
    assert compute_rule_requirements(chunks) == []


def test_rule_pass_ignores_prose_without_obligation_language():
    chunks = [_chunk(text="This project forms part of the state's rural connectivity programme.")]
    assert compute_rule_requirements(chunks) == []


def test_rule_pass_strips_html_from_chunk_text():
    chunks = [_chunk(text="<p>The tenderer <b>must</b> hold a valid CIDB G7 licence.</p>")]
    rows = compute_rule_requirements(chunks)

    assert len(rows) == 1
    assert "<b>" not in rows[0]["description"]
    assert "CIDB G7" in rows[0]["description"]


def test_rule_pass_splits_multiple_sentences():
    chunks = [_chunk(text=(
        "The bidder shall provide audited accounts for three years. "
        "The bidder must also submit a valid tax clearance certificate."
    ))]
    assert len(compute_rule_requirements(chunks)) == 2


@pytest.mark.parametrize("text,expected", [
    ("The bidder shall hold a valid CIDB registration certificate", "certification"),
    ("The tenderer must provide a bank guarantee for the bid bond", "financial"),
    ("Bidders must comply with the Occupational Safety and Health Act", "legal"),
    # experience and personnel are their own categories — they used to be swept into technical,
    # which hid the two things a bid is most often disqualified on.
    ("The bidder shall have completed three similar projects in the last five years", "experience"),
    ("The tenderer must provide key staff with a qualified engineer on site", "personnel"),
    # Submission mechanics are not a category the database recognises — they land in `other`.
    ("The bidder shall submit three sealed copies before the closing date", "other"),
])
def test_rule_categorisation(text, expected):
    assert _categorise(text) == expected


# ------------------- grounding guardrail (the critical one) -------------------
def test_requirement_citing_unknown_chunk_is_dropped():
    """The model cited an excerpt that was never sent — the forensic failure mode."""
    index = {"ch-1": _chunk("ch-1", "The bidder shall hold a licence.")}
    raw = {"requirements": [{
        "description": "Bidder must hold ISO 9001 certification",
        "chunk_id": "ch-INVENTED",
        "category": "certification",
    }]}
    assert validate_llm_requirements(raw, index) == []


def test_grounded_requirement_is_kept():
    index = {"ch-1": _chunk("ch-1", "The bidder shall hold a valid CIDB G7 licence.", page=12)}
    raw = {"requirements": [{
        "description": "Bidder must hold a valid CIDB G7 licence",
        "chunk_id": "ch-1",
        "category": "certification",
        "is_mandatory": True,
        "source_clause": "3.2",
        "source_text": "The bidder shall hold a valid CIDB G7 licence.",
        "confidence": 0.9,
    }]}
    kept = validate_llm_requirements(raw, index)

    assert len(kept) == 1
    assert kept[0]["source_page"] == 12          # taken from OUR chunk row
    assert kept[0]["source_doc"] == "doc-1"
    assert kept[0]["source"] == "llm"


def test_page_comes_from_our_chunk_not_the_model():
    """The model identifies which excerpt; we decide where that excerpt lives."""
    index = {"ch-1": _chunk("ch-1", "The bidder shall submit a bond.", page=7)}
    raw = {"requirements": [{
        "description": "Submit a bond", "chunk_id": "ch-1",
        "source_page": 999, "source_doc": "doc-EVIL",   # both ignored
    }]}
    kept = validate_llm_requirements(raw, index)

    assert kept[0]["source_page"] == 7
    assert kept[0]["source_doc"] == "doc-1"


def test_fabricated_source_text_falls_back_to_the_excerpt():
    """source_text must be verbatim; a rewritten quote must not be stored as one."""
    index = {"ch-1": _chunk("ch-1", "The bidder shall submit audited accounts for three years.")}
    raw = {"requirements": [{
        "description": "Submit audited accounts",
        "chunk_id": "ch-1",
        "source_text": "The bidder is obliged to furnish three years of audited financials.",
    }]}
    kept = validate_llm_requirements(raw, index)

    assert kept[0]["source_text"] == "The bidder shall submit audited accounts for three years."


def test_verbatim_source_text_is_preserved():
    index = {"ch-1": _chunk("ch-1", "Clause 4.1 The bidder shall submit audited accounts.")}
    raw = {"requirements": [{
        "description": "Submit audited accounts", "chunk_id": "ch-1",
        "source_text": "The bidder shall submit audited accounts.",
    }]}
    assert validate_llm_requirements(raw, index)[0]["source_text"] == \
        "The bidder shall submit audited accounts."


def test_unknown_category_falls_back_to_other():
    index = {"ch-1": _chunk("ch-1", "text")}
    raw = {"requirements": [{"description": "x", "chunk_id": "ch-1", "category": "invented"}]}
    assert validate_llm_requirements(raw, index)[0]["category"] == "other"


def test_confidence_is_clamped():
    index = {"ch-1": _chunk("ch-1", "text")}
    raw = {"requirements": [
        {"description": "a", "chunk_id": "ch-1", "confidence": 5.0},
        {"description": "b", "chunk_id": "ch-1", "confidence": "not a number"},
    ]}
    kept = validate_llm_requirements(raw, index)
    # Stored as a 0-100 integer: 5.0 clamps to the top of the range, and an unreadable value
    # falls back to the 0.6 default.
    assert kept[0]["confidence"] == 100
    assert kept[1]["confidence"] == 60


@pytest.mark.parametrize("raw", [None, [], "text", {}, {"requirements": "not a list"}])
def test_malformed_llm_output_yields_nothing(raw):
    assert validate_llm_requirements(raw, {"ch-1": _chunk()}) == []


def test_empty_description_is_dropped():
    index = {"ch-1": _chunk("ch-1", "text")}
    assert validate_llm_requirements({"requirements": [{"description": "  ", "chunk_id": "ch-1"}]}, index) == []


# ------------------------------- merge -------------------------------
def test_rule_row_wins_over_duplicate_llm_row():
    rule = [{"description": "Bidder shall hold a CIDB G7 licence", "category": "certification",
             "source_doc": "doc-1", "source": "rule", "confidence": 0.5}]
    llm = [{"description": "bidder shall hold a CIDB G7 licence  ", "category": "Certification",
            "source_doc": "doc-1", "source": "llm", "confidence": 0.9}]

    merged = merge(rule, llm)
    assert len(merged) == 1
    assert merged[0]["source"] == "rule"


def test_llm_adds_what_rules_could_not_see():
    rule = [{"description": "Bidder shall hold a licence", "category": "certification",
             "source_doc": "doc-1", "source": "rule"}]
    llm = [{"description": "Pricing must remain valid for 90 days", "category": "financial",
            "source_doc": "doc-1", "source": "llm"}]

    merged = merge(rule, llm)
    assert len(merged) == 2
    assert {r["source"] for r in merged} == {"rule", "llm"}


def test_merge_survives_an_llm_outage():
    """ask() returning None must still leave the rule rows standing."""
    rule = [{"description": "Bidder shall submit a bond", "category": "financial",
             "source_doc": "doc-1", "source": "rule"}]
    assert merge(rule, []) == rule


# ------------------------------ batching ------------------------------
def test_batching_splits_on_the_character_budget():
    # Sized from the module's own constants: the budget has been retuned twice, and a test that
    # hard-codes a chunk count silently stops testing the split when it changes again.
    count = _BATCH_CHAR_BUDGET // _MAX_CHUNK_CHARS + 3
    chunks = [_chunk(f"ch-{i}", "x" * (_MAX_CHUNK_CHARS + 500)) for i in range(count)]
    batches = _batch(chunks)

    assert len(batches) > 1
    assert sum(len(b) for b in batches) == count       # nothing lost
    ids = [c["chunk_id"] for b in batches for c in b]
    assert len(set(ids)) == count                      # nothing duplicated


def test_a_single_oversized_chunk_still_gets_its_own_batch():
    assert len(_batch([_chunk("ch-1", "x" * 50_000)])) == 1


def test_batching_empty_input():
    assert _batch([]) == []


# --------------------------- tender summary ---------------------------
def test_days_until_counts_forward_and_backward():
    today = date(2026, 8, 25)
    assert days_until("2026-09-01", today) == 7
    assert days_until("2026-08-20", today) == -5
    assert days_until(None, today) is None
    assert days_until("not a date", today) is None


def test_compute_facts_counts_mandatory_and_unreviewed_requirements():
    """Requirements have no dismissed state — `status` carries the review position instead."""
    requirements = [
        {"category": "legal", "mandatory": True, "status": "met"},
        {"category": "legal", "mandatory": True, "status": "unchecked"},
        {"category": "financial", "mandatory": False, "status": "unchecked"},
    ]
    facts = compute_facts({"title": "T"}, [], requirements)

    assert facts["requirements_total"] == 3
    assert facts["requirements_mandatory"] == 2
    assert facts["requirements_pending_review"] == 2      # 'unchecked' = nobody has reviewed it
    assert facts["requirements_by_category"]["legal"] == {"total": 2, "mandatory": 2}


def test_compute_facts_counts_only_processed_documents():
    documents = [
        {"extraction_status": "done"}, {"extraction_status": "done"},
        {"extraction_status": "failed"}, {"extraction_status": "queued"},
    ]
    facts = compute_facts({}, documents, [])
    assert facts["documents_processed"] == 2
    assert facts["documents_total"] == 4


def test_deterministic_summary_needs_no_llm():
    facts = compute_facts(
        {"title": "Supply of Network Equipment", "buyer": "Ministry of Works",
         "closing_date": "2026-09-10"},
        [{"extraction_status": "done"}],
        [{"category": "certification", "mandatory": True, "status": "unchecked"}],
        today=date(2026, 8, 25),
    )
    text = _deterministic_summary(facts)

    assert "Supply of Network Equipment" in text
    assert "Ministry of Works" in text
    assert "16 days remain" in text
    assert "1 requirements extracted" in text


def test_deterministic_summary_says_so_when_closing_date_is_unknown():
    text = _deterministic_summary(compute_facts({"title": "T"}, [], []))
    assert "not stated" in text


def test_deterministic_summary_flags_a_passed_deadline():
    facts = compute_facts({"title": "T", "closing_date": "2026-08-01"}, [], [],
                          today=date(2026, 8, 25))
    assert "has passed" in _deterministic_summary(facts)


# --------------------------- meta back-fill ---------------------------
# `_backfill_from_llm_meta(workspace, meta)` maps LLM-extracted meta keys onto workspace
# columns, filling only what is still blank.

def test_backfill_populates_blank_columns_from_extracted_meta():
    patch = _backfill_from_llm_meta(
        {"buyer_name": None, "closing_date": None, "tender_reference": None},
        {"buyer": "Ministry of Works", "closing_date": "2026-09-10",
         "reference": "MOW/2026/114"},
    )
    assert patch["buyer_name"] == "Ministry of Works"
    assert patch["closing_date"] == "2026-09-10"
    assert patch["tender_reference"] == "MOW/2026/114"


def test_backfill_never_overwrites_a_human_entered_value():
    patch = _backfill_from_llm_meta(
        {"buyer_name": "Typed By A Human"},
        {"buyer": "Extracted Buyer"},
    )
    assert "buyer_name" not in patch


def test_backfill_skips_unparseable_dates():
    assert "closing_date" not in _backfill_from_llm_meta({}, {"closing_date": "sometime next month"})


def test_backfill_parses_a_formatted_contract_value():
    patch = _backfill_from_llm_meta({}, {"contract_value": "1,250,000"})
    assert patch["contract_value"] == 1250000.0


def test_backfill_skips_an_unparseable_contract_value():
    """A value we cannot read must not become a confident-looking number on the workspace."""
    assert "contract_value" not in _backfill_from_llm_meta({}, {"contract_value": "circa 1.2m"})


def test_backfill_of_an_empty_extraction_changes_nothing():
    assert _backfill_from_llm_meta({}, {}) == {}


def test_backfill_never_touches_decision_columns():
    """Rule 3: extraction may fill facts, never decisions."""
    patch = _backfill_from_llm_meta(
        {}, {"buyer": "X", "bid_decision": "bid", "readiness_score": 90},
    )
    assert "bid_decision" not in patch
    assert "readiness_score" not in patch
