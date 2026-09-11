"""Workspace summary — derived facts first, narrative second.

Everything quantitative is computed deterministically here; the LLM writes prose AND
extracts metadata (buyer, reference, closing date, contract value) from the raw markdown
saved during ADE extraction. If the LLM is unavailable the deterministic summary still
renders and backfill is skipped for that run.

Fields a human has already filled are never overwritten, and `bid_decision`/
`readiness_score` are untouchable here.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

# How many chars of markdown to send per document — enough for metadata on the cover page
# without blowing the context budget when there are multiple documents.
_MARKDOWN_CAP_CHARS = 8_000

# Workspace columns the LLM meta dict may fill when blank. Maps LLM key → workspace column.
_LLM_META_TO_WORKSPACE = {
    "buyer": "buyer_name",
    "reference": "tender_reference",
    "closing_date": "closing_date",
    "contract_value": "contract_value",
    "currency": "currency",
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
    try:
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
    workspace: dict,
    documents: list[dict],
    requirements: list[dict],
    today: date | None = None,
) -> dict:
    """Derive every number in the summary. Pure — no DB, no LLM, unit-testable."""
    live = [req for req in requirements]
    mandatory = [req for req in live if req.get("mandatory")]

    by_category: dict[str, dict] = {}
    for req in live:
        bucket = by_category.setdefault(
            req.get("category") or "other", {"total": 0, "mandatory": 0}
        )
        bucket["total"] += 1
        if req.get("mandatory"):
            bucket["mandatory"] += 1

    return {
        "tender_title": workspace.get("title"),
        "buyer": workspace.get("buyer"),
        "reference": workspace.get("reference"),
        "closing_date": workspace.get("closing_date"),
        "days_until_closing": days_until(workspace.get("closing_date"), today),
        "contract_value": workspace.get("contract_value"),
        "currency": workspace.get("currency"),
        "stage": workspace.get("stage"),
        "documents_processed": sum(1 for doc in documents if doc.get("extraction_status") == "done"),
        "documents_total": len(documents),
        "requirements_total": len(live),
        "requirements_mandatory": len(mandatory),
        "requirements_pending_review": sum(1 for req in live if req.get("status") == "unchecked"),
        "requirements_by_category": by_category,
    }


def _deterministic_summary(facts: dict) -> str:
    """Readable summary with no LLM involved — the fallback, and the floor on quality."""
    lines: list[str] = []
    buyer = facts.get("buyer")
    lines.append(
        f"{facts.get('tender_title') or 'This workspace'}"
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
        parts = [
            f"{cat.replace('_', ' ')} ({values['mandatory']})"
            for cat, values in hotspots if values["mandatory"]
        ]
        lines.append("Mandatory requirements concentrate in: " + ", ".join(parts) + ".")

    return "\n".join(lines)


def _backfill_from_llm_meta(workspace: dict, meta: dict) -> dict:
    """Build a patch dict from LLM-extracted meta fields, skipping already-filled columns."""
    patch: dict = {}
    for llm_key, workspace_col in _LLM_META_TO_WORKSPACE.items():
        if workspace.get(workspace_col) not in (None, "", 0):
            continue
        value = meta.get(llm_key)
        if value in (None, "", []):
            continue
        if llm_key == "closing_date":
            parsed = _parse_date(value)
            if parsed is None:
                continue
            value = parsed.isoformat()
        if llm_key == "contract_value":
            try:
                value = float(str(value).replace(",", "").strip())
            except (TypeError, ValueError):
                continue
        patch[workspace_col] = value
    return patch


def summarise(workspace_id: str) -> dict:
    """Summarise a tendering workspace from its extracted documents."""
    from backend.core import llm_reasoning
    from .. import db
    from ..prompts import TENDER_SUMMARY

    workspace = db.get_tendering_workspace(workspace_id) or {}
    documents = db.list_core_documents_for_workspace(workspace_id)
    requirements = db.list_workspace_requirements_raw(workspace_id)

    # Collect markdown from each document's ADE extraction for the LLM to read.
    document_excerpts = []
    for document in documents:
        extraction = db.get_extraction_by_document(document["document_id"])
        if not extraction:
            continue
        markdown = (extraction.get("extracted_json") or {}).get("markdown") or ""
        if markdown:
            document_excerpts.append({
                "filename": document.get("filename") or document.get("name"),
                "text": markdown[:_MARKDOWN_CAP_CHARS],
            })

    facts = compute_facts(workspace, documents, requirements)

    payload = {"facts": facts, "document_excerpts": document_excerpts}
    answer = llm_reasoning.ask(TENDER_SUMMARY, payload, workspace_id=workspace_id)

    if answer and isinstance(answer, dict):
        summary_text = str(answer.get("summary") or "").strip() or _deterministic_summary(facts)
        meta = answer.get("meta") or {}
        if isinstance(meta, dict):
            patch = _backfill_from_llm_meta(workspace, meta)
            if patch:
                db.update_workspace(workspace_id, patch)
                workspace = {**workspace, **patch}
    else:
        summary_text = _deterministic_summary(facts)

    db.update_workspace(workspace_id, {"ai_summary": summary_text})
    db.write_workspace_audit(workspace_id, "system", "workspace_summarised", {
        "requirements_total": facts["requirements_total"],
        "documents_processed": facts["documents_processed"],
    })
    return {
        "summary": summary_text,
        "requirements_total": facts["requirements_total"],
        "requirements_mandatory": facts["requirements_mandatory"],
        "days_until_closing": facts.get("days_until_closing"),
    }
