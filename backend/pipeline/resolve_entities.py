"""Stage 4a — entity resolution.

Pull named values out of every extraction in the case, normalise them, and upsert a
deduplicated canonical entity per (type, name). This is the first half of the agentic
layer: turning per-document fields into case-wide entities. ADE does NOT do this — it has
no concept of the case.
"""
from __future__ import annotations

import re
import uuid

from .. import db

# Which extracted fields map to which entity type.
_FIELD_TO_TYPE = {
    # financial / payment_tracing / audit
    "vendor_name": "vendor",
    "approval_officer": "person",
    "bank_account": "bank_account",
    "po_number": "po",
    "invoice_number": "invoice",
    # procurement_fraud
    "awarded_vendor": "vendor",
    "approving_officer": "person",   # custom field users add to procurement cases
    # financial_crime
    "reporting_entity": "company",
    "investigation_reference": "reference",
    # corruption
    "benefit_type": "benefit",
}
_LIST_FIELD_TO_TYPE = {
    # conflict_of_interest
    "competing_vendors": "vendor",
    "person_names": "person",
    "related_companies": "company",
    "shareholders": "person",
    "directors": "person",
    "phone_numbers": "phone",
    # financial_crime
    "counterparties": "person",
    "account_numbers": "bank_account",
    # corruption
    "involved_parties": "person",
    # communication
    "participants": "person",
    # general
    "party_names": "person",
    "signatories": "person",
}


def _normalise(name: str) -> str:
    s = (name or "").strip()
    # Strip role in parentheses: "Dato' Razif (Procurement Director)" → "Dato' Razif"
    s = re.sub(r"\s*\(.*?\)", "", s)
    # Strip comma-separated role suffix: "Dato' Razif, Procurement Director" → "Dato' Razif"
    s = re.sub(r",.*$", "", s)
    return re.sub(r"\s+", " ", s.lower()).strip()


def resolve(case_id: str) -> list[dict]:
    extractions = db.list_extractions(case_id)
    # canonical_key -> {type, display_name, doc_ids}
    seen: dict[str, dict] = {}

    def add(value, etype, doc_id):
        if not value or not str(value).strip():
            return
        display = str(value).strip()
        key = f"{etype}:{_normalise(display)}"
        rec = seen.setdefault(key, {"type": etype, "display": display, "docs": set()})
        rec["docs"].add(doc_id)

    for ex in extractions:
        doc_id = ex["document_id"]
        data = ex.get("extracted_json") or {}
        for field, etype in _FIELD_TO_TYPE.items():
            add(data.get(field), etype, doc_id)
        for field, etype in _LIST_FIELD_TO_TYPE.items():
            for v in (data.get(field) or []):
                add(v, etype, doc_id)

    out = []
    for rec in seen.values():
        out.append(
            db.upsert_entity(
                {
                    "entity_id": str(uuid.uuid4()),
                    "case_id": case_id,
                    "entity_type": rec["type"],
                    "canonical_name": rec["display"],
                    "aliases": [],
                    "confidence_score": 0.9,
                    "source_document_ids": sorted(rec["docs"]),
                }
            )
        )
    return out
