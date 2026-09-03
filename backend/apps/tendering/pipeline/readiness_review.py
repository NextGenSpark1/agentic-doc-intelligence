"""Submission readiness — the pre-submit scan.

A cross-record completeness audit spanning requirements, evidence links, document expiry
dates, and processing status. It answers one question a bid manager asks the night before a
deadline: *what is still missing, and can we submit?*

Three design commitments:

1. **The score is arithmetic, not judgement.** `compute_gaps` and `compute_score` are pure
   functions over rows already in the database. No LLM is involved in deciding readiness, so
   the number is reproducible and every point of it can be traced to a named gap. The LLM, if
   available, only writes prose *from* the computed gaps.

2. **Score and blockers are separate.** A percentage alone hides the one unmet mandatory
   requirement that will get the bid thrown out. `submission_blocked` is its own boolean with
   its own reasons, and the UI should lead with it.

3. **Readiness is advisory, never gating.** Nothing here writes `bid_decision` or marks a
   workspace submitted. It reports; a human decides.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

_MANDATORY_WEIGHT = 3
_OPTIONAL_WEIGHT = 1

_EXPIRY_WARNING_DAYS = 30
_CLOSING_SOON_DAYS = 7

BLOCKER, WARNING, INFO = "blocker", "warning", "info"


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _gap(gap_type: str, severity: str, message: str, **refs) -> dict:
    return {"gap_type": gap_type, "severity": severity, "message": message,
            **{key: value for key, value in refs.items() if value is not None}}


def is_satisfied(requirement: dict, links: list[dict], library_docs: dict[str, dict],
                 today: date) -> bool:
    """Is this requirement actually met?

    Two ways: a human marked it met/complete, or it has at least one confirmed evidence link
    to a library document that has not expired. A pending AI proposal does not count.
    """
    if requirement.get("status") == "met":
        return True
    if requirement.get("completion_status") == "complete":
        return True
    for link in links:
        if link.get("human_review_status") != "confirmed":
            continue
        document = library_docs.get(link.get("doc_id") or "")
        if document is None:
            continue
        expiry = _parse_date(document.get("expiry_date"))
        if expiry and expiry < today:
            continue
        return True
    return False


def compute_gaps(
    workspace: dict,
    requirements: list[dict],
    evidence_links: list[dict],
    documents: list[dict],
    library_docs: list[dict],
    today: date | None = None,
) -> list[dict]:
    """Every reason this workspace is not ready to submit. Pure — no DB, no LLM."""
    today = today or datetime.now(timezone.utc).date()
    library_index = {doc["doc_id"]: doc for doc in library_docs}

    links_by_req: dict[str, list[dict]] = {}
    for link in evidence_links:
        if link.get("human_review_status") != "dismissed":
            links_by_req.setdefault(link["req_id"], []).append(link)

    gaps: list[dict] = []
    closing = _parse_date(workspace.get("closing_date"))

    # ---- deadline ----
    if closing:
        days = (closing - today).days
        if days < 0:
            gaps.append(_gap("closing_date_passed", BLOCKER,
                             f"The closing date ({closing.isoformat()}) passed {abs(days)} days ago."))
        elif days <= _CLOSING_SOON_DAYS:
            gaps.append(_gap("closing_date_imminent", WARNING,
                             f"Only {days} day(s) remain until the closing date."))
    else:
        gaps.append(_gap("closing_date_unknown", WARNING,
                         "No closing date recorded — it could not be extracted and has not been set."))

    # ---- documents ----
    if not documents:
        gaps.append(_gap("no_documents", BLOCKER,
                         "No tender documents have been uploaded, so no requirements are known."))
    else:
        for document in documents:
            if document.get("extraction_status") not in ("done",):
                severity = BLOCKER if document.get("extraction_status") == "failed" else WARNING
                gaps.append(_gap(
                    "document_not_processed", severity,
                    f"'{document.get('filename') or document.get('document_id')}' is "
                    f"{document.get('extraction_status') or 'unprocessed'} — requirements in it have not been read.",
                    document_id=document.get("document_id"),
                ))

    # ---- requirements ----
    if not requirements:
        gaps.append(_gap("no_requirements", BLOCKER,
                         "No requirements have been extracted, so completeness cannot be assessed."))
    else:
        for requirement in requirements:
            req_id = requirement["req_id"]
            links = links_by_req.get(req_id, [])
            description = (requirement.get("description") or "")[:120]
            mandatory = bool(requirement.get("mandatory"))

            if requirement.get("status") == "unchecked":
                gaps.append(_gap(
                    "requirement_pending_review", WARNING,
                    f"Requirement has not been reviewed: \"{description}\"",
                    req_id=req_id,
                ))

            if not is_satisfied(requirement, links, library_index, today):
                if not links:
                    gaps.append(_gap(
                        "mandatory_requirement_unmet" if mandatory else "requirement_unmet",
                        BLOCKER if mandatory else WARNING,
                        f"No evidence attached for {'mandatory ' if mandatory else ''}requirement: "
                        f"\"{description}\"",
                        req_id=req_id,
                    ))
                elif all(link.get("human_review_status") == "pending" for link in links):
                    gaps.append(_gap(
                        "evidence_pending_review",
                        BLOCKER if mandatory else WARNING,
                        f"Evidence has been proposed but not approved for "
                        f"{'mandatory ' if mandatory else ''}requirement: \"{description}\"",
                        req_id=req_id,
                    ))

            if not requirement.get("owner"):
                gaps.append(_gap("requirement_unassigned", INFO,
                                 f"No owner assigned: \"{description}\"", req_id=req_id))

            # ---- evidence expiry, checked against the closing date ----
            for link in links:
                if link.get("human_review_status") != "confirmed":
                    continue
                document = library_index.get(link.get("doc_id") or "")
                if document is None:
                    continue
                expiry = _parse_date(document.get("expiry_date"))
                if not expiry:
                    continue
                if expiry < today:
                    gaps.append(_gap(
                        "evidence_expired", BLOCKER,
                        f"'{document.get('title')}' expired on {expiry.isoformat()} and cannot be "
                        f"submitted for: \"{description}\"",
                        req_id=req_id, doc_id=document["doc_id"],
                    ))
                elif closing and expiry < closing:
                    gaps.append(_gap(
                        "evidence_expires_before_closing", BLOCKER,
                        f"'{document.get('title')}' expires {expiry.isoformat()}, before the closing "
                        f"date ({closing.isoformat()}) — it will have lapsed at evaluation.",
                        req_id=req_id, doc_id=document["doc_id"],
                    ))
                elif (expiry - today).days <= _EXPIRY_WARNING_DAYS:
                    gaps.append(_gap(
                        "evidence_expiring_soon", WARNING,
                        f"'{document.get('title')}' expires in {(expiry - today).days} day(s).",
                        req_id=req_id, doc_id=document["doc_id"],
                    ))

    return gaps


def compute_score(requirements: list[dict], evidence_links: list[dict],
                  library_docs: list[dict], today: date | None = None) -> dict:
    """Weighted completeness of the requirement set.

    Mandatory requirements weigh triple. The score (0.0–1.0) measures progress; blockers
    are reported separately. The integer version (0–100) is written to `readiness_score`.
    """
    today = today or datetime.now(timezone.utc).date()
    library_index = {doc["doc_id"]: doc for doc in library_docs}

    links_by_req: dict[str, list[dict]] = {}
    for link in evidence_links:
        if link.get("human_review_status") != "dismissed":
            links_by_req.setdefault(link["req_id"], []).append(link)

    if not requirements:
        return {"score": 0.0, "satisfied": 0, "total": 0,
                "mandatory_satisfied": 0, "mandatory_total": 0}

    earned = possible = 0
    satisfied_count = mandatory_satisfied = mandatory_total = 0
    for requirement in requirements:
        mandatory = bool(requirement.get("mandatory"))
        weight = _MANDATORY_WEIGHT if mandatory else _OPTIONAL_WEIGHT
        possible += weight
        if mandatory:
            mandatory_total += 1
        if is_satisfied(requirement, links_by_req.get(requirement["req_id"], []),
                        library_index, today):
            earned += weight
            satisfied_count += 1
            if mandatory:
                mandatory_satisfied += 1

    return {
        "score": round(earned / possible, 4) if possible else 0.0,
        "satisfied": satisfied_count,
        "total": len(requirements),
        "mandatory_satisfied": mandatory_satisfied,
        "mandatory_total": mandatory_total,
    }


def summarise_gaps(gaps: list[dict]) -> dict:
    """Counts by severity, plus the go/no-go verdict."""
    blockers = [gap for gap in gaps if gap["severity"] == BLOCKER]
    return {
        "blockers": len(blockers),
        "warnings": sum(1 for gap in gaps if gap["severity"] == WARNING),
        "info": sum(1 for gap in gaps if gap["severity"] == INFO),
        "submission_blocked": bool(blockers),
        "blocking_reasons": [gap["message"] for gap in blockers[:10]],
    }


def build_report(
    workspace: dict,
    requirements: list[dict],
    evidence_links: list[dict],
    documents: list[dict],
    library_docs: list[dict],
    today: date | None = None,
) -> dict:
    """The full readiness read-model. Pure, so the whole report is unit-testable."""
    gaps = compute_gaps(workspace, requirements, evidence_links, documents, library_docs, today)
    scoring = compute_score(requirements, evidence_links, library_docs, today)
    severity_rank = {BLOCKER: 0, WARNING: 1, INFO: 2}
    return {
        "workspace_id": workspace.get("id"),
        **scoring,
        **summarise_gaps(gaps),
        "gaps": sorted(gaps, key=lambda gap: severity_rank.get(gap["severity"], 3)),
    }


def review(workspace_id: str) -> dict:
    """Run the readiness scan and persist the score.

    Writes only `readiness_score` (as integer 0–100) — advisory, never gating.
    `bid_decision` remains reachable only by human-invoked routes.
    """
    from .. import db

    workspace = db.get_tendering_workspace(workspace_id) or {}
    requirements = db.list_workspace_requirements_raw(workspace_id)
    evidence_links = db.list_evidence_links(workspace_id)
    documents = db.list_core_documents_for_workspace(workspace_id)
    org_id = workspace.get("org_id", "")
    library_docs = db.list_library_documents(org_id) if org_id else []

    report = build_report(workspace, requirements, evidence_links, documents, library_docs)

    score_int = round(report["score"] * 100)
    db.update_workspace(workspace_id, {"readiness_score": score_int})
    db.write_workspace_audit(workspace_id, "system", "readiness_reviewed", {
        "score": score_int,
        "blockers": report["blockers"],
        "warnings": report["warnings"],
        "submission_blocked": report["submission_blocked"],
    })
    return report


def narrate(report: dict) -> str:
    """A short prose readiness statement.

    The LLM writes only from the computed report — it cannot introduce a gap, change the
    score, or declare the workspace ready. If unavailable, the deterministic version stands.
    """
    import json
    from backend.core import llm
    from ..prompts import READINESS_REVIEW

    try:
        return llm.complete(
            tier="reasoning",
            messages=[
                {"role": "system", "content": READINESS_REVIEW},
                {"role": "user", "content": json.dumps(report, default=str)},
            ],
        )
    except Exception:
        return deterministic_narrative(report)


def deterministic_narrative(report: dict) -> str:
    """Readable readiness statement with no LLM — the fallback and the quality floor."""
    lines = [
        f"Readiness: {report['score'] * 100:.0f}% "
        f"({report['satisfied']} of {report['total']} requirements satisfied; "
        f"{report['mandatory_satisfied']} of {report['mandatory_total']} mandatory)."
    ]
    if report["submission_blocked"]:
        lines.append(f"NOT READY TO SUBMIT — {report['blockers']} blocking issue(s):")
        lines += [f"  - {reason}" for reason in report["blocking_reasons"]]
    else:
        lines.append("No blocking issues found.")
    if report["warnings"]:
        lines.append(f"{report['warnings']} warning(s) to review before submission.")
    return "\n".join(lines)
