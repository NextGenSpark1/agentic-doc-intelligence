"""Tendering product routes — tenders, documents, requirements, vault, evidence, tasks.

Mounted on the core app (`backend.core.main`). Tenders are NOT cases: this router owns
`/tenders/*` end to end, including its own document routes (thin mirrors of core's
case-document routes, writing `documents.tender_id` instead of `documents.case_id`). Core
Python is untouched by this product apart from chunk scoping.

Two isolation boundaries, both enforced on every route:
  * `load_tender_or_403` — tender-scoped routes, mirroring core's `load_case_or_403`.
  * `assert_org_access`  — vault routes. The vault is org-level, so it cannot lean on the
    tender guard; without this an id would be enough to read another company's certificates.

**Rule 3 is structural.** Pipeline stages write `human_review_status='pending'` rows and
nothing else. Every transition to confirmed/dismissed, and the bid decision itself, is
reachable only through the human-invoked handlers below.
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import (APIRouter, BackgroundTasks, Depends, File, HTTPException, Query,
                     UploadFile)
from pydantic import BaseModel, Field

from backend.core.auth import get_current_user
from . import db, pipeline
from .access import assert_org_access, load_tender_or_403
from .pipeline import vault as vault_pipeline
from .schemas import REQUIREMENT_CATEGORIES

router = APIRouter()

_TENDER_STAGES = ("identified", "assessing", "bidding", "submitted", "awarded", "lost", "withdrawn")
_BID_DECISIONS = ("bid", "no_bid")
_REVIEW_STATUSES = ("pending", "confirmed", "dismissed")
_COMPLETION_STATUSES = ("not_started", "in_progress", "complete")
_TASK_STATUSES = ("open", "in_progress", "done", "blocked")
_VAULT_DOC_TYPES = ("certificate", "licence", "financial", "policy", "cv", "reference", "other")


# ------------------------- request models -------------------------
class TenderCreate(BaseModel):
    title: str
    buyer: str | None = None
    reference_no: str | None = None
    closing_date: str | None = None
    contract_value: float | None = None
    currency: str | None = None
    submission_method: str | None = None


class TenderPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    buyer: str | None = None
    reference_no: str | None = None
    closing_date: str | None = None
    contract_value: float | None = None
    currency: str | None = None
    submission_method: str | None = None
    tender_stage: str | None = None


class BidDecision(BaseModel):
    """Human-only. No pipeline stage may reach this endpoint (Rule 3)."""

    decision: str = Field(..., description="'bid' or 'no_bid'")
    decided_by: str


class RequirementCreate(BaseModel):
    description: str
    category: str = "other"
    is_mandatory: bool = False
    required_evidence: str | None = None
    source_document_id: str | None = None
    source_page: int | None = None
    source_clause: str | None = None


class RequirementReview(BaseModel):
    status: str  # "confirmed" | "dismissed"
    reviewed_by: str
    dismissal_reason: str | None = None


class RequirementPatch(BaseModel):
    owner_id: str | None = None
    completion_status: str | None = None
    required_evidence: str | None = None
    category: str | None = None
    is_mandatory: bool | None = None


class VaultDocumentPatch(BaseModel):
    title: str | None = None
    doc_type: str | None = None
    issued_date: str | None = None
    expiry_date: str | None = None


class EvidenceLinkCreate(BaseModel):
    """Manually attach a vault document to a requirement."""

    supplier_document_id: str
    rationale: str | None = None


class EvidenceReview(BaseModel):
    status: str  # "confirmed" | "dismissed"
    reviewed_by: str
    dismissal_reason: str | None = None


class TaskCreate(BaseModel):
    title: str
    requirement_id: str | None = None
    assignee_id: str | None = None
    due_date: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    assignee_id: str | None = None
    due_date: str | None = None
    status: str | None = None


# ------------------------------ helpers ---------------------------
def _reject_unknown(value: str | None, allowed: tuple[str, ...], field: str) -> None:
    if value is not None and value not in allowed:
        raise HTTPException(422, f"{field} must be one of {list(allowed)}")


async def _load_requirement_or_404(requirement_id: str, user: dict) -> tuple[dict, dict]:
    """Fetch a requirement and access-check the tender that owns it.

    Requirement routes are not tender-scoped in their path, so without this any authenticated
    user could read or review another org's requirements by id.
    """
    requirement = await asyncio.to_thread(db.get_requirement, requirement_id)
    if not requirement:
        raise HTTPException(404, "requirement not found")
    tender = await load_tender_or_403(requirement["tender_id"], user)
    return requirement, tender


# ------------------------------ tenders ---------------------------
@router.post("/tenders", status_code=201)
async def create_tender(body: TenderCreate, user: dict = Depends(get_current_user)):
    tender_id = f"TEN-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    org_id = membership["org_id"] if membership else None

    record = {
        "tender_id": tender_id,
        "org_id": org_id,
        "title": body.title,
        "buyer": body.buyer,
        "reference_no": body.reference_no,
        "closing_date": body.closing_date,
        "contract_value": body.contract_value,
        "currency": body.currency,
        "submission_method": body.submission_method,
        "tender_stage": "identified",
        "status": "Intake",
        "owner_id": user["user_id"],
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    created = await asyncio.to_thread(db.insert_tender, record)
    await asyncio.to_thread(db.write_tender_audit, tender_id, user["user_id"], "tender_created",
                            {"title": body.title, "buyer": body.buyer})
    return created


@router.get("/tenders")
async def list_tenders(user: dict = Depends(get_current_user)):
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    if not membership:
        tenders = await asyncio.to_thread(db.list_tenders, owner_id=user["user_id"])
    else:
        # Same team-scoping rules as core's GET /cases — admin sees the org, supervisor sees
        # what they created, member sees their supervisor's. Diverging here would give tenders
        # a different visibility model from cases.
        role, org_id = membership["role"], membership["org_id"]
        if role == "org_admin":
            created_by = None
        elif role == "supervisor":
            created_by = user["user_id"]
        else:
            created_by = membership.get("invited_by")
        tenders = await asyncio.to_thread(db.list_tenders, org_id=org_id, created_by=created_by)

    async def enrich(t: dict) -> dict:
        docs, reqs = await asyncio.gather(
            asyncio.to_thread(db.count_tender_documents, t["tender_id"]),
            asyncio.to_thread(db.list_requirements, t["tender_id"]),
        )
        live = [r for r in reqs if r.get("human_review_status") != "dismissed"]
        return {
            **t,
            "doc_count": docs,
            "requirement_count": len(live),
            "requirements_pending_review": sum(
                1 for r in live if r.get("human_review_status") == "pending"),
        }

    enriched = list(await asyncio.gather(*(enrich(t) for t in tenders)))
    return {
        "tenders": enriched,
        "stats": {
            "open_tenders": sum(1 for t in enriched
                                if (t.get("tender_stage") or "") in ("identified", "assessing", "bidding")),
            "requirements_pending_review": sum(t["requirements_pending_review"] for t in enriched),
        },
    }


@router.get("/tenders/{tender_id}")
async def get_tender(tender_id: str, user: dict = Depends(get_current_user)):
    return await load_tender_or_403(tender_id, user)


@router.patch("/tenders/{tender_id}")
async def patch_tender(tender_id: str, body: TenderPatch, user: dict = Depends(get_current_user)):
    await load_tender_or_403(tender_id, user)
    _reject_unknown(body.tender_stage, _TENDER_STAGES, "tender_stage")

    patch = body.model_dump(exclude_none=True)
    if not patch:
        return await asyncio.to_thread(db.get_tender, tender_id)
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    return await asyncio.to_thread(db.update_tender, tender_id, patch)


@router.delete("/tenders/{tender_id}", status_code=204)
async def delete_tender(tender_id: str, user: dict = Depends(get_current_user)):
    await load_tender_or_403(tender_id, user)
    await asyncio.to_thread(db.delete_tender, tender_id)


@router.post("/tenders/{tender_id}/bid-decision")
async def set_bid_decision(tender_id: str, body: BidDecision,
                           user: dict = Depends(get_current_user)):
    """Record the human bid/no-bid decision.

    Rule 3: the only write path to `bid_decision`. Analysis may produce a recommendation; it
    can never set this field.
    """
    await load_tender_or_403(tender_id, user)
    if body.decision not in _BID_DECISIONS:
        raise HTTPException(422, f"decision must be one of {list(_BID_DECISIONS)}")

    now = datetime.now(timezone.utc).isoformat()
    updated = await asyncio.to_thread(db.update_tender, tender_id, {
        "bid_decision": body.decision,
        "bid_decision_by": body.decided_by,
        "bid_decision_at": now,
        "updated_at": now,
    })
    await asyncio.to_thread(db.write_tender_audit, tender_id, body.decided_by,
                            "bid_decision_recorded", {"decision": body.decision})
    return updated or {}


@router.post("/tenders/{tender_id}/analysis", status_code=202)
async def run_analysis(tender_id: str, background: BackgroundTasks,
                       user: dict = Depends(get_current_user)):
    await load_tender_or_403(tender_id, user)
    background.add_task(pipeline.run_tender_analysis, tender_id)
    return {"status": "queued", "tender_id": tender_id}


# ------------------------- tender documents -----------------------
@router.get("/tenders/{tender_id}/documents")
async def list_tender_documents(tender_id: str, user: dict = Depends(get_current_user)):
    await load_tender_or_403(tender_id, user)
    return {"documents": await asyncio.to_thread(db.list_tender_documents, tender_id)}


@router.post("/tenders/{tender_id}/documents", status_code=201)
async def upload_tender_document(tender_id: str, file: UploadFile = File(...),
                                 user: dict = Depends(get_current_user)):
    """Upload a tender document. Mirrors core's case-document upload, keyed on tender_id."""
    tender = await load_tender_or_403(tender_id, user)
    content = await file.read()
    if not content:
        raise HTTPException(422, "uploaded file is empty")

    document_id = f"TDOC-{uuid.uuid4().hex[:8].upper()}"
    storage_path = f"{tender_id}/{document_id}/{file.filename}"
    await asyncio.to_thread(db.upload_evidence, storage_path, content,
                            file.content_type or "application/octet-stream")

    record = {
        "document_id": document_id,
        "case_id": None,
        "tender_id": tender_id,
        "filename": file.filename,
        "file_hash": hashlib.sha256(content).hexdigest(),
        "storage_path": storage_path,
        "extraction_status": "uploaded",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    created = await asyncio.to_thread(db.insert_document, record)

    if (tender.get("status") or "").lower() == "intake":
        await asyncio.to_thread(db.update_tender, tender_id, {"status": "active"})
    return created


@router.post("/tenders/{tender_id}/documents/{document_id}/extract", status_code=202)
async def extract_tender_document(tender_id: str, document_id: str, background: BackgroundTasks,
                                  user: dict = Depends(get_current_user)):
    await load_tender_or_403(tender_id, user)
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("tender_id") != tender_id:
        raise HTTPException(404, "document not found")
    if doc.get("extraction_status") not in ("uploaded", "failed"):
        raise HTTPException(409, "extraction already in progress or completed")
    await asyncio.to_thread(db.update_document, document_id, {"extraction_status": "queued"})
    background.add_task(pipeline.process_document, document_id)
    return {"status": "queued", "document_id": document_id}


# --------------------------- requirements -------------------------
@router.get("/tenders/{tender_id}/requirements")
async def list_requirements(
    tender_id: str,
    category: str | None = Query(None),
    review_status: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    await load_tender_or_403(tender_id, user)
    _reject_unknown(category, REQUIREMENT_CATEGORIES, "category")
    _reject_unknown(review_status, _REVIEW_STATUSES, "review_status")
    return {"requirements": await asyncio.to_thread(
        db.list_requirements, tender_id, category, review_status)}


@router.get("/tenders/{tender_id}/compliance-matrix")
async def compliance_matrix(tender_id: str, user: dict = Depends(get_current_user)):
    """The compliance matrix is a read-model over requirements, not a separate record type.

    Grouped by category with per-group counts and each requirement's approved evidence, so the
    UI renders a table without doing the aggregation itself. Dismissed requirements are
    excluded — they are explicitly ruled out.
    """
    await load_tender_or_403(tender_id, user)
    requirements, links = await asyncio.gather(
        asyncio.to_thread(db.list_requirements, tender_id),
        asyncio.to_thread(db.list_evidence_links_for_tender, tender_id),
    )
    live = [r for r in requirements if r.get("human_review_status") != "dismissed"]

    links_by_requirement: dict[str, list[dict]] = {}
    for link in links:
        if link.get("human_review_status") != "dismissed":
            links_by_requirement.setdefault(link["requirement_id"], []).append(link)

    enriched = [
        {**r, "evidence": links_by_requirement.get(r["requirement_id"], [])}
        for r in live
    ]

    groups: dict[str, list[dict]] = {}
    for r in enriched:
        groups.setdefault(r.get("category") or "other", []).append(r)

    def _summarise(items: list[dict]) -> dict:
        return {
            "total": len(items),
            "mandatory": sum(1 for i in items if i.get("is_mandatory")),
            "confirmed": sum(1 for i in items if i.get("human_review_status") == "confirmed"),
            "pending_review": sum(1 for i in items if i.get("human_review_status") == "pending"),
            "complete": sum(1 for i in items if i.get("completion_status") == "complete"),
            "unassigned": sum(1 for i in items if not i.get("owner_id")),
            "with_approved_evidence": sum(
                1 for i in items
                if any(e.get("human_review_status") == "confirmed" for e in i["evidence"])),
            "without_any_evidence": sum(1 for i in items if not i["evidence"]),
        }

    ordered = [c for c in REQUIREMENT_CATEGORIES if c in groups]
    return {
        "tender_id": tender_id,
        "totals": _summarise(enriched),
        "categories": [
            {"category": cat, **_summarise(groups[cat]), "requirements": groups[cat]}
            for cat in ordered
        ],
    }


@router.post("/tenders/{tender_id}/requirements", status_code=201)
async def create_requirement(tender_id: str, body: RequirementCreate,
                             user: dict = Depends(get_current_user)):
    """Add a requirement by hand.

    Born `confirmed`, not `pending` — a human typed it, so there is nothing to review. The
    mirror image of Rule 3: AI output starts pending, human input starts confirmed.
    """
    tender = await load_tender_or_403(tender_id, user)
    _reject_unknown(body.category, REQUIREMENT_CATEGORIES, "category")

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "requirement_id": f"REQ-{uuid.uuid4().hex[:8].upper()}",
        "tender_id": tender_id,
        "org_id": tender.get("org_id"),
        "description": body.description,
        "category": body.category,
        "is_mandatory": body.is_mandatory,
        "required_evidence": body.required_evidence,
        "source_document_id": body.source_document_id,
        "source_page": body.source_page,
        "source_clause": body.source_clause,
        "source": "manual",
        "human_review_status": "confirmed",
        "reviewed_by": user["user_id"],
        "reviewed_at": now,
        "created_at": now,
    }
    created = await asyncio.to_thread(db.insert_requirement, row)
    if created is None:
        raise HTTPException(409, "an identical requirement already exists on this tender")
    await asyncio.to_thread(db.write_tender_audit, tender_id, user["user_id"],
                            "requirement_created",
                            {"requirement_id": row["requirement_id"], "source": "manual"})
    return created


@router.patch("/requirements/{requirement_id}/review")
async def review_requirement(requirement_id: str, body: RequirementReview,
                             user: dict = Depends(get_current_user)):
    """Confirm or dismiss an AI-extracted requirement. Rule 3's state transition."""
    if body.status not in _REVIEW_STATUSES:
        raise HTTPException(422, f"status must be one of {list(_REVIEW_STATUSES)}")
    requirement, _ = await _load_requirement_or_404(requirement_id, user)

    updated = await asyncio.to_thread(db.update_requirement, requirement_id, {
        "human_review_status": body.status,
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "dismissal_reason": body.dismissal_reason,
    })
    if not updated:
        raise HTTPException(404, "requirement not found")
    if body.status != "pending":
        await asyncio.to_thread(db.write_tender_audit, requirement["tender_id"], body.reviewed_by,
                                f"requirement_{body.status}",
                                {"requirement_id": requirement_id,
                                 "dismissal_reason": body.dismissal_reason})
    return updated


@router.patch("/requirements/{requirement_id}")
async def patch_requirement(requirement_id: str, body: RequirementPatch,
                            user: dict = Depends(get_current_user)):
    """Assign an owner or move completion status. Workflow only — never review state."""
    _reject_unknown(body.completion_status, _COMPLETION_STATUSES, "completion_status")
    _reject_unknown(body.category, REQUIREMENT_CATEGORIES, "category")
    requirement, _ = await _load_requirement_or_404(requirement_id, user)

    patch = body.model_dump(exclude_none=True)
    if not patch:
        return requirement
    return await asyncio.to_thread(db.update_requirement, requirement_id, patch) or requirement


# ------------------------- supplier vault (org) -------------------------
@router.get("/vault/documents")
async def list_vault_documents(include_superseded: bool = Query(False),
                               user: dict = Depends(get_current_user)):
    org_id = await assert_org_access(None, user)
    return {"documents": await asyncio.to_thread(
        db.list_supplier_documents, org_id, include_superseded)}


@router.post("/vault/documents", status_code=201)
async def upload_vault_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Query(...),
    doc_type: str = Query("other"),
    issued_date: str | None = Query(None),
    expiry_date: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    """Upload a company document to the org's vault.

    Org-scoped, not tender-scoped: uploaded once, citable by every tender the org bids on.
    """
    org_id = await assert_org_access(None, user)
    _reject_unknown(doc_type, _VAULT_DOC_TYPES, "doc_type")

    content = await file.read()
    if not content:
        raise HTTPException(422, "uploaded file is empty")

    supplier_document_id = f"SUP-{uuid.uuid4().hex[:8].upper()}"
    # Storage prefix is the ORG, not a tender — the vault's isolation boundary in storage.
    storage_path = f"{org_id}/vault/{supplier_document_id}/{file.filename}"
    await asyncio.to_thread(db.upload_evidence, storage_path, content,
                            file.content_type or "application/octet-stream")

    record = {
        "supplier_document_id": supplier_document_id,
        "org_id": org_id,
        "title": title,
        "doc_type": doc_type,
        "storage_path": storage_path,
        "filename": file.filename,
        "issued_date": issued_date,
        "expiry_date": expiry_date,
        "extraction_status": "uploaded",
        "uploaded_by": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    created = await asyncio.to_thread(db.insert_supplier_document, record)
    background.add_task(vault_pipeline.process_supplier_document, supplier_document_id)
    return created


@router.patch("/vault/documents/{supplier_document_id}")
async def patch_vault_document(supplier_document_id: str, body: VaultDocumentPatch,
                               user: dict = Depends(get_current_user)):
    org_id = await assert_org_access(None, user)
    existing = await asyncio.to_thread(db.get_supplier_document, supplier_document_id)
    if not existing or existing.get("org_id") != org_id:
        raise HTTPException(404, "vault document not found")
    _reject_unknown(body.doc_type, _VAULT_DOC_TYPES, "doc_type")

    patch = body.model_dump(exclude_none=True)
    if not patch:
        return existing
    return await asyncio.to_thread(db.update_supplier_document, supplier_document_id, patch)


@router.post("/vault/documents/{supplier_document_id}/supersede/{new_document_id}")
async def supersede_vault_document(supplier_document_id: str, new_document_id: str,
                                   user: dict = Depends(get_current_user)):
    """Mark a vault document as replaced by a newer version.

    The old row is kept, not deleted — an expired certificate is still a record of what was
    valid at submission time — but it stops being proposed as evidence.
    """
    org_id = await assert_org_access(None, user)
    for doc_id in (supplier_document_id, new_document_id):
        doc = await asyncio.to_thread(db.get_supplier_document, doc_id)
        if not doc or doc.get("org_id") != org_id:
            raise HTTPException(404, "vault document not found")
    return await asyncio.to_thread(vault_pipeline.supersede, supplier_document_id, new_document_id)


# --------------------------- evidence links ---------------------------
@router.post("/tenders/{tender_id}/evidence-matching", status_code=202)
async def run_evidence_matching(tender_id: str, background: BackgroundTasks,
                                user: dict = Depends(get_current_user)):
    """Re-run vault matching for this tender — e.g. after uploading new vault documents."""
    await load_tender_or_403(tender_id, user)
    from .pipeline import evidence_matching

    background.add_task(evidence_matching.match, tender_id)
    return {"status": "queued", "tender_id": tender_id}


@router.get("/requirements/{requirement_id}/evidence")
async def list_evidence(requirement_id: str, user: dict = Depends(get_current_user)):
    await _load_requirement_or_404(requirement_id, user)
    return {"evidence": await asyncio.to_thread(db.list_evidence_links, requirement_id)}


@router.post("/requirements/{requirement_id}/evidence", status_code=201)
async def attach_evidence(requirement_id: str, body: EvidenceLinkCreate,
                          user: dict = Depends(get_current_user)):
    """Attach a vault document by hand. Born confirmed — a human chose it."""
    requirement, tender = await _load_requirement_or_404(requirement_id, user)
    org_id = tender.get("org_id")

    supplier_doc = await asyncio.to_thread(db.get_supplier_document, body.supplier_document_id)
    if not supplier_doc or supplier_doc.get("org_id") != org_id:
        raise HTTPException(404, "vault document not found")

    now = datetime.now(timezone.utc).isoformat()
    created = await asyncio.to_thread(db.upsert_evidence_link, {
        "evidence_link_id": f"EVL-{uuid.uuid4().hex[:8].upper()}",
        "requirement_id": requirement_id,
        "supplier_document_id": body.supplier_document_id,
        "org_id": org_id,
        "rationale": body.rationale,
        "source": "manual",
        "human_review_status": "confirmed",
        "reviewed_by": user["user_id"],
        "reviewed_at": now,
        "created_at": now,
    })
    if created is None:
        raise HTTPException(409, "this document is already linked to the requirement")
    await asyncio.to_thread(db.write_tender_audit, requirement["tender_id"], user["user_id"],
                            "evidence_attached",
                            {"requirement_id": requirement_id,
                             "supplier_document_id": body.supplier_document_id})
    return created


@router.patch("/evidence/{evidence_link_id}/review")
async def review_evidence(evidence_link_id: str, body: EvidenceReview,
                          user: dict = Depends(get_current_user)):
    """Approve or reject a proposed evidence match. Rule 3 for matching.

    An AI-proposed link does not count toward a submission until a human confirms it.
    """
    if body.status not in _REVIEW_STATUSES:
        raise HTTPException(422, f"status must be one of {list(_REVIEW_STATUSES)}")

    link = await asyncio.to_thread(db.get_evidence_link, evidence_link_id)
    if not link:
        raise HTTPException(404, "evidence link not found")
    requirement, _ = await _load_requirement_or_404(link["requirement_id"], user)

    updated = await asyncio.to_thread(db.update_evidence_link, evidence_link_id, {
        "human_review_status": body.status,
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "dismissal_reason": body.dismissal_reason,
    })
    if not updated:
        raise HTTPException(404, "evidence link not found")
    if body.status != "pending":
        await asyncio.to_thread(db.write_tender_audit, requirement["tender_id"], body.reviewed_by,
                                f"evidence_{body.status}",
                                {"evidence_link_id": evidence_link_id,
                                 "requirement_id": link["requirement_id"]})
    return updated


# ---------------------------- readiness ---------------------------
@router.get("/tenders/{tender_id}/readiness")
async def get_readiness(tender_id: str, narrative: bool = Query(False),
                        user: dict = Depends(get_current_user)):
    """Submission-readiness scan: score, blockers, and the full gap checklist.

    Computed fresh on every call rather than stored — gaps are derived entirely from current
    state, so a cached copy would be stale the moment anyone approves a document. Only the
    score is persisted, on `tenders.readiness_score`.

    Pass `narrative=true` for a prose statement as well; it costs an LLM call and adds nothing
    the structured report does not already contain.
    """
    tender = await load_tender_or_403(tender_id, user)
    from .pipeline import readiness_review

    org_id = tender.get("org_id")
    requirements, links, documents, tasks = await asyncio.gather(
        asyncio.to_thread(db.list_requirements, tender_id),
        asyncio.to_thread(db.list_evidence_links_for_tender, tender_id),
        asyncio.to_thread(db.list_tender_documents, tender_id),
        asyncio.to_thread(db.list_tasks, tender_id),
    )
    vault = await asyncio.to_thread(db.list_supplier_documents, org_id, True) if org_id else []

    report = readiness_review.build_report(tender, requirements, links, documents, vault, tasks)
    if narrative:
        report["narrative"] = await asyncio.to_thread(readiness_review.narrate, report)
    return report


@router.post("/tenders/{tender_id}/readiness", status_code=202)
async def run_readiness_review(tender_id: str, background: BackgroundTasks,
                               user: dict = Depends(get_current_user)):
    """Re-run the readiness scan and persist the score."""
    await load_tender_or_403(tender_id, user)
    from .pipeline import readiness_review

    background.add_task(readiness_review.review, tender_id)
    return {"status": "queued", "tender_id": tender_id}


# ------------------------------- tasks ----------------------------
@router.get("/tenders/{tender_id}/tasks")
async def list_tasks(tender_id: str, user: dict = Depends(get_current_user)):
    await load_tender_or_403(tender_id, user)
    return {"tasks": await asyncio.to_thread(db.list_tasks, tender_id)}


@router.post("/tenders/{tender_id}/tasks", status_code=201)
async def create_task(tender_id: str, body: TaskCreate, user: dict = Depends(get_current_user)):
    tender = await load_tender_or_403(tender_id, user)
    row = {
        "task_id": f"TSK-{uuid.uuid4().hex[:8].upper()}",
        "tender_id": tender_id,
        "org_id": tender.get("org_id"),
        "requirement_id": body.requirement_id,
        "title": body.title,
        "assignee_id": body.assignee_id,
        "due_date": body.due_date,
        "status": "open",
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return await asyncio.to_thread(db.insert_task, row)


@router.patch("/tasks/{task_id}")
async def patch_task(task_id: str, body: TaskPatch, user: dict = Depends(get_current_user)):
    _reject_unknown(body.status, _TASK_STATUSES, "status")
    existing = await asyncio.to_thread(db.get_task, task_id)
    if not existing:
        raise HTTPException(404, "task not found")
    await load_tender_or_403(existing["tender_id"], user)

    patch = body.model_dump(exclude_none=True)
    if not patch:
        return existing
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    return await asyncio.to_thread(db.update_task, task_id, patch) or existing


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    existing = await asyncio.to_thread(db.get_task, task_id)
    if not existing:
        raise HTTPException(404, "task not found")
    await load_tender_or_403(existing["tender_id"], user)
    await asyncio.to_thread(db.delete_task, task_id)
