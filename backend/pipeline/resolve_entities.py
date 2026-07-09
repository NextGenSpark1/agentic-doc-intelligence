"""Stage 4a — entity resolution.

Pull named values out of every extraction in the case, normalise them, and upsert a
deduplicated canonical entity per (type, name). This is the first half of the agentic
layer: turning per-document fields into case-wide entities. ADE does NOT do this — it has
no concept of the case.

After the deterministic pass, a Gemini reasoning call looks for aliases the regex normaliser
can't catch (name-order variants, abbreviations, translated titles) and merges them. Every
merge is validated against the candidate names we actually sent — the model cannot introduce
an entity we never extracted — and merged entities are tagged source="llm" so a merge can
always be told apart from a plain rule-based dedup.
"""
from __future__ import annotations

import re
import uuid

from .. import db
from . import llm_reasoning

_ALIAS_MERGE_PROMPT = (
    "You are helping resolve entities for a forensic investigation case. Below is a JSON list "
    "of candidate entity names already deduplicated by exact normalised match, each with its "
    "type and how many documents it appears in. Some of these may still be the SAME real-world "
    "person, company, or account under a different name — e.g. abbreviations, name-order "
    "variants, or a title/spelling difference the normaliser missed. Only group candidates you "
    "are confident refer to the same entity; when unsure, leave them separate. Never invent a "
    "name that is not in the candidate list.\n\n"
    'Reply with strict JSON: {"clusters": [{"canonical_name": str, "entity_type": str, '
    '"members": [str, ...], "confidence": float}]}. Only include clusters with 2 or more '
    "members. `entity_type` and every name in `members` must exactly match an entry from the "
    "candidate list."
)

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


def _apply_llm_merge(seen: dict[str, dict]) -> dict[str, dict]:
    """Ask Gemini to merge aliases the regex normaliser missed. Any merge that references a
    name or type outside what we actually sent is dropped — the model can dedupe, not invent."""
    candidates = [
        {"type": rec["type"], "name": rec["display"], "doc_count": len(rec["docs"])}
        for rec in seen.values()
    ]
    if len(candidates) < 2:
        return seen

    result = llm_reasoning.ask(_ALIAS_MERGE_PROMPT, {"candidates": candidates})
    clusters = result.get("clusters") if isinstance(result, dict) else None
    if not clusters:
        return seen

    by_type_name = {(rec["type"], rec["display"]): key for key, rec in seen.items()}
    merged = dict(seen)
    for cluster in clusters if isinstance(clusters, list) else []:
        if not isinstance(cluster, dict):
            continue
        etype = str(cluster.get("entity_type") or "").strip()
        members = cluster.get("members") or []
        valid_keys = list(dict.fromkeys(
            by_type_name[(etype, m)] for m in members
            if (etype, m) in by_type_name and by_type_name[(etype, m)] in merged
        ))
        if len(valid_keys) < 2:
            continue  # not enough grounded members to justify a merge

        primary = merged[valid_keys[0]]
        canonical = str(cluster.get("canonical_name") or "").strip() or primary["display"]
        aliases = set(primary.get("aliases") or [])
        for key in valid_keys[1:]:
            other = merged.pop(key)
            aliases.add(other["display"])
            primary["docs"] |= other["docs"]
        aliases.discard(canonical)
        primary["display"] = canonical
        primary["aliases"] = sorted(aliases)
        primary["source"] = "llm"
        primary["confidence"] = llm_reasoning.clamp_confidence(cluster.get("confidence"), default=0.75)
    return merged


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

    seen = _apply_llm_merge(seen)

    out = []
    for rec in seen.values():
        out.append(
            db.upsert_entity(
                {
                    "entity_id": str(uuid.uuid4()),
                    "case_id": case_id,
                    "entity_type": rec["type"],
                    "canonical_name": rec["display"],
                    "aliases": rec.get("aliases", []),
                    "confidence_score": rec.get("confidence", 0.9),
                    "source_document_ids": sorted(rec["docs"]),
                    "source": rec.get("source", "rule"),
                }
            )
        )
    return out
