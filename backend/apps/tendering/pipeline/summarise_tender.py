"""Tender summary — derived facts first, narrative second.

Same discipline as `investigation/pipeline/summarise.py`: everything quantitative is computed
deterministically here, and the LLM only writes prose *from those facts*. It cannot introduce a
date, an amount, or a requirement, because it is never asked to produce one — and if the LLM is
unavailable the deterministic summary still renders.

This stage also back-fills the tender row from the extracted tender notice. That is
extraction, not decision-making: buyer and closing date are facts printed in the document.
Fields a human has already filled are never overwritten, and `bid_decision` is untouchable
here (Rule 3).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

# Which TenderNotice extraction field back-fills which `tenders` column.
_META_FROM_EXTRACTION = {
    "buyer": "buyer_name",
    "reference_no": "tender_reference",
    "closing_date": "closing_date",
    "contract_value": "contract_value",
    "currency": "currency",
    "submission_method": "submission_method",
}


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text[:len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    try:  # ISO timestamps from the database
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def days_until(closing: object, today: date | None = None) -> int | None:
    """Days remaining until the closing date. Negative once it has passed."""
    parsed = _parse_date(closing)
    if parsed is None:
        return None
    return (parsed - (today or datetime.now(timezone.utc).date())).days


def compute_facts(
    tender: dict,
    documents: list[dict],
    requirements: list[dict],
    today: date | None = None,
) -> dict:
    """Derive every number in the summary. Pure — no DB, no LLM, unit-testable."""
    live = [r for r in requirements if r.get("human_review_status") != "dismissed"]
    mandatory = [r for r in live if r.get("is_mandatory")]

    by_category: dict[str, dict] = {}
    for req in live:
        bucket = by_category.setdefault(
            req.get("category") or "other", {"total": 0, "mandatory": 0}
        )
        bucket["total"] += 1
        if req.get("is_mandatory"):
            bucket["mandatory"] += 1

    return {
        "tender_title": tender.get("title"),
        "buyer": tender.get("buyer"),
        "reference_no": tender.get("reference_no"),
        "closing_date": tender.get("closing_date"),
        "days_until_closing": days_until(tender.get("closing_date"), today),
        "contract_value": tender.get("contract_value"),
        "currency": tender.get("currency"),
        "submission_method": tender.get("submission_method"),
        "tender_stage": tender.get("tender_stage"),
        "documents_processed": sum(1 for d in documents if d.get("extraction_status") == "done"),
        "documents_total": len(documents),
        "requirements_total": len(live),
        "requirements_mandatory": len(mandatory),
        "requirements_pending_review": sum(
            1 for r in live if r.get("human_review_status") == "pending"
        ),
        "requirements_by_category": by_category,
    }


def _deterministic_summary(facts: dict) -> str:
    """Readable summary with no LLM involved — the fallback, and the floor on quality."""
    lines: list[str] = []
    buyer = facts.get("buyer")
    lines.append(
        f"{facts.get('tender_title') or 'This tender'}"
        + (f" — issued by {buyer}." if buyer else ".")
    )

    days = facts.get("days_until_closing")
    if days is not None:
        if days < 0:
            lines.append(f"Closing date has passed ({abs(days)} days ago).")
        else:
            lines.append(f"{days} days remain until the closing date ({facts.get('closing_date')}).")
    elif facts.get("closing_date"):
        lines.append(f"Closing date: {facts['closing_date']}.")
    else:
        lines.append("Closing date is not stated in the documents processed so far.")

    if facts.get("contract_value"):
        lines.append(f"Estimated value: {facts.get('currency') or ''} {facts['contract_value']}".strip() + ".")

    lines.append(
        f"{facts['documents_processed']} of {facts['documents_total']} documents processed; "
        f"{facts['requirements_total']} requirements extracted "
        f"({facts['requirements_mandatory']} mandatory, "
        f"{facts['requirements_pending_review']} awaiting review)."
    )

    hotspots = sorted(
        facts.get("requirements_by_category", {}).items(),
        key=lambda kv: kv[1]["mandatory"], reverse=True,
    )[:3]
    if hotspots and hotspots[0][1]["mandatory"]:
        parts = [f"{cat.replace('_', ' ')} ({v['mandatory']})" for cat, v in hotspots if v["mandatory"]]
        lines.append("Mandatory requirements concentrate in: " + ", ".join(parts) + ".")

    return "\n".join(lines)


def backfill_meta(tender: dict, extracted: dict) -> dict:
    """Fields to copy from a tender-notice extraction into blank `tenders` columns.

    Only fills what is empty — a value a human typed is never overwritten by extraction.
    Returns just the patch, so the caller can skip the write when nothing changed. Decision
    columns (`bid_decision`, `readiness_score`) are absent from the map by construction, so
    extraction can never write one.
    """
    patch: dict = {}
    for meta_field, extraction_field in _META_FROM_EXTRACTION.items():
        if tender.get(meta_field) not in (None, "", 0):
            continue
        value = extracted.get(extraction_field)
        if value in (None, "", []):
            continue
        if meta_field == "closing_date":
            parsed = _parse_date(value)
            if parsed is None:
                continue
            value = parsed.isoformat()
        patch[meta_field] = value
    return patch


def summarise(tender_id: str) -> dict:
    from backend.core import llm

    from .. import db
    from ..prompts import TENDER_SUMMARY

    tender = db.get_tender(tender_id) or {}
    documents = db.list_tender_documents(tender_id)
    requirements = db.list_requirements(tender_id)

    # Back-fill tender metadata from the tender-notice extraction, if one exists.
    for document in documents:
        extraction = db.get_extraction_by_document(document["document_id"])
        if not extraction:
            continue
        patch = backfill_meta(tender, extraction.get("extracted_json") or {})
        if patch:
            db.update_tender(tender_id, {**patch, "updated_at": datetime.now(timezone.utc).isoformat()})
            tender = {**tender, **patch}

    facts = compute_facts(tender, documents, requirements)

    try:
        summary_text = llm.complete(
            tier="reasoning",
            messages=[
                {"role": "system", "content": TENDER_SUMMARY},
                {"role": "user", "content": json.dumps(facts, default=str)},
            ],
        )
    except Exception:
        summary_text = _deterministic_summary(facts)

    db.update_tender(tender_id, {"ai_summary": summary_text})
    return {
        "summary": summary_text,
        "requirements_total": facts["requirements_total"],
        "requirements_mandatory": facts["requirements_mandatory"],
        "days_until_closing": facts["days_until_closing"],
    }
