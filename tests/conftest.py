"""Shared test fixtures.

`sample_extractions` is a hand-built corpus that deliberately contains a duplicate invoice,
a bank account shared by two vendors, a split payment, and a shared company director — so
the pure pipeline functions have something to find.
"""
import pytest


@pytest.fixture
def sample_extractions():
    return [
        {"document_id": "d1", "extracted_json": {
            "vendor_name": "Nova Build", "amount": 9000, "currency": "MYR",
            "bank_account": "ACC-111", "invoice_number": "INV-001",
            "payment_date": "2024-06-01", "po_number": "PO-1"}},
        {"document_id": "d2", "extracted_json": {
            "vendor_name": "Apex Supplies", "amount": 9500,
            "bank_account": "ACC-111", "invoice_number": "INV-002",
            "payment_date": "2024-06-02"}},
        {"document_id": "d3", "extracted_json": {
            "vendor_name": "Nova Build", "amount": 4000,
            "bank_account": "ACC-111", "invoice_number": "INV-001",
            "payment_date": "2024-06-02"}},
        {"document_id": "d4", "extracted_json": {
            "directors": ["Jane Tan"], "related_companies": ["Nova Build", "Apex Supplies"]}},
    ]
