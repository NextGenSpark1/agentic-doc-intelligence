"""Bid / no-bid recommendation — the advisory layer over the readiness report.

The deterministic readiness report already says what is missing. This turns it into the argument
a bid manager actually has to make: pursue this tender or walk away, and on what grounds.

Rule 3 draws the line here, harder than anywhere else in the product. This writes
`workspace_bid_decisions.recommendation`; it never touches `tender_workspaces.bid_decision`,
which is the team's own decision and is only reachable from the route a person clicks. A
recommendation is an argument to be weighed, and the export the team sends onward carries both.

The readiness score is passed through unchanged. The model is told it, so it can reason about it,
and is told it may not restate it as its own — a second, differing score in the same report is
how a team ends up trusting the wrong one.
"""
from __future__ import annotations

from datetime import datetime, timezone

_VALID_RECOMMENDATIONS = ("bid", "no_bid", "pending")
_MAX_ITEMS = 6
_MAX_ITEM_CHARS = 300
_MAX_RATIONALE_CHARS = 2_000


def _clean_items(raw: object, limit: int = _MAX_ITEMS) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    for entry in raw:
        text = str(entry or "").strip()[:_MAX_ITEM_CHARS]
        if text:
            items.append(text)
        if len(items) == limit:
            break
    return items


def validate_recommendation(raw: object, report: dict) -> dict | None:
    """Keep the model's answer only if it is usable, and never let it outrank the report.

    A recommendation with no rationale is dropped (Rule 2: the argument is the point). A "bid"
    while the report says submission is blocked is downgraded to "pending" rather than discarded:
    the reasoning is still worth showing, but the model does not get to wave a blocker through.
    """
    if not isinstance(raw, dict):
        return None

    recommendation = str(raw.get("recommendation") or "").strip().lower()
    if recommendation not in _VALID_RECOMMENDATIONS:
        return None

    rationale = str(raw.get("rationale") or "").strip()[:_MAX_RATIONALE_CHARS]
    if not rationale:
        return None

    if recommendation == "bid" and report.get("submission_blocked"):
        recommendation = "pending"
        rationale = ("Downgraded to pending: the readiness report still has blocking issues. "
                     + rationale)

    return {
        "recommendation": recommendation,
        "rationale": rationale,
        "strengths": _clean_items(raw.get("strengths")),
        "risks": _clean_items(raw.get("risks")),
    }


def deterministic_recommendation(report: dict) -> dict:
    """The answer when the model is unavailable — the report, restated as an argument.

    Never "bid": with no model to weigh the case, the honest position is that the team has not
    been advised yet. Blockers are surfaced either way, which is the part that matters.
    """
    blockers = report.get("blocking_reasons") or []
    satisfied = report.get("satisfied") or 0
    total = report.get("total") or 0
    mandatory_satisfied = report.get("mandatory_satisfied") or 0
    mandatory_total = report.get("mandatory_total") or 0

    if report.get("submission_blocked"):
        recommendation = "no_bid" if not blockers[:1] else "pending"
        summary = (f"{len(blockers)} blocking issue(s) stand between this workspace and a "
                   f"submission.")
    else:
        recommendation = "pending"
        summary = "No blocking issues were found by the readiness check."

    rationale = (
        f"{summary} {satisfied} of {total} requirements are satisfied, including "
        f"{mandatory_satisfied} of {mandatory_total} mandatory ones. "
        "This summary was produced without the AI advisor, which was unavailable — it restates "
        "the readiness report and is not a recommendation to bid."
    )
    return {
        "recommendation": recommendation,
        "rationale": rationale,
        "strengths": ([f"{mandatory_satisfied} of {mandatory_total} mandatory requirements "
                       f"already have approved evidence"] if mandatory_satisfied else []),
        "risks": [str(reason) for reason in blockers[:_MAX_ITEMS]],
    }


def _payload(workspace: dict, report: dict) -> dict:
    return {
        "tender": {
            "title": workspace.get("title"),
            "buyer": workspace.get("buyer"),
            "closing_date": str(workspace.get("closing_date") or "") or None,
            "contract_value": workspace.get("contract_value"),
            "currency": workspace.get("currency"),
            "stage": workspace.get("stage"),
        },
        "readiness": {
            "score_percent": round((report.get("score") or 0) * 100),
            "submission_blocked": report.get("submission_blocked"),
            "requirements_satisfied": report.get("satisfied"),
            "requirements_total": report.get("total"),
            "mandatory_satisfied": report.get("mandatory_satisfied"),
            "mandatory_total": report.get("mandatory_total"),
            "blocking_reasons": report.get("blocking_reasons") or [],
            "gaps": [
                {"type": gap.get("gap_type"), "severity": gap.get("severity"),
                 "message": gap.get("message")}
                for gap in (report.get("gaps") or [])[:40]
            ],
        },
    }


def generate(workspace_id: str) -> dict:
    """Build, persist and return a bid recommendation for one workspace.

    Runs the readiness report fresh rather than reading the stored score: the recommendation has
    to rest on the evidence position right now, not on whatever the last analysis left behind.
    """
    from .. import db
    from ..prompts import BID_DECISION
    from . import readiness_review

    workspace = db.get_tendering_workspace(workspace_id) or {}
    requirements = db.list_workspace_requirements_raw(workspace_id)
    evidence_links = db.list_evidence_links(workspace_id)
    documents = db.list_core_documents_for_workspace(workspace_id)
    org_id = workspace.get("org_id") or ""
    library_docs = db.list_library_documents(org_id) if org_id else []

    report = readiness_review.build_report(
        workspace, requirements, evidence_links, documents, library_docs
    )

    from backend.core import llm_reasoning

    answer = llm_reasoning.ask(BID_DECISION, _payload(workspace, report),
                               workspace_id=workspace_id)
    advised = validate_recommendation(answer, report)
    source = "llm"
    if advised is None:
        advised = deterministic_recommendation(report)
        source = "deterministic"

    record = {
        "workspace_id": workspace_id,
        "recommendation": advised["recommendation"],
        # The report's score, not the model's: one number, computed one way.
        "score": round((report.get("score") or 0) * 100),
        "rationale": advised["rationale"],
        "strengths": advised["strengths"],
        "risks": advised["risks"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    saved = db.save_workspace_bid_decision(workspace_id, record) or record

    db.write_workspace_audit(workspace_id, "system", "bid_decision_generated", {
        "recommendation": record["recommendation"],
        "score": record["score"],
        "submission_blocked": report.get("submission_blocked"),
        "source": source,
    })
    return saved
