"""Investigation document types + classify wrapper.

Owns the fraud-flavoured document labels and hands them to the core classify engine. Tendering
has its own equivalent (tender_notice, BOQ, pricing_schedule, …) pointing at the same engine.
"""
from __future__ import annotations

from backend.core import classify as _engine

KNOWN_TYPES = [
    "invoice", "bank_statement", "contract", "tender_document", "payment_voucher",
    "company_registration", "email", "whatsapp_screenshot", "approval_form", "other",
]

_HEURISTICS = {
    "invoice": ["invoice", "inv no", "amount due"],
    "bank_statement": ["statement", "opening balance", "closing balance"],
    "contract": ["agreement", "hereby", "party of the first part", "terms and conditions"],
    "tender_document": ["tender", "rfp", "request for proposal", "bid"],
    "payment_voucher": ["voucher", "payment authorised", "pay to"],
    "company_registration": ["certificate of incorporation", "company no", "directors"],
    "email": ["from:", "subject:", "sent:"],
    "whatsapp_screenshot": ["whatsapp", "online", "typing..."],
    "approval_form": ["approved by", "signature", "approval"],
}


def heuristic(text: str) -> str:
    return _engine.heuristic(text, _HEURISTICS)


def classify(markdown: str) -> str:
    return _engine.classify(markdown, KNOWN_TYPES, _HEURISTICS)
