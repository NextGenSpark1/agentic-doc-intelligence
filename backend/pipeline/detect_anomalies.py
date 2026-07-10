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
    "You are a senior forensic analyst with expertise across procurement fraud, financial crime, "
    "corruption, conflict of interest, money laundering, and document forgery. "
    "You are examining a full investigation case. Below is the complete case context: every "
    "document's extracted structured fields (including any relationship_indicators, risk_notes, "
    "compliance_flags, or narrative observations captured during extraction), plus the entities, "
    "relationships, and timeline already established from prior analysis passes.\n\n"
    "Rule-based checks have already flagged duplicate invoices, shared bank accounts, split "
    "payments, and budget-ceiling proximity — do NOT repeat those.\n\n"

    "Systematically check every category below. Report any finding you can support with evidence "
    "from the documents — do not limit yourself to the patterns listed. These are starting points, "
    "not an exhaustive ceiling.\n\n"

    "IDENTITY AND NAME PATTERNS\n"
    "- Approving officer's surname or given name appears in the vendor/company name "
    "(e.g. officer 'Rashid' approves 'Rashid & Farid Construction') — strong conflict indicator\n"
    "- Director or shareholder of the vendor shares a name with a public official, officer, or "
    "internal staff member in the awarding organisation\n"
    "- Same person appears as both a signatory for the vendor and an approver for the awarding body\n"
    "- Entity names that are near-identical or differ only by a word (shell company variation)\n\n"

    "ADDRESS AND CONTACT OVERLAP\n"
    "- Vendor director's registered address matches a home or emergency-contact address of an "
    "approving officer or internal staff member found in any document\n"
    "- Multiple vendors sharing the same registered address (possible shell/front company cluster)\n"
    "- Same phone number, email, or contact appearing across different vendors or individuals\n"
    "- Vendor business address is a residential address or virtual-office indicator\n\n"

    "VENDOR ELIGIBILITY AND REGISTRATION\n"
    "- Vendor incorporated or registered within 6 months of contract award\n"
    "- Vendor age at time of award suggests no track record for a contract of that scale or complexity\n"
    "- Vendor's stated business nature does not match the contract scope\n"
    "- Vendor registration number, tax ID, or licence missing or inconsistent across documents\n\n"

    "PROCUREMENT PROCESS INTEGRITY\n"
    "- Open or competitive tender waived without adequate documented justification\n"
    "- Emergency or urgent procurement clause invoked but no independent technical urgency report found\n"
    "- Procurement steps out of logical order (award before evaluation, payment before contract, "
    "invoice date before award date)\n"
    "- Conflict-of-interest declaration missing, incomplete, or not submitted by the approving officer\n"
    "- Single-source or direct negotiation used repeatedly for the same vendor or officer combination\n"
    "- Evaluation criteria or scoring sheets absent from the procurement file\n"
    "- Contract scope, timeline, or value modified significantly after award without re-tendering\n\n"

    "FINANCIAL PATTERNS\n"
    "- Advance or mobilisation payment processed before compliance documents were cleared\n"
    "- Payment authorised by the same person who approved the contract award\n"
    "- Round-number or suspiciously uniform payment amounts across multiple transactions\n"
    "- Large advance payment (above 20–30% of contract) without performance bond or insurance\n"
    "- Invoiced amount inflated relative to contract value or market benchmarks stated in documents\n"
    "- Circular payment: funds flow A → B → C → back to A or a related party\n"
    "- Layered transactions: multiple intermediaries with no clear commercial purpose\n"
    "- Payments to a bank account not previously registered to the vendor\n"
    "- Transaction amounts structured just below reporting or approval thresholds\n\n"

    "CONFLICT OF INTEREST AND RELATED-PARTY INDICATORS\n"
    "- Any relationship_indicators field mentioning family, business, or personal ties between "
    "vendor parties and approving officers\n"
    "- Director or beneficial owner of vendor is a current or former employee of the awarding body\n"
    "- Vendor's directors or shareholders include relatives of approving officers (even if not "
    "explicitly stated — look for surname matches or address overlaps as circumstantial evidence)\n"
    "- Approving officer is also listed as a witness, signatory, or contact in vendor documents\n"
    "- Risk or compliance notes in extracted fields flagging a relationship or undisclosed interest\n\n"

    "DOCUMENT INTEGRITY AND CONSISTENCY\n"
    "- Dates, amounts, reference numbers, or names that differ between documents describing the "
    "same transaction or event\n"
    "- A document references an attachment, report, or supporting file that is absent from the case\n"
    "- Missing signatures, missing dates, or unsigned approvals on documents that require them\n"
    "- A memo or review document explicitly notes missing compliance items — treat each noted gap "
    "as a finding in its own right\n"
    "- Document numbering gaps or sequence anomalies suggesting removed or inserted pages\n"
    "- Fonts, formatting, or metadata inconsistencies suggesting alteration or fabrication\n\n"

    "COMMUNICATION AND BEHAVIOURAL PATTERNS\n"
    "- Communications that reveal pre-arrangement, bid coordination, or price-fixing intent\n"
    "- Use of informal channels (personal email, messaging) for official procurement decisions\n"
    "- Urgency language used to bypass controls ('must award today', 'waive the process')\n"
    "- Commitments made before formal approval, suggesting decision was predetermined\n\n"

    "CONCENTRATION AND SYSTEMIC RISK\n"
    "- Multiple contracts awarded to the same vendor by the same officer across the case documents\n"
    "- All contracts in a programme going to vendors with common directors, addresses, or bank accounts\n"
    "- A single officer approving an unusually high volume or value of awards without countersignature\n\n"

    "GROUNDING RULES — NON-NEGOTIABLE\n"
    "Every finding must cite at least one document_id present in the input. "
    "Never invent a document, entity, name, amount, or date not present in the provided data. "
    "If a pattern is partially supported, state what is confirmed and what requires further investigation. "
    "A finding that says 'cannot be confirmed from documents alone' is still valuable — flag it.\n\n"

    'Reply with strict JSON: {"findings": [{"finding_type": str, '
    '"severity": "high"|"medium"|"low", "confidence": float (0.0-1.0), '
    '"statement": str, "supporting_document_ids": [str]}]}.\n'
    "Severity: high = direct evidence of fraud, violation, or undisclosed conflict; "
    "medium = suspicious pattern that warrants investigation or escalation; "
    "low = procedural gap, missing document, or minor irregularity worth noting.\n"
    "Return an empty list only if there is genuinely nothing to flag."
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
