"""Stage 4d — anomaly detection.

`compute_findings(extractions)` is PURE: it takes a list of extraction dicts and returns
finding dicts. No DB, no IDs, no I/O — so it is trivially unit-testable, which matters
because these rules must survive legal scrutiny. `detect(case_id)` is the thin wrapper that
loads, calls the pure function, stamps IDs/status, and persists.

AI-first: `detect()` runs a case-reasoning LLM pass over the whole case (every extraction plus
the entities/relationships/timeline already computed) as the PRIMARY source of findings — it
surfaces things that need actual cross-document reasoning (a vendor formed right before a
contract award, narrative inconsistencies between documents, circular payments) which the
hard-coded rules can't reach. The deterministic rules (`compute_findings`: duplicate invoices,
shared bank accounts, split payments, budget-ceiling proximity) run only as a fallback when the
LLM returns nothing (quota exhausted, key missing, provider down) — they stay pure and
unit-tested, which matters because these must survive legal scrutiny. Every LLM finding is
tagged source="llm" (rule findings are source="rule") and must cite at least one supporting
document_id we actually sent; anything that cites a document we never sent is dropped.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from . import llm_reasoning

_SPLIT_PAYMENT_WINDOW_DAYS = 3
_NON_NUMERIC_RE = re.compile(r"[^\d.]")

_FINDINGS_PROMPT = (
    "You are a forensic investigation analyst. Below is the full context for one case: every "
    "document's extracted structured fields, plus the entities, relationships, and timeline "
    "already established. Rule-based checks already caught duplicate invoices, shared bank "
    "accounts, split payments, and budget-ceiling proximity — do NOT repeat those. Look instead "
    "for things that need real cross-document reasoning: a vendor formed shortly before winning "
    "a contract, a vendor sharing a director with the approving officer's other awards, "
    "narrative inconsistencies between two documents describing the same event, circular or "
    "round-trip payments, timing that doesn't logically add up. Every finding must cite at "
    "least one supporting document_id that is present in the input below — never invent a "
    "document, entity, or fact that isn't there.\n\n"
    'Reply with strict JSON: {"findings": [{"finding_type": str, "severity": '
    '"high"|"medium"|"low", "confidence": float, "statement": str, '
    '"supporting_document_ids": [str, ...]}]}. Return an empty list if nothing stands out '
    "beyond what the rules already found."
)


def _to_float(v) -> float:
    """Parse a numeric value that may carry currency symbols, commas, or spaces."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    cleaned = _NON_NUMERIC_RE.sub("", str(v).replace(",", ""))
    return float(cleaned) if cleaned else 0.0


def _finding(ftype: str, severity: str, confidence: float, statement: str, doc_ids: list[str],
             source: str = "rule") -> dict:
    return {
        "finding_type": ftype,
        "severity": severity,
        "confidence": confidence,
        "statement": statement,
        "supporting_document_ids": doc_ids,
        "source": source,
    }


def compute_findings(extractions: list[dict]) -> list[dict]:
    findings: list[dict] = []

    # Rule 1: duplicate invoice numbers across documents
    inv_to_docs: dict[str, list] = defaultdict(list)
    for ex in extractions:
        inv = ((ex.get("extracted_json") or {}).get("invoice_number") or "").strip()
        if inv:
            inv_to_docs[inv].append(ex["document_id"])
    for inv, docs in inv_to_docs.items():
        if len(docs) > 1:
            findings.append(_finding(
                "duplicate_invoice", "high", 0.95,
                f"Invoice number {inv} appears on {len(docs)} separate documents.", docs))

    # Rule 2: shared bank account across multiple vendors
    acct_to: dict[str, set] = defaultdict(set)
    acct_docs: dict[str, set] = defaultdict(set)
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        acct = (d.get("bank_account") or "").strip()
        vendor = (d.get("vendor_name") or d.get("awarded_vendor") or "").strip()
        if acct and vendor:
            acct_to[acct].add(vendor)
            acct_docs[acct].add(ex["document_id"])
    for acct, vendors in acct_to.items():
        if len(vendors) > 1:
            findings.append(_finding(
                "shared_bank_account", "high", 0.9,
                f"Bank account {acct} is shared by {len(vendors)} vendors: "
                f"{', '.join(sorted(vendors))}.", sorted(acct_docs[acct])))

    # Rule 3: split payments — same vendor, multiple payments within a short window
    by_vendor: dict[str, list] = defaultdict(list)
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        vendor = (d.get("vendor_name") or d.get("awarded_vendor") or "").strip()
        amount = d.get("amount") or d.get("contract_value")
        pdate = d.get("payment_date")
        if vendor and amount and pdate:
            try:
                day = datetime.fromisoformat(str(pdate)).date()
                by_vendor[vendor].append((day, _to_float(amount), ex["document_id"]))
            except (ValueError, TypeError):
                continue
    for vendor, payments in by_vendor.items():
        payments.sort()
        for i in range(len(payments) - 1):
            gap = (payments[i + 1][0] - payments[i][0]).days
            if 0 <= gap <= _SPLIT_PAYMENT_WINDOW_DAYS:
                docs = [payments[i][2], payments[i + 1][2]]
                total = payments[i][1] + payments[i + 1][1]
                findings.append(_finding(
                    "split_payment", "medium", 0.7,
                    f"Two payments to {vendor} within {gap} day(s) totalling {total:.2f} "
                    f"— possible threshold splitting.", docs))

    # Rule 4: contract value near approved budget ceiling (≥ 95%) — procurement fraud
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        try:
            budget = _to_float(d.get("budget_amount"))
            contract = _to_float(d.get("contract_value"))
            if budget > 0 and contract > 0 and budget > contract and (contract / budget) >= 0.95:
                pct = round(contract / budget * 100, 1)
                vendor = (d.get("awarded_vendor") or "Unknown vendor").strip()
                findings.append(_finding(
                    "budget_ceiling_proximity", "high", 0.85,
                    f"Contract to {vendor} ({contract:,.2f}) is {pct}% of the approved "
                    f"budget ({budget:,.2f}) — possible budget manipulation.",
                    [ex["document_id"]]))
        except (ValueError, TypeError):
            continue

    return findings


def _llm_findings(case_id: str, extractions: list[dict]) -> list[dict]:
    from .. import db

    valid_doc_ids = {ex["document_id"] for ex in extractions}
    if not valid_doc_ids:
        return []

    payload = {
        "documents": [
            {"document_id": ex["document_id"], "fields": ex.get("extracted_json") or {}}
            for ex in extractions
        ],
        "entities": [
            {"type": e.get("entity_type"), "name": e.get("canonical_name"),
             "aliases": e.get("aliases"), "document_ids": e.get("source_document_ids")}
            for e in db.list_entities(case_id)
        ],
        "relationships": [
            {"source": r.get("source_name"), "target": r.get("target_name"),
             "type": r.get("relationship_type"), "evidence": r.get("evidence")}
            for r in db.list_relationships(case_id)
        ],
        "timeline": [
            {"date": t.get("event_date"), "label": t.get("label"), "document_id": t.get("document_id")}
            for t in db.get_client().table("timeline_events").select("*").eq("case_id", case_id).execute().data
        ],
    }
    result = llm_reasoning.ask(_FINDINGS_PROMPT, payload, case_id)
    items = result.get("findings") if isinstance(result, dict) else None
    if not items or not isinstance(items, list):
        return []

    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        statement = str(item.get("statement") or "").strip()
        doc_ids = [d for d in (item.get("supporting_document_ids") or []) if d in valid_doc_ids]
        if not statement or not doc_ids:
            continue  # ungrounded — drop rather than persist an unsupported claim
        ftype = str(item.get("finding_type") or "").strip() or "llm_detected"
        out.append(_finding(
            ftype,
            llm_reasoning.clamp_severity(item.get("severity")),
            llm_reasoning.clamp_confidence(item.get("confidence"), default=0.6),
            statement, doc_ids, source="llm",
        ))
    return out


def detect(case_id: str) -> list[dict]:
    from .. import db

    # Clear previous pending findings to avoid duplicates on re-run
    db.get_client().table("findings").delete().eq("case_id", case_id).eq("human_review_status", "pending").execute()

    extractions = db.list_extractions(case_id)
    # AI-first: LLM cross-document reasoning is the primary output
    findings = _llm_findings(case_id, extractions)
    # Rules are a fallback only when LLM returns nothing (quota exhausted, key missing, etc.)
    if not findings:
        findings = compute_findings(extractions)

    persisted = []
    for f in findings:
        row = {
            **f,
            "finding_id": str(uuid.uuid4()),
            "case_id": case_id,
            "human_review_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        persisted.append(db.insert_finding(row))
    return persisted
