"""Investigation schema routing + shape."""
from backend.schemas.investigation import (
    ConflictOfInterest,
    FinancialTransaction,
    ProcurementRecord,
    schema_for_case_type,
)


def test_case_type_routing():
    assert schema_for_case_type("Procurement Fraud") is ProcurementRecord
    assert schema_for_case_type("Payment Tracing") is FinancialTransaction
    assert schema_for_case_type("conflict_of_interest") is ConflictOfInterest


def test_unknown_case_type_defaults_to_financial():
    assert schema_for_case_type("something weird") is FinancialTransaction


def test_schema_exposes_json_schema_for_ade():
    # ADE Extract consumes JSON Schema; confirm our model produces one with the right fields.
    props = FinancialTransaction.model_json_schema()["properties"]
    assert {"vendor_name", "amount", "bank_account", "invoice_number"} <= set(props)
