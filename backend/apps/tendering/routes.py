"""Tendering platform routes — workspaces, requirements, bid decisions, document library.

Mounted on the core app in backend/core/main.py. All endpoints are scoped to the
authenticated user's tendering-platform organisation. Endpoints return 404 (not 403) when
the user has no tendering membership so the frontend mock-fallback kicks in gracefully.
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import get_current_user
from backend.core.config import get_settings
from backend.core.db_core import get_user_membership, list_team_member_ids, list_org_members
from backend.core.orgs import check_org_not_suspended
from . import db

router = APIRouter(prefix="/tendering", tags=["tendering"])


def _is_platform_admin(user: dict) -> bool:
    return user.get("email", "").lower() in [
        address.lower() for address in get_settings().platform_admin_emails
    ]


def _get_tendering_org_id(user: dict) -> str:
    """Return the org_id for the authenticated user on the tendering platform."""
    return _get_tendering_membership(user)["org_id"]


def _get_tendering_membership(user: dict) -> dict:
    """Return full membership for the tendering platform.

    Returns 404 (not 403) for missing membership so the frontend mock-fallback catches it.
    """
    if _is_platform_admin(user):
        raise HTTPException(404, "Platform admins don't have a tendering workspace")
    membership = get_user_membership(user["user_id"], platform="tendering")
    if not membership:
        raise HTTPException(404, "No tendering organisation membership")
    check_org_not_suspended(membership)
    return membership


def _can_access_workspace(workspace: dict, user_id: str, role: str, org_id: str) -> bool:
    """Check if a user may read a specific workspace based on their role."""
    if role == "org_admin":
        return True
    if role == "supervisor":
        team_ids = list_team_member_ids(org_id, user_id)
        return workspace.get("created_by") in ([user_id] + team_ids)
    # member: own or assigned
    return (
        workspace.get("created_by") == user_id
        or user_id in (workspace.get("team_members") or [])
    )


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
    storage_path: str = ""  # path within the Supabase Storage bucket


class CreateLibraryDocumentIn(BaseModel):
    title: str
    filename: str = ""
    category: str = "other"
    file_type: str = ""
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    tags: list[str] = []
    url: str = ""


class WorkspaceChatIn(BaseModel):
    message: str
    history: list[dict] = []


# ── Dashboard stats ────────────────────────────────────────────────────────────

@router.get("/my-team")
async def get_my_team(user: dict = Depends(get_current_user)):
    """Return org members the current user may assign to workspaces.

    Supervisors get their invitees; org_admin gets all members; members get empty list.
    """
    membership = await asyncio.to_thread(_get_tendering_membership, user)
    org_id = membership["org_id"]
    role = membership["role"]
    if role == "member":
        return []
    all_members = await asyncio.to_thread(list_org_members, org_id)
    if role == "supervisor":
        user_id = user["user_id"]
        return [
            m for m in all_members
            if m.get("invited_by") == user_id and m["user_id"] != user_id
        ]
    # org_admin sees everyone
    return [m for m in all_members if m["user_id"] != user["user_id"]]


@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    membership = await asyncio.to_thread(_get_tendering_membership, user)
    org_id = membership["org_id"]
    role = membership["role"]
    if role == "org_admin":
        workspaces = await asyncio.to_thread(db.list_tendering_workspaces, org_id)
    elif role == "supervisor":
        workspaces = await asyncio.to_thread(db.list_tendering_workspaces_for_supervisor, org_id, user["user_id"])
    else:
        workspaces = await asyncio.to_thread(db.list_tendering_workspaces_for_member, org_id, user["user_id"])
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
    membership = await asyncio.to_thread(_get_tendering_membership, user)
    org_id = membership["org_id"]
    role = membership["role"]
    if role == "org_admin":
        workspaces = await asyncio.to_thread(db.list_tendering_workspaces, org_id)
    elif role == "supervisor":
        workspaces = await asyncio.to_thread(db.list_tendering_workspaces_for_supervisor, org_id, user["user_id"])
    else:
        workspaces = await asyncio.to_thread(db.list_tendering_workspaces_for_member, org_id, user["user_id"])
    return workspaces


@router.post("/workspaces", status_code=201)
async def create_workspace(body: CreateWorkspaceIn, user: dict = Depends(get_current_user)):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.create_workspace, org_id, body.model_dump(), user["user_id"])
    return workspace


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    membership = await asyncio.to_thread(_get_tendering_membership, user)
    org_id = membership["org_id"]
    role = membership["role"]
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")
    if not _can_access_workspace(workspace, user["user_id"], role, org_id):
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

    workspace_doc = await asyncio.to_thread(
        db.create_workspace_document, workspace_id, body.model_dump()
    )

    # Create a core documents row so the extraction pipeline can find this file.
    if body.storage_path:
        from backend.core import db_core as core_db
        import uuid as _uuid
        from datetime import datetime, timezone
        core_document_id = str(_uuid.uuid4())
        await asyncio.to_thread(core_db.insert_document, {
            "document_id": core_document_id,
            "case_id": None,
            "workspace_id": workspace_id,
            "filename": body.name,
            "file_hash": "",
            "storage_path": body.storage_path,
            "document_type": "unclassified",
            "extraction_status": "uploaded",
            "page_count": 0,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })
        await asyncio.to_thread(
            db.link_core_document_to_workspace_doc, workspace_doc["id"], core_document_id
        )
        workspace_doc["document_id"] = core_document_id

    return workspace_doc


@router.post("/workspaces/{workspace_id}/documents/{doc_id}/extract", status_code=202)
async def extract_workspace_document(
    workspace_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Trigger ADE extraction for a single workspace document.

    Returns 202 immediately; extraction runs in the background.
    Only works if the doc was registered with a storage_path.
    """
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")

    workspace_doc = await asyncio.to_thread(db.get_workspace_document, doc_id)
    if not workspace_doc or workspace_doc["workspace_id"] != workspace_id:
        raise HTTPException(404, "Document not found")

    core_document_id = workspace_doc.get("document_id")
    if not core_document_id:
        raise HTTPException(409, "Document has no storage path — re-upload with storage_path set")

    from backend.core import db_core as core_db
    core_doc = await asyncio.to_thread(core_db.get_document, core_document_id)
    if not core_doc:
        raise HTTPException(404, "Core document record missing")
    if core_doc.get("extraction_status") not in ("uploaded", "failed"):
        raise HTTPException(409, "Extraction already in progress or completed")

    await asyncio.to_thread(core_db.update_document, core_document_id, {"extraction_status": "queued"})

    from .pipeline import process_workspace_document
    background_tasks.add_task(process_workspace_document, doc_id)
    return {"status": "queued", "doc_id": doc_id, "document_id": core_document_id}


@router.delete("/workspaces/{workspace_id}/documents/{doc_id}", status_code=204)
async def delete_workspace_document(
    workspace_id: str,
    doc_id: str,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")

    workspace_doc = await asyncio.to_thread(db.get_workspace_document, doc_id)
    if not workspace_doc or workspace_doc["workspace_id"] != workspace_id:
        raise HTTPException(404, "Document not found")

    await asyncio.to_thread(db.delete_workspace_document, doc_id)


@router.post("/workspaces/{workspace_id}/analyse", status_code=202)
async def analyse_workspace(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Trigger the pipeline: extract requirements → summarise → readiness review.

    Returns immediately (202); the pipeline runs in a background task. The workspace
    stage is set to 'analysing' at once so the UI can show progress.
    """
    membership = await asyncio.to_thread(_get_tendering_membership, user)
    org_id = membership["org_id"]
    role = membership["role"]
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")
    if not _can_access_workspace(workspace, user["user_id"], role, org_id):
        raise HTTPException(404, "Workspace not found")

    await asyncio.to_thread(db.update_workspace, workspace_id, {"stage": "analysing"})

    def _run_pipeline() -> None:
        from .pipeline import run_workspace_analysis
        result = run_workspace_analysis(workspace_id)
        next_stage = "new" if "error" in result else "preparing"
        db.update_workspace(workspace_id, {"stage": next_stage})

    background_tasks.add_task(_run_pipeline)
    return {"status": "analysing", "workspace_id": workspace_id}


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


@router.delete("/library/{doc_id}", status_code=204)
async def delete_library_document(
    doc_id: str,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    docs = await asyncio.to_thread(db.list_library_documents, org_id)
    if not any(d["doc_id"] == doc_id for d in docs):
        raise HTTPException(404, "Document not found")
    await asyncio.to_thread(db.delete_library_document, doc_id)


# ── Workspace AI chat ───────────────────────────────────────────────────────────

@router.post("/workspaces/{workspace_id}/chat")
async def workspace_chat(
    workspace_id: str,
    body: WorkspaceChatIn,
    user: dict = Depends(get_current_user),
):
    from backend.core import llm

    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != org_id:
        raise HTTPException(404, "Workspace not found")

    # Retrieve relevant chunks from extracted documents
    chunks: list[dict] = []
    try:
        embedding = await asyncio.to_thread(lambda: llm.embed([body.message])[0])
        chunks = await asyncio.to_thread(db.match_workspace_chunks, workspace_id, embedding, 8)
    except Exception:
        pass

    if not chunks:
        return {
            "answer": (
                "No extracted document content found yet. "
                "Upload RFP documents, click Extract on each, then ask me anything."
            ),
            "citations": [],
        }

    doc_context = "\n\n".join(f"[{i + 1}] {c.get('text', '')}" for i, c in enumerate(chunks))

    # Include a brief requirements summary so the LLM knows the current state
    requirements = await asyncio.to_thread(db.list_workspace_requirements, workspace_id)
    critical_gaps = [req for req in requirements if req.get("status") == "gap" and req.get("mandatory")]
    gap_lines = "\n".join(f"  - {req.get('description', '')}" for req in critical_gaps[:10])
    gap_section = f"\nCRITICAL MANDATORY GAPS:\n{gap_lines}\n" if gap_lines else ""

    system_prompt = (
        f"You are an AI tender assistant for: {workspace.get('title', '')}.\n"
        f"Buyer: {workspace.get('buyer', '')}. Closing: {workspace.get('closing_date', '')}. "
        f"Readiness: {workspace.get('readiness_score', 0)}%.\n"
        f"{gap_section}"
        "Answer questions about the tender, its requirements, and how to address gaps. "
        "Cite document excerpts inline as [1], [2] etc. "
        "Be concise and practical. If something isn't supported by the excerpts, say so clearly.\n\n"
        f"RELEVANT DOCUMENT EXCERPTS:\n{doc_context}"
    )

    recent_history = [
        {"role": m["role"], "content": str(m.get("content", ""))}
        for m in (body.history or [])[-6:]
        if m.get("role") in ("user", "assistant")
    ]

    try:
        answer = llm.complete(
            tier="reasoning",
            messages=[
                {"role": "system", "content": system_prompt},
                *recent_history,
                {"role": "user", "content": body.message},
            ],
        )
    except Exception:
        answer = "The AI assistant is temporarily unavailable. Check that the LLM provider is configured."

    citations = [
        {
            "document_id": c.get("document_id", ""),
            "page": c.get("page") or 0,
            "quoted_text": (c.get("text") or "")[:200],
            "chunk_id": c.get("chunk_id", ""),
        }
        for c in chunks
    ]
    return {"answer": answer, "citations": citations}
