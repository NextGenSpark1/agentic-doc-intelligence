"""Tendering platform routes — workspaces, requirements, bid decisions, document library.

Mounted on the core app in backend/core/main.py. All endpoints are scoped to the
authenticated user's tendering-platform organisation. Endpoints return 404 (not 403) when
the user has no tendering membership so the frontend mock-fallback kicks in gracefully.
"""
from __future__ import annotations

import asyncio
import traceback
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import get_current_user
from backend.core.config import get_settings
from backend.core.db_core import get_user_membership, list_team_member_ids, list_org_members
from backend.core.orgs import check_org_not_suspended
from backend.core.ratelimit import rate_limit
from backend.core.text_utils import strip_html as _strip_html
from . import db

router = APIRouter(prefix="/tendering", tags=["tendering"])


import re as _re

def _clean_chunk_text(text: str) -> str:
    """Strip HTML and markdown artifacts from a chunk before showing it as a citation excerpt."""
    cleaned = _strip_html(text)
    cleaned = _re.sub(r'^#{1,6}\s+', '', cleaned, flags=_re.MULTILINE)
    cleaned = _re.sub(r'\{#[^}]+\}', '', cleaned)
    cleaned = _re.sub(r'\n{2,}', ' ', cleaned).strip()
    return cleaned


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


async def _load_workspace_or_404(
    workspace_id: str, user: dict, detail: str = "Workspace not found"
) -> dict:
    """Load a workspace and enforce BOTH org and role scope.

    EVERY workspace-scoped route must go through this. Most routes used to check only that the
    workspace belonged to the caller's org, so the role rule applied to the tender list and the
    tender page but to nothing else: a member who was never assigned — or who was removed from
    the team — could still delete the workspace, edit it, or read its requirements, evidence and
    documents straight from the API, because the workspace id in the URL was all it took.

    404 rather than 403 throughout: a caller who may not reach a workspace does not get to learn
    that it exists.
    """
    membership = await asyncio.to_thread(_get_tendering_membership, user)
    workspace = await asyncio.to_thread(db.get_tendering_workspace, workspace_id)
    if not workspace or workspace["org_id"] != membership["org_id"]:
        raise HTTPException(404, detail)
    # _can_access_workspace hits the DB for supervisors (list_team_member_ids) — keep it off the
    # event loop like every other DB call in this module.
    allowed = await asyncio.to_thread(
        _can_access_workspace, workspace, user["user_id"], membership["role"], membership["org_id"]
    )
    if not allowed:
        raise HTTPException(404, detail)
    return workspace


# ── Storage paths ──────────────────────────────────────────────────────────────
# Uploads go straight from the browser to Supabase Storage, so the client is what tells us
# where the file landed. The backend then downloads that path with the service key, which
# bypasses every storage policy — so an unchecked path is an instruction to fetch any file in
# the bucket on the caller's behalf. These two functions are the check.

_MAX_STORAGE_PATH_CHARS = 512


def is_safe_storage_path(storage_path: str) -> bool:
    """True if `storage_path` looks like a plain key inside the bucket.

    Rejects traversal (`..`), absolute paths and URLs, backslashes, empty segments and
    control characters — anything that could resolve somewhere other than where it reads.
    """
    path = storage_path or ""
    if not path or path != path.strip() or len(path) > _MAX_STORAGE_PATH_CHARS:
        return False
    if path.startswith("/") or "\\" in path or "//" in path or "://" in path:
        return False
    segments = path.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return False
    return all(character.isprintable() for character in path)


def is_storage_path_within(storage_path: str, folder: str) -> bool:
    """True if `storage_path` is a file inside `folder`'s own directory in the bucket."""
    if not folder or not is_safe_storage_path(storage_path):
        return False
    return storage_path.startswith(f"{folder}/")


def is_http_url(url: str) -> bool:
    """True for an ordinary http(s) link, which is all a document `url` is ever meant to be.

    The client sends this alongside the upload and the UI puts it straight into `<iframe src>`
    and `<a href>`. A `javascript:` or `data:` value there runs as script for the next colleague
    who opens the document, so anything that is not plain http(s) is refused on the way in.
    """
    candidate = (url or "").strip().lower()
    return candidate.startswith("https://") or candidate.startswith("http://")


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
    # bid_decision stays client-settable: it is a human's call, which is the whole point of
    # Rule 3. readiness_score does not — it is computed by the readiness review from the
    # requirements and evidence, and a client that could write it could show a green 100%
    # over a workspace with unmet mandatory requirements. The pipeline still writes it through
    # db.update_workspace, which is not reachable from this request body.
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
    # Sent when the file itself is replaced. It belongs to the vault row rather than the library
    # row, so the route applies it separately — library_documents has no storage_path column.
    storage_path: Optional[str] = None


_VALID_REQUIREMENT_STATUSES = {"met", "partial", "gap", "unchecked", "rejected"}


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
    storage_path: str = ""  # path within library-documents Supabase Storage bucket


class WorkspaceChatIn(BaseModel):
    message: str
    history: list[dict] = []


class ReviewEvidenceLinkIn(BaseModel):
    status: str  # 'confirmed' | 'dismissed'


# ── Dashboard stats ────────────────────────────────────────────────────────────

@router.get("/my-team")
async def get_my_team(user: dict = Depends(get_current_user), org_id: str | None = None):
    """Return org members the current user may assign to workspaces.

    Supervisors get their invitees; org_admin gets all members; members get empty list.
    platform_admin can pass org_id as a query param to get all members of that org.
    """
    if _is_platform_admin(user):
        if not org_id:
            return []
        all_members = await asyncio.to_thread(list_org_members, org_id)
        return [m for m in all_members if m["user_id"] != user["user_id"]]

    membership = await asyncio.to_thread(_get_tendering_membership, user)
    member_org_id = membership["org_id"]
    role = membership["role"]
    if role == "member":
        return []
    all_members = await asyncio.to_thread(list_org_members, member_org_id)
    if role == "supervisor":
        user_id = user["user_id"]
        return [
            m for m in all_members
            if m.get("invited_by") == user_id and m["user_id"] != user_id
        ]
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
    # mode='json' serialises date/datetime fields to ISO strings before Supabase sees them.
    workspace = await asyncio.to_thread(db.create_workspace, org_id, body.model_dump(mode='json'), user["user_id"])
    return workspace


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    workspace = await _load_workspace_or_404(workspace_id, user)
    workspace["documents"] = await asyncio.to_thread(db.list_workspace_documents, workspace_id)
    return workspace


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: UpdateWorkspaceIn,
    user: dict = Depends(get_current_user),
):
    await _load_workspace_or_404(workspace_id, user)
    updated = await asyncio.to_thread(
        db.update_workspace, workspace_id, body.model_dump(exclude_none=True, mode='json')
    )
    if not updated:
        raise HTTPException(500, "Update failed")
    return updated


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    # Who *should* be allowed to delete a tender (creator only? org_admin only?) is a product
    # decision still open with the team. Until it lands, deletion at least follows the same rule
    # as viewing: a member who cannot open the tender can no longer delete it either.
    await _load_workspace_or_404(workspace_id, user)
    await asyncio.to_thread(db.delete_workspace, workspace_id)


@router.post("/workspaces/{workspace_id}/documents", status_code=201)
async def add_workspace_document(
    workspace_id: str,
    body: CreateWorkspaceDocumentIn,
    user: dict = Depends(get_current_user),
):
    await _load_workspace_or_404(workspace_id, user)
    # The browser uploads to `<workspace_id>/<file>` and then tells us the path. Without this
    # check it could name any file in the bucket — including another org's tender — and Extract
    # would fetch it with the service key and expose its text in this workspace.
    if body.storage_path and not is_storage_path_within(body.storage_path, workspace_id):
        raise HTTPException(400, "storage_path must be a file inside this workspace's folder")
    if body.url and not is_http_url(body.url):
        raise HTTPException(400, "url must be an http(s) link")

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


@router.post("/workspaces/{workspace_id}/documents/{doc_id}/extract", status_code=202,
             dependencies=[Depends(rate_limit("extraction", 60, 3600))])
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
    await _load_workspace_or_404(workspace_id, user)

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
    if core_doc.get("extraction_status") in ("queued", "processing"):
        raise HTTPException(409, "Extraction already in progress")

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
    await _load_workspace_or_404(workspace_id, user)

    workspace_doc = await asyncio.to_thread(db.get_workspace_document, doc_id)
    if not workspace_doc or workspace_doc["workspace_id"] != workspace_id:
        raise HTTPException(404, "Document not found")

    await asyncio.to_thread(db.delete_workspace_document, doc_id)


@router.get("/workspaces/{workspace_id}/documents/{doc_id}/extraction")
async def get_document_extraction(
    workspace_id: str,
    doc_id: str,
    user: dict = Depends(get_current_user),
):
    """Return the ADE-extracted markdown for a workspace document."""
    await _load_workspace_or_404(workspace_id, user)

    workspace_doc = await asyncio.to_thread(db.get_workspace_document, doc_id)
    if not workspace_doc or workspace_doc["workspace_id"] != workspace_id:
        raise HTTPException(404, "Document not found")

    core_document_id = workspace_doc.get("document_id")
    if not core_document_id:
        raise HTTPException(404, "Document not found")

    extraction = await asyncio.to_thread(db.get_extraction_by_document, core_document_id)
    if not extraction:
        raise HTTPException(404, "Extraction not available — run Extract first")

    markdown = (extraction.get("extracted_json") or {}).get("markdown") or ""
    return {"markdown": markdown}


@router.post("/workspaces/{workspace_id}/analyse", status_code=202,
             dependencies=[Depends(rate_limit("analysis", 10, 3600))])
async def analyse_workspace(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Trigger the pipeline: extract requirements → summarise → readiness review.

    Returns immediately (202); the pipeline runs in a background task. The workspace
    stage is set to 'analysing' at once so the UI can show progress.
    """
    workspace = await _load_workspace_or_404(workspace_id, user)
    # Two runs at once both delete the pending requirements and then insert their own, so the
    # workspace ends up with duplicates. The UI disables its button, but that does not cover two
    # people (or two tabs) starting a run within the same few seconds.
    if workspace.get("stage") == "analysing":
        raise HTTPException(409, "Analysis is already running for this workspace")

    await asyncio.to_thread(db.update_workspace, workspace_id, {"stage": "analysing"})

    def _run_pipeline() -> None:
        from .pipeline import run_workspace_analysis
        from backend.core.db_core import _reset_client
        try:
            result = run_workspace_analysis(workspace_id)
            next_stage = "new" if "error" in result else "preparing"
        except Exception:
            traceback.print_exc()
            next_stage = "new"
            _reset_client()  # flush stale HTTP/2 connection before the status update
        db.update_workspace(workspace_id, {"stage": next_stage})

    background_tasks.add_task(_run_pipeline)
    return {"status": "analysing", "workspace_id": workspace_id}


@router.get("/workspaces/{workspace_id}/requirements")
async def list_requirements(workspace_id: str, user: dict = Depends(get_current_user)):
    await _load_workspace_or_404(workspace_id, user)
    return await asyncio.to_thread(db.list_workspace_requirements, workspace_id)


@router.get("/workspaces/{workspace_id}/bid-decision")
async def get_bid_decision(workspace_id: str, user: dict = Depends(get_current_user)):
    await _load_workspace_or_404(workspace_id, user)
    decision = await asyncio.to_thread(db.get_workspace_bid_decision, workspace_id)
    if not decision:
        raise HTTPException(404, "No bid decision for this workspace")
    return decision


@router.post("/workspaces/{workspace_id}/generate-bid-decision", status_code=201,
             dependencies=[Depends(rate_limit("bid_decision", 20, 3600))])
async def generate_bid_decision(workspace_id: str, user: dict = Depends(get_current_user)):
    """Generate (and store) a bid/no-bid recommendation for this workspace.

    Synchronous: it is one LLM call over a report we already hold, and the caller wants the
    answer on screen. Returns the stored recommendation, in the same shape as GET bid-decision.

    It writes `workspace_bid_decisions.recommendation` only. The team's own `bid_decision` on the
    workspace stays where it is — a recommendation is an argument, and accepting it is a click a
    person makes (Rule 3).
    """
    await _load_workspace_or_404(workspace_id, user)
    from .pipeline import bid_decision

    try:
        return await asyncio.to_thread(bid_decision.generate, workspace_id)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        await asyncio.to_thread(
            db.write_workspace_audit, workspace_id, user.get("email") or "user",
            "bid_decision_generation_failed", {"error": f"{type(exc).__name__}: {exc}"[:500]},
        )
        raise HTTPException(502, "Could not generate a bid recommendation — please try again.")


# ── Evidence links ─────────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/evidence-links")
async def list_workspace_evidence_links(workspace_id: str, user: dict = Depends(get_current_user)):
    await _load_workspace_or_404(workspace_id, user)
    return await asyncio.to_thread(db.list_evidence_links, workspace_id)


@router.patch("/evidence-links/{link_id}")
async def review_evidence_link(
    link_id: str,
    body: ReviewEvidenceLinkIn,
    user: dict = Depends(get_current_user),
):
    if body.status not in ("confirmed", "dismissed"):
        raise HTTPException(400, "status must be 'confirmed' or 'dismissed'")
    link = await asyncio.to_thread(db.get_evidence_link, link_id)
    if not link:
        raise HTTPException(404, "Evidence link not found")
    await _load_workspace_or_404(link["workspace_id"], user, "Evidence link not found")
    await asyncio.to_thread(db.update_evidence_link_status, link_id, body.status)
    # Stamp the reviewer's email on the requirement so the matrix can show
    # "rejected by X" / "updated by X" alongside the recomputed status.
    reviewer_email = user.get("email") or ""
    await asyncio.to_thread(
        db.recalculate_requirement_status_from_evidence, link["req_id"], reviewer_email
    )
    await asyncio.to_thread(db.recalculate_workspace_readiness, link["workspace_id"])
    return {"id": link_id, "status": body.status}


# ── Requirements ───────────────────────────────────────────────────────────────

@router.patch("/requirements/{req_id}")
async def update_requirement(
    req_id: str,
    body: UpdateRequirementIn,
    user: dict = Depends(get_current_user),
):
    if body.status is not None and body.status not in _VALID_REQUIREMENT_STATUSES:
        raise HTTPException(
            400,
            f"status must be one of: {', '.join(sorted(_VALID_REQUIREMENT_STATUSES))}",
        )
    requirement = await asyncio.to_thread(db.get_requirement, req_id)
    if not requirement:
        raise HTTPException(404, "Requirement not found")
    workspace = await _load_workspace_or_404(
        requirement["workspace_id"], user, "Requirement not found"
    )
    patch = body.model_dump(exclude_none=True)
    # A manual status change is audited on the requirement itself, not just the audit log —
    # the compliance matrix shows the person and time next to the badge.
    if body.status is not None:
        patch["status_updated_by"] = user.get("email") or ""
    updated = await asyncio.to_thread(db.update_requirement, req_id, patch)
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
    if body.url and not is_http_url(body.url):
        raise HTTPException(400, "url must be an http(s) link")
    if body.storage_path:
        if not is_safe_storage_path(body.storage_path):
            raise HTTPException(400, "invalid storage_path")
        claimed = await asyncio.to_thread(db.get_supplier_document_by_storage_path, body.storage_path)
        if claimed and claimed.get("org_id") != org_id:
            raise HTTPException(409, "That file is already registered to another organisation")
    docs = await asyncio.to_thread(db.list_library_documents, org_id)
    if not any(d["doc_id"] == doc_id for d in docs):
        raise HTTPException(404, "Document not found")

    # storage_path lives on the vault row; everything else on the library row. A replace that
    # sends nothing but the new path is valid, so an empty metadata patch is not an error.
    patch = body.model_dump(exclude_none=True)
    patch.pop("storage_path", None)
    if patch:
        updated = await asyncio.to_thread(db.update_library_document, doc_id, patch)
        if not updated:
            raise HTTPException(500, "Update failed")

    if body.storage_path:
        await asyncio.to_thread(db.repoint_supplier_document, doc_id, body.storage_path, body.filename)

    refreshed = await asyncio.to_thread(db.list_library_documents, org_id)
    return next((d for d in refreshed if d["doc_id"] == doc_id), None)


@router.post("/library", status_code=201)
async def add_library_document(
    body: CreateLibraryDocumentIn,
    user: dict = Depends(get_current_user),
):
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    if body.url and not is_http_url(body.url):
        raise HTTPException(400, "url must be an http(s) link")
    if body.storage_path:
        if not is_safe_storage_path(body.storage_path):
            raise HTTPException(400, "invalid storage_path")
        # Vault uploads still land in one shared `general/` folder, so there is no per-org
        # prefix to check against (moving them under `<org_id>/` is the pending storage change,
        # together with making the buckets private). Until then, refuse a path another org has
        # already registered: that is the case where claiming a path means reading their file.
        claimed = await asyncio.to_thread(db.get_supplier_document_by_storage_path, body.storage_path)
        if claimed and claimed.get("org_id") != org_id:
            raise HTTPException(409, "That file is already registered to another organisation")

    data = body.model_dump(mode='json')
    library_doc = await asyncio.to_thread(db.create_library_document, org_id, data)

    if body.storage_path:
        await asyncio.to_thread(db.create_supplier_document, org_id, {
            "title": body.title,
            "doc_type": body.category,
            "storage_path": body.storage_path,
            "filename": body.filename,
            "issued_date": data.get("issue_date"),
            "expiry_date": data.get("expiry_date"),
            "library_doc_id": str(library_doc["doc_id"]),
        })
        # Extraction is triggered manually by the user clicking Extract on the doc card.

    return library_doc


@router.get("/library/{doc_id}/extraction")
async def get_library_document_extraction(doc_id: str, user: dict = Depends(get_current_user)):
    """Return ADE-extracted text for a library document (concatenated from vault chunks)."""
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    docs = await asyncio.to_thread(db.list_library_documents, org_id)
    if not any(d["doc_id"] == doc_id for d in docs):
        raise HTTPException(404, "Document not found")
    supplier_doc = await asyncio.to_thread(db.get_supplier_document_by_library_doc, doc_id)
    if not supplier_doc:
        raise HTTPException(404, "No vault entry — extract the document first")
    if supplier_doc.get("extraction_status") != "done":
        raise HTTPException(404, "Extraction not complete")
    chunks = await asyncio.to_thread(db.list_supplier_chunks, supplier_doc["supplier_document_id"])
    text = "\n\n".join(c["text"] for c in chunks if c.get("text"))
    return {"text": text, "chunk_count": len(chunks)}


@router.post("/library/{doc_id}/extract", status_code=202,
             dependencies=[Depends(rate_limit("extraction", 60, 3600))])
async def extract_library_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Trigger ADE extraction + embedding for a library document.

    Returns 202 immediately; vault processing runs in the background.
    The supplier_document row must already exist (created on upload via storage_path).
    """
    org_id = await asyncio.to_thread(_get_tendering_org_id, user)
    docs = await asyncio.to_thread(db.list_library_documents, org_id)
    if not any(d["doc_id"] == doc_id for d in docs):
        raise HTTPException(404, "Document not found")

    supplier_doc = await asyncio.to_thread(db.get_supplier_document_by_library_doc, doc_id)
    if not supplier_doc:
        raise HTTPException(409, "No vault entry for this document — re-upload to enable extraction")

    supplier_document_id = supplier_doc["supplier_document_id"]
    await asyncio.to_thread(
        db.update_supplier_document, supplier_document_id, {"extraction_status": "queued"}
    )
    from .pipeline.vault import process_supplier_document
    background_tasks.add_task(process_supplier_document, supplier_document_id)
    return {"status": "queued", "supplier_document_id": supplier_document_id}


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

@router.post("/workspaces/{workspace_id}/chat",
             dependencies=[Depends(rate_limit("chat", 30, 60))])
async def workspace_chat(
    workspace_id: str,
    body: WorkspaceChatIn,
    user: dict = Depends(get_current_user),
):
    from backend.core import llm

    workspace = await _load_workspace_or_404(workspace_id, user)

    # Retrieve relevant chunks from extracted documents
    chunks: list[dict] = []
    try:
        embedding = (await asyncio.to_thread(llm.embed, [body.message]))[0]
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
        traceback.print_exc()
        answer = "The AI assistant is temporarily unavailable. Check that the LLM provider is configured."

    citations = [
        {
            "document_id": c.get("document_id", ""),
            "page": c.get("page") or 0,
            "quoted_text": _clean_chunk_text(c.get("text") or ""),
            "chunk_id": c.get("chunk_id", ""),
        }
        for c in chunks
    ]
    return {"answer": answer, "citations": citations}
