"""Submission readiness — the pre-submit scan.

A cross-record completeness audit spanning requirements, evidence links, vault expiry dates,
documents, and tasks. It answers one question a bid manager asks the night before a deadline:
*what is still missing, and can we submit?*

Three design commitments:

1. **The score is arithmetic, not judgement.** `compute_gaps` and `compute_score` are pure
   functions over rows already in the database. No LLM is involved in deciding readiness, so
   the number is reproducible and every point of it can be traced to a named gap. The LLM, if
   available, only writes prose *from* the computed gaps.

2. **Score and blockers are separate.** A percentage alone hides the one unmet mandatory
   requirement that will get the bid thrown out. `submission_blocked` is its own boolean with
   its own reasons, and the UI should lead with it.

3. **Readiness is advisory, never gating (Rule 3).** Nothing here writes `bid_decision` or
   marks a tender submitted. It reports; a human decides.

Gaps are computed on demand rather than stored: they are derived entirely from current state,
so a persisted copy would be stale the moment anyone approves a document. Only the score is
written back, onto `tenders.readiness_score`.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

# Requirement weighting. A mandatory requirement carries three times a discretionary one:
# missing it is usually disqualifying, missing an optional one usually costs a few points.
_MANDATORY_WEIGHT = 3
_OPTIONAL_WEIGHT = 1

# A certificate valid today but expiring before the closing date is a trap — it lapses while
# the bid is still being evaluated.
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
            **{k: v for k, v in refs.items() if v is not None}}


def is_satisfied(requirement: dict, links: list[dict], vault: dict[str, dict],
                 today: date) -> bool:
    """Is this requirement actually met?

    Two ways: a human marked it complete, or it has at least one *approved* evidence link to a
    vault document that is neither expired nor superseded. A pending AI proposal does not count
    — that is Rule 3: the AI suggesting evidence is not the same as the team having it.
    """
    if requirement.get("completion_status") == "complete":
        return True
    for link in links:
        if link.get("human_review_status") != "confirmed":
            continue
        document = vault.get(link.get("supplier_document_id") or "")
        if document is None:
            continue
        if document.get("superseded_by"):
            continue
        expiry = _parse_date(document.get("expiry_date"))
        if expiry and expiry < today:
            continue
        return True
    return False


def compute_gaps(
    tender: dict,
    requirements: list[dict],
    evidence_links: list[dict],
    documents: list[dict],
    vault_documents: list[dict],
    tasks: list[dict],
    today: date | None = None,
) -> list[dict]:
    """Every reason this tender is not ready to submit. Pure — no DB, no LLM."""
    today = today or datetime.now(timezone.utc).date()
    vault = {d["supplier_document_id"]: d for d in vault_documents}

    links_by_requirement: dict[str, list[dict]] = {}
    for link in evidence_links:
        if link.get("human_review_status") != "dismissed":
            links_by_requirement.setdefault(link["requirement_id"], []).append(link)

    live = [r for r in requirements if r.get("human_review_status") != "dismissed"]
    gaps: list[dict] = []
    closing = _parse_date(tender.get("closing_date"))

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
    unprocessed = [d for d in documents if d.get("extraction_status") not in ("done",)]
    for document in unprocessed:
        severity = BLOCKER if document.get("extraction_status") == "failed" else WARNING
        gaps.append(_gap(
            "document_not_processed", severity,
            f"'{document.get('filename') or document.get('document_id')}' is "
            f"{document.get('extraction_status') or 'unprocessed'} — requirements in it have not been read.",
            document_id=document.get("document_id"),
        ))
    if not documents:
        gaps.append(_gap("no_documents", BLOCKER,
                         "No tender documents have been uploaded, so no requirements are known."))

    # ---- requirements ----
    for requirement in live:
        rid = requirement["requirement_id"]
        links = links_by_requirement.get(rid, [])
        description = (requirement.get("description") or "")[:120]
        mandatory = bool(requirement.get("is_mandatory"))

        if requirement.get("human_review_status") == "pending":
            gaps.append(_gap(
                "requirement_pending_review", WARNING,
                f"Requirement has not been reviewed by anyone yet: \"{description}\"",
                requirement_id=rid,
            ))

        if not is_satisfied(requirement, links, vault, today):
            if not links:
                gaps.append(_gap(
                    "mandatory_requirement_unmet" if mandatory else "requirement_unmet",
                    BLOCKER if mandatory else WARNING,
                    f"No evidence attached for {'mandatory ' if mandatory else ''}requirement: "
                    f"\"{description}\"",
                    requirement_id=rid,
                ))
            elif all(l.get("human_review_status") == "pending" for l in links):
                gaps.append(_gap(
                    "evidence_pending_review",
                    BLOCKER if mandatory else WARNING,
                    f"Evidence has been proposed but not approved for "
                    f"{'mandatory ' if mandatory else ''}requirement: \"{description}\"",
                    requirement_id=rid,
                ))

        if not requirement.get("owner_id"):
            gaps.append(_gap("requirement_unassigned", INFO,
                             f"No owner assigned: \"{description}\"", requirement_id=rid))

        # ---- evidence expiry, checked against the CLOSING date, not today ----
        for link in links:
            if link.get("human_review_status") != "confirmed":
                continue
            document = vault.get(link.get("supplier_document_id") or "")
            if document is None:
                continue
            if document.get("superseded_by"):
                gaps.append(_gap(
                    "evidence_superseded", WARNING,
                    f"'{document.get('title')}' has been replaced by a newer version but is "
                    f"still attached to: \"{description}\"",
                    requirement_id=rid, supplier_document_id=document["supplier_document_id"],
                ))
                continue
            expiry = _parse_date(document.get("expiry_date"))
            if not expiry:
                continue
            if expiry < today:
                gaps.append(_gap(
                    "evidence_expired", BLOCKER,
                    f"'{document.get('title')}' expired on {expiry.isoformat()} and cannot be "
                    f"submitted for: \"{description}\"",
                    requirement_id=rid, supplier_document_id=document["supplier_document_id"],
                ))
            elif closing and expiry < closing:
                gaps.append(_gap(
                    "evidence_expires_before_closing", BLOCKER,
                    f"'{document.get('title')}' expires {expiry.isoformat()}, before the closing "
                    f"date ({closing.isoformat()}) — it will have lapsed at evaluation.",
                    requirement_id=rid, supplier_document_id=document["supplier_document_id"],
                ))
            elif (expiry - today).days <= _EXPIRY_WARNING_DAYS:
                gaps.append(_gap(
                    "evidence_expiring_soon", WARNING,
                    f"'{document.get('title')}' expires in {(expiry - today).days} day(s).",
                    requirement_id=rid, supplier_document_id=document["supplier_document_id"],
                ))

    if not live:
        gaps.append(_gap("no_requirements", BLOCKER,
                         "No requirements have been extracted, so completeness cannot be assessed."))

    # ---- tasks ----
    overdue = [
        t for t in tasks
        if t.get("status") not in ("done",)
        and (parsed := _parse_date(t.get("due_date"))) is not None and parsed < today
    ]
    for task in overdue:
        gaps.append(_gap("task_overdue", WARNING,
                         f"Task is overdue: \"{task.get('title')}\"", task_id=task.get("task_id")))

    open_tasks = [t for t in tasks if t.get("status") not in ("done",)]
    if open_tasks:
        gaps.append(_gap("open_tasks", INFO,
                         f"{len(open_tasks)} task(s) still open."))

    return gaps


def compute_score(requirements: list[dict], evidence_links: list[dict],
                  vault_documents: list[dict], today: date | None = None) -> dict:
    """Weighted completeness of the requirement set.

    Mandatory requirements weigh triple. The score measures *progress*; it deliberately does
    not encode blockers — those are reported separately, because a single unmet mandatory
    requirement sinks a bid regardless of how good the percentage looks.
    """
    today = today or datetime.now(timezone.utc).date()
    vault = {d["supplier_document_id"]: d for d in vault_documents}

    links_by_requirement: dict[str, list[dict]] = {}
    for link in evidence_links:
        if link.get("human_review_status") != "dismissed":
            links_by_requirement.setdefault(link["requirement_id"], []).append(link)

    live = [r for r in requirements if r.get("human_review_status") != "dismissed"]
    if not live:
        return {"score": 0.0, "satisfied": 0, "total": 0,
                "mandatory_satisfied": 0, "mandatory_total": 0}

    earned = possible = 0
    satisfied_count = mandatory_satisfied = mandatory_total = 0
    for requirement in live:
        mandatory = bool(requirement.get("is_mandatory"))
        weight = _MANDATORY_WEIGHT if mandatory else _OPTIONAL_WEIGHT
        possible += weight
        if mandatory:
            mandatory_total += 1
        if is_satisfied(requirement, links_by_requirement.get(requirement["requirement_id"], []),
                        vault, today):
            earned += weight
            satisfied_count += 1
            if mandatory:
                mandatory_satisfied += 1

    return {
        "score": round(earned / possible, 4) if possible else 0.0,
        "satisfied": satisfied_count,
        "total": len(live),
        "mandatory_satisfied": mandatory_satisfied,
        "mandatory_total": mandatory_total,
    }


def summarise_gaps(gaps: list[dict]) -> dict:
    """Counts by severity, plus the go/no-go verdict."""
    blockers = [g for g in gaps if g["severity"] == BLOCKER]
    return {
        "blockers": len(blockers),
        "warnings": sum(1 for g in gaps if g["severity"] == WARNING),
        "info": sum(1 for g in gaps if g["severity"] == INFO),
        "submission_blocked": bool(blockers),
        "blocking_reasons": [g["message"] for g in blockers[:10]],
    }


def build_report(
    tender: dict,
    requirements: list[dict],
    evidence_links: list[dict],
    documents: list[dict],
    vault_documents: list[dict],
    tasks: list[dict],
    today: date | None = None,
) -> dict:
    """The full readiness read-model. Pure, so the whole report is unit-testable."""
    gaps = compute_gaps(tender, requirements, evidence_links, documents,
                        vault_documents, tasks, today)
    scoring = compute_score(requirements, evidence_links, vault_documents, today)
    severity_rank = {BLOCKER: 0, WARNING: 1, INFO: 2}
    return {
        "tender_id": tender.get("tender_id"),
        **scoring,
        **summarise_gaps(gaps),
        # Blockers first: the list is read top-down under deadline pressure.
        "gaps": sorted(gaps, key=lambda g: severity_rank.get(g["severity"], 3)),
    }


def review(tender_id: str) -> dict:
    """Run the readiness scan and persist the score.

    Writes only `readiness_score` — advisory, never gating. `bid_decision` and submission state
    remain reachable only by human-invoked routes (Rule 3).
    """
    from .. import db

    tender = db.get_tender(tender_id) or {}
    requirements = db.list_requirements(tender_id)
    evidence_links = db.list_evidence_links_for_tender(tender_id)
    documents = db.list_tender_documents(tender_id)
    vault_documents = db.list_supplier_documents(tender.get("org_id"), include_superseded=True) \
        if tender.get("org_id") else []
    tasks = db.list_tasks(tender_id)

    report = build_report(tender, requirements, evidence_links, documents, vault_documents, tasks)

    db.update_tender(tender_id, {
        "readiness_score": report["score"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    db.write_tender_audit(tender_id, "system", "readiness_reviewed", {
        "score": report["score"],
        "blockers": report["blockers"],
        "warnings": report["warnings"],
        "submission_blocked": report["submission_blocked"],
    })
    return report


def narrate(report: dict) -> str:
    """A short prose readiness statement.

    The LLM writes only from the computed report — it cannot introduce a gap, change the score,
    or declare the tender ready. If it is unavailable, the deterministic version stands.
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
    """Readable readiness statement with no LLM involved — the fallback and the quality floor."""
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
