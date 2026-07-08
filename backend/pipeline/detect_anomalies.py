"""Stage 4d — anomaly detection (rule-based for the MVP).

`compute_findings(extractions)` is PURE: it takes a list of extraction dicts and returns
finding dicts. No DB, no IDs, no I/O — so it is trivially unit-testable, which matters
because these rules must survive legal scrutiny. `detect(case_id)` is the thin wrapper that
loads, calls the pure function, stamps IDs/status, and persists.

Rules: duplicate invoices, shared bank accounts across vendors, split payments. Detection
is deliberately NOT delegated to an opaque LLM — only the narrative (in summarise) is.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone

_SPLIT_PAYMENT_WINDOW_DAYS = 3
_NON_NUMERIC_RE = re.compile(r"[^\d.]")


def _to_float(v) -> float:
    """Parse a numeric value that may carry currency symbols, commas, or spaces."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    cleaned = _NON_NUMERIC_RE.sub("", str(v).replace(",", ""))
    return float(cleaned) if cleaned else 0.0


def _finding(ftype: str, severity: str, confidence: float, statement: str, doc_ids: list[str]) -> dict:
    return {
        "finding_type": ftype,
        "severity": severity,
        "confidence": confidence,
        "statement": statement,
        "supporting_document_ids": doc_ids,
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


def detect(case_id: str) -> list[dict]:
    from .. import db

    # Clear previous pending findings to avoid duplicates on re-run
    db.get_client().table("findings").delete().eq("case_id", case_id).eq("human_review_status", "pending").execute()

    findings = compute_findings(db.list_extractions(case_id))
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
