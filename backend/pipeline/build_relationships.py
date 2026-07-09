"""Stage 4b — relationship discovery.

The headline differentiator from the business case: "same bank account across 4 vendors",
"same director linked to multiple companies", "same phone reused". We find shared values
across documents and record them as graph edges in the `relationships` table.

AI-first: a case-reasoning LLM pass is the primary source of edges — it looks for relationships
implied by the narrative content of the extracted fields, not just exact shared values (e.g. one
party introducing another, a stated associate tie). The deterministic rule-based joins
(`compute_relationships`) run only as a fallback when the LLM returns nothing (quota exhausted,
key missing, provider down). Every LLM edge must cite a document_id that actually exists in the
case; anything else is dropped before persisting.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from .. import db
from . import llm_reasoning

# (shared field, the entity it ties together, edge label)
_SHARED_LINKS = [
    ("bank_account", "vendor_name", "shared_bank_account"),
    ("bank_account", "awarded_vendor", "shared_bank_account"),
]

_RELATIONSHIP_PROMPT = (
    "You are helping map relationships between entities in a forensic investigation case. "
    "Below is a JSON list of document extractions (document_id + extracted structured fields). "
    "Beyond simple shared-value joins (same bank account, same officer, same phone), look for "
    "relationships implied by the narrative content of the fields themselves — e.g. one party "
    "introducing another, a stated family or associate tie, a prior dealing referenced in "
    "passing. Cite the exact document_id the relationship comes from and quote the phrase that "
    "supports it. Do not invent a document_id, entity name, or fact that is not present in the "
    "input.\n\n"
    'Reply with strict JSON: {"relationships": [{"source_name": str, "target_name": str, '
    '"relationship_type": str, "evidence_quote": str, "document_id": str, "confidence": float}]}. '
    "Return an empty list if you find nothing beyond what simple field matching would already show."
)


def _llm_relationships(extractions: list[dict], case_id: str) -> list[dict]:
    valid_doc_ids = {ex["document_id"] for ex in extractions}
    if len(valid_doc_ids) < 2:
        return []

    payload = {
        "documents": [
            {"document_id": ex["document_id"], "fields": ex.get("extracted_json") or {}}
            for ex in extractions
        ]
    }
    result = llm_reasoning.ask(_RELATIONSHIP_PROMPT, payload, case_id)
    items = result.get("relationships") if isinstance(result, dict) else None
    if not items or not isinstance(items, list):
        return []

    edges = []
    for item in items:
        if not isinstance(item, dict):
            continue
        doc_id = str(item.get("document_id") or "")
        source = str(item.get("source_name") or "").strip()
        target = str(item.get("target_name") or "").strip()
        label = str(item.get("relationship_type") or "").strip()
        if not (doc_id in valid_doc_ids and source and target and label):
            continue  # ungrounded — the model cited something we never sent
        edges.append(_edge(
            case_id, source, target, label,
            {"evidence_quote": item.get("evidence_quote"), "document_id": doc_id},
            source_flag="llm",
            reasoning=item.get("evidence_quote"),
            confidence=llm_reasoning.clamp_confidence(item.get("confidence"), default=0.6),
        ))
    return edges


def compute_relationships(extractions: list[dict], case_id: str | None = None) -> list[dict]:
    edges: list[dict] = []
    actual_case_id = case_id or "unknown"

    # 1. Shared bank account across different vendors
    acct_to_vendors: dict[str, set] = defaultdict(set)
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        acct = (d.get("bank_account") or "").strip()
        vendor = (d.get("vendor_name") or d.get("awarded_vendor") or "").strip()
        if acct and vendor:
            acct_to_vendors[acct].add(vendor)
    for acct, vendors in acct_to_vendors.items():
        if len(vendors) > 1:
            vendors_sorted = sorted(vendors)
            for i in range(len(vendors_sorted)):
                for j in range(i + 1, len(vendors_sorted)):
                    edges.append(_edge(actual_case_id, vendors_sorted[i], vendors_sorted[j],
                                       "shared_bank_account", {"bank_account": acct}))

    # 2. Shared director/shareholder across companies (conflict-of-interest docs)
    person_to_companies: dict[str, set] = defaultdict(set)
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        people = (d.get("directors") or []) + (d.get("shareholders") or [])
        for company in (d.get("related_companies") or []):
            for person in people:
                if person and company:
                    person_to_companies[person.strip()].add(company.strip())
    for person, companies in person_to_companies.items():
        if len(companies) > 1:
            companies_sorted = sorted(companies)
            for i in range(len(companies_sorted)):
                for j in range(i + 1, len(companies_sorted)):
                    edges.append(_edge(actual_case_id, companies_sorted[i], companies_sorted[j],
                                       "shared_principal", {"person": person}))

    # 3. Approving officer → awarded vendor (procurement fraud / financial)
    seen_pairs: set[tuple] = set()
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        officer = (d.get("approval_officer") or d.get("approving_officer") or "").strip()
        vendor = (d.get("vendor_name") or d.get("awarded_vendor") or "").strip()
        if officer and vendor:
            pair = (officer, vendor)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                edges.append(_edge(actual_case_id, officer, vendor, "approved_award", {}))

    # 4. Counterparties linked across documents (financial_crime)
    counterparty_docs: dict[str, list] = defaultdict(list)
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        for cp in (d.get("counterparties") or []):
            cp = cp.strip()
            if cp:
                counterparty_docs[cp].append(ex["document_id"])
    for cp, docs in counterparty_docs.items():
        if len(docs) > 1:
            edges.append(_edge(actual_case_id, cp, "multiple documents",
                               "appears_in_multiple_documents",
                               {"document_count": len(docs)}))

    # 5. Involved parties cross-linked (corruption)
    party_to_docs: dict[str, list] = defaultdict(list)
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        for party in (d.get("involved_parties") or []):
            party = party.strip()
            if party:
                party_to_docs[party].append(ex["document_id"])
    parties = sorted(party_to_docs.keys())
    for i in range(len(parties)):
        for j in range(i + 1, len(parties)):
            edges.append(_edge(actual_case_id, parties[i], parties[j],
                               "co_involved", {}))

    return edges


def build(case_id: str) -> list[dict]:
    # Clear existing relationships before rebuild to prevent duplicates on re-run
    db.get_client().table("relationships").delete().eq("case_id", case_id).execute()
    extractions = db.list_extractions(case_id)
    # AI-first: LLM relationship discovery is the primary output
    edges = _llm_relationships(extractions, case_id)
    # Rules are a fallback only when LLM returns nothing
    if not edges:
        edges = compute_relationships(extractions, case_id)
    for e in edges:
        db.insert_relationship(e)
    return edges


def _edge(case_id, a, b, label, meta, source_flag="rule", reasoning=None, confidence=None):
    evidence = dict(meta)
    if confidence is not None:
        evidence["confidence"] = confidence
    edge = {
        "relationship_id": str(uuid.uuid4()),
        "case_id": case_id,
        "source_name": a,
        "target_name": b,
        "relationship_type": label,
        "evidence": evidence,
        "source": source_flag,
    }
    if reasoning is not None:
        edge["reasoning"] = reasoning
    return edge
