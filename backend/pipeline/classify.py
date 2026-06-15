"""Stage 1 — classify a document into a coarse type (invoice, contract, email, ...).

Cheap LLM call on the first slice of parsed text, with a keyword heuristic fallback so the
pipeline still works without an LLM key during early development.
"""
from __future__ import annotations

from .. import llm

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
    low = text.lower()
    best, score = "other", 0
    for t, kws in _HEURISTICS.items():
        hits = sum(1 for k in kws if k in low)
        if hits > score:
            best, score = t, hits
    return best


def classify(markdown: str) -> str:
    snippet = (markdown or "")[:1500]
    if not snippet.strip():
        return "other"
    try:
        answer = llm.complete(
            tier="fast",
            messages=[
                {"role": "system", "content": "Classify the document. Reply with ONE label only, "
                 "from: " + ", ".join(KNOWN_TYPES) + ". No other text."},
                {"role": "user", "content": snippet},
            ],
        ).strip().lower()
        return answer if answer in KNOWN_TYPES else heuristic(snippet)
    except Exception:
        # No LLM key / provider down -> degrade gracefully to heuristic
        return heuristic(snippet)
