"""Anomaly-detection rules — the legally-sensitive logic, tested in isolation (no DB)."""
from backend.pipeline.detect_anomalies import compute_findings


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
