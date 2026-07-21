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
    "You are a senior forensic analyst building an entity relationship graph for an investigation case. "
    "Below is a JSON list of document extractions. Each document has a document_id and extracted fields. "
    "Your task is to identify EVERY meaningful relationship between named entities across all documents. "
    "Be exhaustive — a missed relationship is more dangerous than a false positive.\n\n"

    "RELATIONSHIP CATEGORIES TO EXTRACT\n\n"

    "OWNERSHIP AND CONTROL\n"
    "- director_of: person is a named director of a company\n"
    "- shareholder_of: person holds shares in a company\n"
    "- beneficial_owner_of: person is the ultimate beneficial owner\n"
    "- controls: entity controls or manages another entity\n"
    "- subsidiary_of / parent_of: corporate ownership hierarchy\n\n"

    "APPROVAL AND AUTHORITY\n"
    "- approved_award: officer approved a contract or tender for a vendor\n"
    "- authorised_payment: officer authorised a payment to a vendor or account\n"
    "- signed_contract: person signed a contract on behalf of an entity\n"
    "- reviewed_by / checked_by / prepared_by: document workflow roles\n"
    "- supervisor_of / subordinate_of: internal reporting hierarchy\n\n"

    "FINANCIAL LINKS\n"
    "- bank_account_holder: entity holds or operates a bank account\n"
    "- paid_by / paid_to: payment flow between entities\n"
    "- invoiced: vendor issued invoice to client entity\n"
    "- guarantor_of: entity provides a guarantee for another\n\n"

    "IDENTITY AND NAME-BASED LINKS (CRITICAL — do not skip)\n"
    "- name_similarity: approving officer's surname or given name appears in the vendor or company name "
    "(e.g. 'Zulkarnain bin Rashid' approves 'Rashid & Farid Construction') — always flag this\n"
    "- possible_relative: two individuals share a surname and appear on opposite sides of a transaction\n"
    "- same_person_alias: two names that appear to refer to the same individual across documents\n\n"

    "ADDRESS AND CONTACT OVERLAP (CRITICAL — do not skip)\n"
    "- shared_address: two parties (e.g. vendor director and approving officer) share the same "
    "registered, residential, or emergency-contact address found anywhere in the documents\n"
    "- shared_phone: same phone number or contact appears for two different named parties\n"
    "- shared_email: same email appears for two different named parties\n"
    "- shared_bank_account: same account number linked to more than one vendor or individual\n\n"

    "PROCUREMENT AND CONTRACT LINKS\n"
    "- awarded_contract: vendor was awarded a specific contract or tender\n"
    "- competing_vendor: vendor submitted a competing bid\n"
    "- subcontractor_of: one vendor subcontracts to another\n"
    "- referenced_in: entity or document references another document or entity\n\n"

    "ORGANISATIONAL AND INSTITUTIONAL LINKS\n"
    "- employed_by / works_for: person is employed by an organisation\n"
    "- represents: person acts as representative or agent for an entity\n"
    "- regulates / audits: one body has oversight over another\n"
    "- filed_report_on: entity submitted a report about another entity\n\n"

    "ASSOCIATION AND NARRATIVE LINKS\n"
    "- introduced_by: one party introduced or recommended another\n"
    "- prior_dealings: parties had a documented prior business relationship\n"
    "- co_signatory: two people signed the same document in different roles\n"
    "- witness_for: person witnessed a transaction or document execution\n"
    "- mentioned_together: two parties consistently co-mentioned in suspicious contexts\n\n"

    "INSTRUCTIONS\n"
    "For EVERY relationship:\n"
    "1. Use the exact names as they appear in the documents — do not paraphrase or merge\n"
    "2. Identify the entity type of both source and target from: "
    "person, vendor, company, organization, government_body, bank_account, tender, invoice, po, address, phone, reference, document\n"
    "3. Choose the most specific relationship_type label from the categories above\n"
    "4. Quote the exact phrase from the document that supports the relationship (evidence_quote)\n"
    "5. Cite the document_id the relationship comes from\n"
    "6. Assign confidence 0.0–1.0: 0.9+ = explicitly stated; 0.7–0.89 = strongly implied; "
    "0.5–0.69 = circumstantial but notable; below 0.5 = omit\n\n"
    "Never invent a document_id, name, address, or fact not present in the input data. "
    "If the same relationship appears in multiple documents, emit one entry per document.\n\n"
    'Reply with strict JSON: {"relationships": [{"source_name": str, "source_type": str, '
    '"target_name": str, "target_type": str, "relationship_type": str, '
    '"evidence_quote": str, "document_id": str, "confidence": float}]}. '
    "Return an empty list only if there are genuinely no meaningful relationships."
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
            {
                "evidence_quote": item.get("evidence_quote"),
                "document_id": doc_id,
                "source_type": str(item.get("source_type") or "").strip().lower(),
                "target_type": str(item.get("target_type") or "").strip().lower(),
            },
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
    # Deduplicate: keep first occurrence of each (source, target, type) triple
    seen: set[tuple] = set()
    deduped = []
    for e in edges:
        key = (e["source_name"].lower().strip(), e["target_name"].lower().strip(), e["relationship_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    for e in deduped:
        db.insert_relationship(e)
    return deduped


def _edge(case_id, source_name, target_name, relationship_type, meta, source_flag="rule", reasoning=None, confidence=None):
    evidence = dict(meta)
    if confidence is not None:
        evidence["confidence"] = confidence
    edge = {
        "relationship_id": str(uuid.uuid4()),
        "case_id": case_id,
        "source_name": source_name,
        "target_name": target_name,
        "relationship_type": relationship_type,
        "evidence": evidence,
        "source": source_flag,
    }
    if reasoning is not None:
        edge["reasoning"] = reasoning
    return edge
