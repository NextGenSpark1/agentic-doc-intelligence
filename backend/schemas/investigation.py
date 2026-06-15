"""Investigation extraction schemas (Phase 3).

Every field is Optional and carries a `description`. Two reasons:
  1. ADE Extract uses the description to locate the field in messy, real-world documents.
  2. A given document rarely contains every field; Optional prevents extraction failures
     when a field is genuinely absent.

These same Pydantic classes are the single source of truth: ADE consumes them as the
extraction model, and FastAPI/Supabase store their output. One definition, several jobs.
"""
from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field


class FinancialTransaction(BaseModel):
    vendor_name: Optional[str] = Field(None, description="Name of the vendor or payee receiving funds")
    amount: Optional[float] = Field(None, description="Transaction or invoice amount as a number")
    currency: Optional[str] = Field(None, description="Three-letter currency code, e.g. MYR, USD")
    bank_account: Optional[str] = Field(None, description="Bank account number the payment was made to")
    approval_officer: Optional[str] = Field(None, description="Name of the officer who approved the payment")
    invoice_number: Optional[str] = Field(None, description="Invoice or document reference number")
    payment_date: Optional[str] = Field(None, description="Date of payment in ISO format YYYY-MM-DD")
    po_number: Optional[str] = Field(None, description="Purchase order number linked to the payment")


class ProcurementRecord(BaseModel):
    tender_id: Optional[str] = Field(None, description="Tender or solicitation identifier")
    awarded_vendor: Optional[str] = Field(None, description="Vendor that won the tender")
    competing_vendors: list[str] = Field(default_factory=list, description="Other vendors that bid")
    approval_timeline: Optional[str] = Field(None, description="Key approval dates or sequence described")
    budget_amount: Optional[float] = Field(None, description="Approved budget for the procurement")
    contract_value: Optional[float] = Field(None, description="Final awarded contract value")


class ConflictOfInterest(BaseModel):
    person_names: list[str] = Field(default_factory=list, description="Names of individuals mentioned")
    related_companies: list[str] = Field(default_factory=list, description="Companies linked to the individuals")
    shareholders: list[str] = Field(default_factory=list, description="Named shareholders")
    directors: list[str] = Field(default_factory=list, description="Named directors")
    addresses: list[str] = Field(default_factory=list, description="Physical addresses mentioned")
    phone_numbers: list[str] = Field(default_factory=list, description="Phone numbers mentioned")


class CommunicationIntelligence(BaseModel):
    dates: list[str] = Field(default_factory=list, description="Dates referenced in the communication")
    participants: list[str] = Field(default_factory=list, description="People involved in the conversation")
    intent_indicators: list[str] = Field(default_factory=list, description="Phrases signalling intent or agreement")
    suspicious_keywords: list[str] = Field(default_factory=list, description="Terms suggesting irregularity")
    commitments: list[str] = Field(default_factory=list, description="Promises or commitments made")
    payment_references: list[str] = Field(default_factory=list, description="Amounts or payment references mentioned")


# Maps the dashboard's Case Type -> the schema used to extract its documents.
# (The Settings page states Case Type "is used to select extraction schema".)
SCHEMA_REGISTRY: dict[str, Type[BaseModel]] = {
    "procurement": ProcurementRecord,
    "procurement_fraud": ProcurementRecord,
    "payment_tracing": FinancialTransaction,
    "financial": FinancialTransaction,
    "conflict_of_interest": ConflictOfInterest,
    "communication": CommunicationIntelligence,
    "audit": FinancialTransaction,
}


def schema_for_case_type(case_type: str) -> Type[BaseModel]:
    """Pick the extraction schema for a case type, defaulting to FinancialTransaction."""
    key = (case_type or "").strip().lower().replace(" ", "_")
    return SCHEMA_REGISTRY.get(key, FinancialTransaction)
