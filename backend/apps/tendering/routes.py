"""Tendering platform routes — workspaces, requirements, bid decisions, document library.

Mounted on the core app in backend/core/main.py. All endpoints are scoped to the
authenticated user's tendering-platform organisation. Endpoints return 404 (not 403) when
the user has no tendering membership so the frontend mock-fallback kicks in gracefully.
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import get_current_user
from backend.core.config import get_settings
from backend.core.db_core import get_user_membership
from backend.core.orgs import check_org_not_suspended
from . import db

router = APIRouter(prefix="/tendering", tags=["tendering"])


def _is_platform_admin(user: dict) -> bool:
    return user.get("email", "").lower() in [
        address.lower() for address in get_settings().platform_admin_emails
    ]


def _get_tendering_org_id(user: dict) -> str:
    """Return the org_id for the authenticated user on the tendering platform.

    Returns 404 (not 403) for missing membership so the frontend mock-fallback catches it.
    """
    if _is_platform_admin(user):
        raise HTTPException(404, "Platform admins don't have a tendering workspace")
    membership = get_user_membership(user["user_id"], platform="tendering")
    if not membership:
        raise HTTPException(404, "No tendering organisation membership")
    check_org_not_suspended(membership)
    return membership["org_id"]


# ── Request models ─────────────────────────────────────────────────────────────

class CreateWorkspaceIn(BaseModel):
    title: str
    reference: str = ""
    buyer: str = ""
    category: str = ""
    closing_date: Optional[date] = None
    contract_value: float = 0
    currency: str = "USD"


class UpdateWorkspaceIn(BaseModel):
    title: Optional[str] = None
    reference: Optional[str] = None
    buyer: Optional[str] = None
    category: Optional[str] = None
    closing_date: Optional[date] = None
    contract_value: Optional[float] = None
    currency: Optional[str] = None
    stage: Optional[str] = None
    bid_decision: Optional[str] = None
    readiness_score: Optional[int] = None
    description: Optional[str] = None
    team_members: Optional[list[str]] = None


class UpdateLibraryDocumentIn(BaseModel):
    title: Optional[str] = None
    filename: Optional[str] = None
    category: Optional[str] = None
    file_type: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    tags: Optional[list[str]] = None
    url: Optional[str] = None
    verification_status: Optional[str] = None


class UpdateRequirementIn(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None


class CreateWorkspaceDocumentIn(BaseModel):
    name: str
    category: str = "supporting"
    file_type: str = ""
    size_bytes: int = 0
    url: str = ""


class CreateLibraryDocumentIn(BaseModel):
    title: str
    filename: str = ""
    category: str = "other"
    file_type: str = ""
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    tags: list[str] = []
    url: str = ""


# ── Dashboard stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspaces = await asyncio.to_thread(db.list_tendering_workspaces, org_id)
    active_stages = {"new", "analysing", "preparing", "submitted"}
    active = [workspace for workspace in workspaces if workspace["stage"] in active_stages]
    today = date.today()
    closing_soon = sum(
        1 for workspace in active
        if workspace.get("closing_date")
        and 0 <= (date.fromisoformat(str(workspace["closing_date"])[:10]) - today).days <= 14
    )
    pending_decisions = sum(1 for workspace in active if workspace.get("bid_decision") == "pending")
    avg_readiness = (
        round(sum(workspace.get("readiness_score", 0) for workspace in active) / len(active))
        if active else 0
    )
    return {
        "active_workspaces": len(active),
        "closing_soon": closing_soon,
        "avg_readiness": avg_readiness,
        "pending_decisions": pending_decisions,
    }


# ── Workspaces ─────────────────────────────────────────────────────────────────

@router.get("/workspaces")
async def list_workspaces(user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspaces = await asyncio.to_thread(db.list_tendering_workspaces, org_id)
    return workspaces


@router.post("/workspaces", status_code=201)
async def create_workspace(body: CreateWorkspaceIn, user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.create_workspace, org_id, body.model_dump())
    return workspace


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")
    workspace["documents"] = await asyncio.to_thread(db.list_workspace_documents, workspace_id)
    return workspace


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: UpdateWorkspaceIn,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")
    updated = await asyncio.to_thread(
        db.update_workspace, workspace_id, body.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(500, "Update failed")
    return updated


@router.post("/workspaces/{workspace_id}/documents", status_code=201)
async def add_workspace_document(
    workspace_id: str,
    body: CreateWorkspaceDocumentIn,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")
    return await asyncio.to_thread(db.create_workspace_document, workspace_id, body.model_dump())


@router.get("/workspaces/{workspace_id}/requirements")
async def list_requirements(workspace_id: str, user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")
    return await asyncio.to_thread(db.list_workspace_requirements, workspace_id)


@router.get("/workspaces/{workspace_id}/bid-decision")
async def get_bid_decision(workspace_id: str, user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")
    decision = await asyncio.to_thread(db.get_workspace_bid_decision, workspace_id)
    if not decision:
        raise HTTPException(404, "No bid decision for this workspace")
    return decision


# ── Requirements ───────────────────────────────────────────────────────────────

@router.patch("/requirements/{req_id}")
async def update_requirement(
    req_id: str,
    body: UpdateRequirementIn,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    requirement = await asyncio.to_thread(db.get_requirement, req_id)
    if not requirement:
        raise HTTPException(404, "Requirement not found")
    workspace = await asyncio.to_thread(db.get_tendering_workspace, requirement["workspace_id"])
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Requirement not found")
    updated = await asyncio.to_thread(
        db.update_requirement, req_id, body.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(500, "Update failed")
    if body.status is not None:
        await asyncio.to_thread(db.recalculate_workspace_readiness, workspace["id"])
    return updated


# ── Document library ───────────────────────────────────────────────────────────

@router.get("/library")
async def list_library(user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    return await asyncio.to_thread(db.list_library_documents, org_id)


@router.patch("/library/{doc_id}")
async def update_library_document(
    doc_id: str,
    body: UpdateLibraryDocumentIn,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    docs = await asyncio.to_thread(db.list_library_documents, org_id)
    if not any(d["doc_id"] == doc_id for d in docs):
        raise HTTPException(404, "Document not found")
    updated = await asyncio.to_thread(db.update_library_document, doc_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(500, "Update failed")
    return updated


@router.post("/library", status_code=201)
async def add_library_document(
    body: CreateLibraryDocumentIn,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    return await asyncio.to_thread(db.create_library_document, org_id, body.model_dump())
