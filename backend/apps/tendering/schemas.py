"""Tender extraction schemas + the requirement record shape.

Two different jobs live here:

* **Extraction schemas** (`TenderNotice`, `BillOfQuantities`, …) are handed to ADE through
  core's `run_extraction(document, case, schema_resolver)`. One document in, one structured
  JSON blob out — the same path investigation uses for `FinancialTransaction`.

* **`RequirementRecord`** is not an ADE schema. Requirement extraction produces *many* child
  records from one document, each with clause-level grounding, so it runs as an LLM stage
  (slice 2) and validates its output against this model before anything is persisted.

Rule 2 is enforced at the model level: an AI-generated requirement without a source document
and page cannot be constructed, so it can never reach the database. The matching CHECK
constraint in schema_tendering.sql is the backstop for anything that bypasses this model.
"""
from __future__ import annotations

from typing import Literal, Optional, Type

from pydantic import BaseModel, Field, model_validator

# Requirement categories. Kept as a constant so prompts, validation, and the compliance
# matrix's grouping all read from one list rather than three drifting copies.
REQUIREMENT_CATEGORIES = (
    "legal",
    "financial",
    "technical",
    "certification",
    "submission_instruction",
    "evaluation_criterion",
    "other",
)

RequirementCategory = Literal[
    "legal",
    "financial",
    "technical",
    "certification",
    "submission_instruction",
    "evaluation_criterion",
    "other",
]


# ------------------------- ADE extraction schemas -------------------------
class TenderNotice(BaseModel):
    """Header facts from a tender notice / ITT / RFP cover document."""

    tender_title: Optional[str] = Field(None, description="Official title of the tender")
    tender_reference: Optional[str] = Field(None, description="Tender or solicitation reference number")
    buyer_name: Optional[str] = Field(None, description="Procuring entity or buying organisation")
    buyer_contact: Optional[str] = Field(None, description="Named contact person or email for enquiries")
    closing_date: Optional[str] = Field(None, description="Submission deadline in ISO format YYYY-MM-DD")
    closing_time: Optional[str] = Field(None, description="Submission cut-off time, if stated separately")
    briefing_date: Optional[str] = Field(None, description="Site visit or pre-bid briefing date, ISO format")
    contract_value: Optional[float] = Field(None, description="Estimated contract value as a number")
    currency: Optional[str] = Field(None, description="Three-letter currency code, e.g. MYR, USD")
    contract_duration: Optional[str] = Field(None, description="Contract period or delivery timeframe")
    submission_method: Optional[str] = Field(None, description="How bids are submitted, e.g. portal, sealed envelope")
    bid_bond: Optional[str] = Field(None, description="Bid bond or tender security amount and form required")
    performance_bond: Optional[str] = Field(None, description="Performance bond required on award")
    eligibility_criteria: list[str] = Field(default_factory=list, description="Stated eligibility or pre-qualification conditions")
    required_certifications: list[str] = Field(default_factory=list, description="Certifications, licences, or registrations required of bidders")
    evaluation_criteria: list[str] = Field(default_factory=list, description="Stated award or evaluation criteria and any weightings")


class BillOfQuantities(BaseModel):
    """Priced or unpriced BOQ / schedule of rates."""

    boq_reference: Optional[str] = Field(None, description="BOQ section or reference identifier")
    line_items: list[str] = Field(default_factory=list, description="Description of each line item, in document order")
    quantities: list[str] = Field(default_factory=list, description="Quantity and unit for each line item")
    unit_rates: list[str] = Field(default_factory=list, description="Unit rate for each line item, if priced")
    total_amount: Optional[float] = Field(None, description="Total or summary amount for this BOQ")
    currency: Optional[str] = Field(None, description="Three-letter currency code")


class PricingSchedule(BaseModel):
    """Commercial response form — the supplier's price breakdown."""

    schedule_reference: Optional[str] = Field(None, description="Schedule or form reference")
    price_components: list[str] = Field(default_factory=list, description="Named price components or cost headings")
    component_amounts: list[str] = Field(default_factory=list, description="Amount for each price component")
    total_price: Optional[float] = Field(None, description="Total tendered price")
    currency: Optional[str] = Field(None, description="Three-letter currency code")
    validity_period: Optional[str] = Field(None, description="How long the quoted price stays valid")
    payment_terms: Optional[str] = Field(None, description="Stated payment terms or milestones")


class TenderAddendum(BaseModel):
    """A corrigendum / addendum issued after the original tender."""

    addendum_reference: Optional[str] = Field(None, description="Addendum number or reference")
    issue_date: Optional[str] = Field(None, description="Date the addendum was issued, ISO format")
    affected_clauses: list[str] = Field(default_factory=list, description="Clause numbers the addendum changes")
    changes: list[str] = Field(default_factory=list, description="What each change alters")
    new_closing_date: Optional[str] = Field(None, description="Revised submission deadline, if extended")


class GeneralTenderDocument(BaseModel):
    """Fallback for tender-pack documents with no dedicated schema."""

    document_title: Optional[str] = Field(None, description="Title of the document")
    document_type: Optional[str] = Field(None, description="What kind of document this is")
    issuing_party: Optional[str] = Field(None, description="Organisation that issued the document")
    reference_numbers: list[str] = Field(default_factory=list, description="Any reference or identifier numbers")
    key_dates: list[str] = Field(default_factory=list, description="Dates stated in the document")
    key_clauses: list[str] = Field(default_factory=list, description="Important clauses, conditions, or obligations")


# Maps a tender workspace's case_type -> the schema used to extract its documents.
# Core resolves this per document via `schema_resolver(case.get("case_type"))`, so every
# document in a tender workspace currently extracts against the same schema. Per-document
# schema selection (notice vs BOQ vs pricing) is a slice-2 refinement — it needs core's
# seam widened from case_type to (case_type, document_type), which is a core change and so
# deliberately out of scope for the foundation slice.
SCHEMA_REGISTRY: dict[str, Type[BaseModel]] = {
    "tender": TenderNotice,
    "tender_notice": TenderNotice,
    "itt": TenderNotice,
    "rfp": TenderNotice,
    "boq": BillOfQuantities,
    "bill_of_quantities": BillOfQuantities,
    "pricing_schedule": PricingSchedule,
    "addendum": TenderAddendum,
    "general_tender": GeneralTenderDocument,
}


def schema_for_case_type(case_type: str) -> Type[BaseModel]:
    """Pick the extraction schema for a tender case type, defaulting to TenderNotice.

    Mirrors `apps.investigation.schemas.schema_for_case_type` so core's injection seam sees
    an identical callable shape from both products.
    """
    key = (case_type or "").strip().lower().replace(" ", "_").replace("-", "_")
    return SCHEMA_REGISTRY.get(key, TenderNotice)


# ------------------------- requirement records -------------------------
class RequirementRecord(BaseModel):
    """One extracted obligation, validated before persistence.

    `source` distinguishes who produced the row. Anything not `manual` must carry a source
    document and page — that is Rule 2, and it is checked here rather than trusted to the
    prompt, so an ungrounded LLM requirement fails construction instead of reaching the UI.
    """

    description: str = Field(..., description="The obligation, stated as the tender states it")
    category: RequirementCategory = "other"
    is_mandatory: bool = False
    required_evidence: Optional[str] = Field(
        None, description="What the bidder must supply to satisfy this requirement"
    )

    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    source_clause: Optional[str] = None
    source_text: Optional[str] = Field(
        None, description="Verbatim text the requirement was read from"
    )
    confidence: Optional[float] = None
    source: Literal["rule", "llm", "manual"] = "llm"

    @model_validator(mode="after")
    def _enforce_grounding(self) -> "RequirementRecord":
        if not self.description.strip():
            raise ValueError("requirement description must not be empty")
        if self.source != "manual":
            if not self.source_document_id:
                raise ValueError(
                    f"{self.source}-generated requirement must cite source_document_id (Rule 2)"
                )
            if self.source_page is None:
                raise ValueError(
                    f"{self.source}-generated requirement must cite source_page (Rule 2)"
                )
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")
        return self
