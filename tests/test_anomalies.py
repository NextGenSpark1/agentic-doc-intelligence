"""Anomaly-detection rules — the legally-sensitive logic, tested in isolation (no DB)."""
from backend.apps.investigation.pipeline.detect_anomalies import _dedupe_llm_findings, compute_findings


def test_detects_all_three_anomaly_types(sample_extractions):
    findings = compute_findings(sample_extractions)
    types = {f["finding_type"] for f in findings}
    assert "duplicate_invoice" in types
    assert "shared_bank_account" in types
    assert "split_payment" in types


def test_duplicate_invoice_cites_both_documents(sample_extractions):
    dup = next(f for f in compute_findings(sample_extractions)
               if f["finding_type"] == "duplicate_invoice")
    assert set(dup["supporting_document_ids"]) == {"d1", "d3"}
    assert dup["severity"] == "high"


def test_clean_corpus_yields_no_findings():
    clean = [{"document_id": "x", "extracted_json": {
        "vendor_name": "Solo Vendor", "amount": 100, "bank_account": "ACC-9",
        "invoice_number": "INV-9", "payment_date": "2024-01-01"}}]
    assert compute_findings(clean) == []


def test_llm_finding_duplicating_a_rule_finding_is_dropped():
    """A provable rule finding must not be suppressed by an LLM finding of the same type over
    the same documents — the LLM duplicate is dropped (order/casing differences still collide)."""
    rule = [{"finding_type": "shared_bank_account", "supporting_document_ids": ["d1", "d2"]}]
    llm = [{"finding_type": "Shared_Bank_Account", "supporting_document_ids": ["d2", "d1"]}]
    assert _dedupe_llm_findings(llm, rule) == []


def test_llm_finding_with_new_reasoning_survives():
    """Rules and LLM run together: a genuinely new LLM finding is kept alongside rule findings."""
    rule = [{"finding_type": "shared_bank_account", "supporting_document_ids": ["d1", "d2"]}]
    llm = [{"finding_type": "circular_payment", "supporting_document_ids": ["d1", "d2"]}]
    kept = _dedupe_llm_findings(llm, rule)
    assert len(kept) == 1
    assert kept[0]["finding_type"] == "circular_payment"
