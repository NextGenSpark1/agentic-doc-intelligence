"""Tender document types + classify wrapper.

Owns the tender-flavoured document labels and hands them to the core classify engine —
the exact mirror of `apps.investigation.classify`. Core never learns these labels; it
receives them as arguments.
"""
from __future__ import annotations

from backend.core import classify as _engine

KNOWN_TYPES = [
    "tender_notice",        # the ITT / RFP / invitation itself
    "instructions_to_bidders",
    "terms_of_reference",   # scope of work / specification
    "bill_of_quantities",
    "pricing_schedule",
    "contract_conditions",
    "addendum",             # corrigenda issued after publication
    "bid_form",             # forms the bidder fills in and returns
    "eligibility_document", # licences, registrations, certificates demanded of bidders
    "clarification",        # Q&A between bidder and buyer
    "other",
]

_HEURISTICS = {
    "tender_notice": ["invitation to tender", "request for proposal", "tender notice", "invitation to bid"],
    "instructions_to_bidders": ["instructions to bidders", "instruction to tenderers", "submission requirements"],
    "terms_of_reference": ["terms of reference", "scope of work", "technical specification", "statement of work"],
    "bill_of_quantities": ["bill of quantities", "boq", "schedule of rates", "quantity", "unit rate"],
    "pricing_schedule": ["price schedule", "pricing schedule", "schedule of prices", "tendered sum"],
    "contract_conditions": ["conditions of contract", "general conditions", "special conditions", "form of agreement"],
    "addendum": ["addendum", "corrigendum", "amendment no", "clarification notice"],
    "bid_form": ["form of tender", "bid form", "tender form", "to be completed by the bidder"],
    "eligibility_document": ["certificate of registration", "cidb", "ssm", "licence no", "valid until"],
    "clarification": ["query", "clarification", "question and answer", "response to queries"],
}


def heuristic(text: str) -> str:
    return _engine.heuristic(text, _HEURISTICS)


def classify(markdown: str) -> str:
    return _engine.classify(markdown, KNOWN_TYPES, _HEURISTICS)
