"""Tendering data-access layer — all table touches for the tendering platform."""
from __future__ import annotations

from backend.core.db_core import get_client


def _normalize_requirement(req: dict) -> dict:
    """Rename DB columns to match frontend type expectations."""
    if "source_page" in req:
        req["page"] = req.pop("source_page")
    return req


def _enrich_workspaces(workspaces: list[dict]) -> list[dict]:
    for workspace in workspaces:
        requirements = (
            get_client()
            .table("workspace_requirements")
            .select("req_id, status")
            .eq("workspace_id", workspace["id"])
            .execute()
            .data
        ) or []
        workspace["requirements_count"] = len(requirements)
        workspace["requirements_met"] = sum(1 for r in requirements if r["status"] == "met")
        workspace["requirements_gap"] = sum(1 for r in requirements if r["status"] == "gap")
        workspace["requirements_partial"] = sum(1 for r in requirements if r["status"] == "partial")
    return workspaces


def list_tendering_workspaces(org_id: str) -> list[dict]:
    workspaces = (
        get_client()
        .table("tender_workspaces")
        .select("*")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
        .data
    ) or []
    return _enrich_workspaces(workspaces)


def list_tendering_workspaces_for_supervisor(org_id: str, supervisor_user_id: str) -> list[dict]:
    from backend.core.db_core import list_team_member_ids
    team_ids = list_team_member_ids(org_id, supervisor_user_id)
    creator_ids = [supervisor_user_id] + team_ids
    workspaces = (
        get_client()
        .table("tender_workspaces")
        .select("*")
        .eq("org_id", org_id)
        .in_("created_by", creator_ids)
        .order("created_at", desc=True)
        .execute()
        .data
    ) or []
    return _enrich_workspaces(workspaces)


def list_tendering_workspaces_for_member(org_id: str, user_id: str) -> list[dict]:
    own = (
        get_client()
        .table("tender_workspaces")
        .select("*")
        .eq("org_id", org_id)
        .eq("created_by", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    ) or []
    assigned = (
        get_client()
        .table("tender_workspaces")
        .select("*")
        .eq("org_id", org_id)
        .contains("team_members", [user_id])
        .order("created_at", desc=True)
        .execute()
        .data
    ) or []
    seen: set[str] = set()
    combined: list[dict] = []
    for workspace in own + assigned:
        if workspace["id"] not in seen:
            seen.add(workspace["id"])
            combined.append(workspace)
    return _enrich_workspaces(combined)


def get_tendering_workspace(workspace_id: str) -> dict | None:
    rows = (
        get_client()
        .table("tender_workspaces")
        .select("*")
        .eq("id", workspace_id)
        .execute()
        .data
    )
    return rows[0] if rows else None


def create_workspace(org_id: str, data: dict, created_by: str = "") -> dict:
    row = (
        get_client()
        .table("tender_workspaces")
        .insert({
            "org_id": org_id,
            "title": data["title"],
            "reference": data.get("reference", ""),
            "buyer": data.get("buyer", ""),
            "category": data.get("category", ""),
            "closing_date": data.get("closing_date"),
            "contract_value": data.get("contract_value", 0),
            "currency": data.get("currency", "USD"),
            "created_by": created_by,
        })
        .execute()
        .data
    )
    workspace = row[0]
    workspace["requirements_count"] = 0
    workspace["requirements_met"] = 0
    workspace["requirements_gap"] = 0
    workspace["requirements_partial"] = 0
    workspace["documents"] = []
    return workspace


def update_workspace(workspace_id: str, patch: dict) -> dict | None:
    allowed = {
        "title", "reference", "buyer", "category", "closing_date",
        "contract_value", "currency", "stage", "bid_decision",
        "readiness_score", "description", "team_members",
    }
    safe_patch = {key: value for key, value in patch.items() if key in allowed and value is not None}
    if not safe_patch:
        return get_tendering_workspace(workspace_id)
    row = (
        get_client()
        .table("tender_workspaces")
        .update(safe_patch)
        .eq("id", workspace_id)
        .execute()
        .data
    )
    return row[0] if row else None


def list_workspace_documents(workspace_id: str) -> list[dict]:
    return (
        get_client()
        .table("workspace_documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("uploaded_at", desc=True)
        .execute()
        .data
    ) or []


def list_workspace_requirements(workspace_id: str) -> list[dict]:
    requirements = (
        get_client()
        .table("workspace_requirements")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("created_at")
        .execute()
        .data
    ) or []
    return [_normalize_requirement(req) for req in requirements]


def get_requirement(req_id: str) -> dict | None:
    rows = (
        get_client()
        .table("workspace_requirements")
        .select("*")
        .eq("req_id", req_id)
        .execute()
        .data
    )
    return _normalize_requirement(rows[0]) if rows else None


def update_requirement(req_id: str, patch: dict) -> dict | None:
    allowed = {"status", "owner", "notes"}
    safe_patch = {key: value for key, value in patch.items() if key in allowed and value is not None}
    if not safe_patch:
        return get_requirement(req_id)
    row = (
        get_client()
        .table("workspace_requirements")
        .update(safe_patch)
        .eq("req_id", req_id)
        .execute()
        .data
    )
    return _normalize_requirement(row[0]) if row else None


def recalculate_workspace_readiness(workspace_id: str) -> int:
    requirements = (
        get_client()
        .table("workspace_requirements")
        .select("status")
        .eq("workspace_id", workspace_id)
        .execute()
        .data
    ) or []
    total = len(requirements)
    if not total:
        return 0
    met = sum(1 for r in requirements if r["status"] == "met")
    partial = sum(1 for r in requirements if r["status"] == "partial")
    score = round((met + partial * 0.5) / total * 100)
    get_client().table("tender_workspaces").update({"readiness_score": score}).eq("id", workspace_id).execute()
    return score


def get_workspace_bid_decision(workspace_id: str) -> dict | None:
    rows = (
        get_client()
        .table("workspace_bid_decisions")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def create_workspace_document(workspace_id: str, data: dict) -> dict:
    row = (
        get_client()
        .table("workspace_documents")
        .insert({
            "workspace_id": workspace_id,
            "name": data["name"],
            "category": data.get("category", "supporting"),
            "file_type": data.get("file_type", ""),
            "size_bytes": data.get("size_bytes", 0),
            "url": data.get("url", ""),
        })
        .execute()
        .data
    )
    return row[0]


def create_library_document(org_id: str, data: dict) -> dict:
    row = (
        get_client()
        .table("library_documents")
        .insert({
            "org_id": org_id,
            "title": data["title"],
            "filename": data.get("filename", ""),
            "category": data.get("category", "other"),
            "file_type": data.get("file_type", ""),
            "issue_date": data.get("issue_date"),
            "expiry_date": data.get("expiry_date"),
            "tags": data.get("tags", []),
            "url": data.get("url", ""),
        })
        .execute()
        .data
    )
    return row[0]


def update_library_document(doc_id: str, patch: dict) -> dict | None:
    allowed = {"title", "filename", "category", "file_type", "issue_date", "expiry_date", "tags", "url", "verification_status"}
    safe_patch = {key: value for key, value in patch.items() if key in allowed and value is not None}
    if not safe_patch:
        return None
    row = (
        get_client()
        .table("library_documents")
        .update(safe_patch)
        .eq("doc_id", doc_id)
        .execute()
        .data
    )
    return row[0] if row else None


def list_library_documents(org_id: str) -> list[dict]:
    return (
        get_client()
        .table("library_documents")
        .select("*")
        .eq("org_id", org_id)
        .order("uploaded_at", desc=True)
        .execute()
        .data
    ) or []


# ─────────────────────── Pipeline support ────────────────────────────────────

import hashlib as _hashlib


def requirement_hash(row: dict) -> str:
    """Stable dedup key — description + source doc + page."""
    text = (row.get("description") or "").strip().lower()
    source = str(row.get("source_doc") or row.get("source_document_id") or "")
    page = str(row.get("source_page") or "")
    return _hashlib.md5(f"{text}|{source}|{page}".encode()).hexdigest()


def list_pipeline_documents(workspace_id: str) -> list[dict]:
    """Return workspace documents that have a linked core document_id (processable by ADE)."""
    rows = (
        get_client()
        .table("workspace_documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
        .data
    ) or []
    # Return all docs; callers filter on extraction_status via the core documents row.
    return rows


def get_core_document(document_id: str) -> dict | None:
    rows = get_client().table("documents").select("*").eq("document_id", document_id).execute().data
    return rows[0] if rows else None


def list_core_documents_for_workspace(workspace_id: str) -> list[dict]:
    return (
        get_client()
        .table("documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
        .data
    ) or []


def delete_workspace_requirements(workspace_id: str, pending_only: bool = False) -> None:
    """Delete requirements for a workspace. If pending_only, only deletes unchecked ones."""
    query = get_client().table("workspace_requirements").delete().eq("workspace_id", workspace_id)
    if pending_only:
        query = query.eq("status", "unchecked")
    query.execute()


def insert_workspace_requirement(data: dict) -> dict | None:
    try:
        return get_client().table("workspace_requirements").insert(data).execute().data[0]
    except Exception:
        return None


def list_workspace_requirements_raw(workspace_id: str) -> list[dict]:
    """Return requirements without frontend field renaming — for pipeline use."""
    return (
        get_client()
        .table("workspace_requirements")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
        .data
    ) or []


def list_evidence_links(workspace_id: str) -> list[dict]:
    return (
        get_client()
        .table("evidence_links")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
        .data
    ) or []


def upsert_evidence_link(data: dict) -> dict | None:
    try:
        return (
            get_client()
            .table("evidence_links")
            .upsert(data, on_conflict="req_id,doc_id")
            .execute()
            .data[0]
        )
    except Exception:
        return None


def write_workspace_audit(workspace_id: str, actor: str, action: str, detail: dict | None = None) -> None:
    get_client().table("audit_log").insert({
        "case_id": None,
        "workspace_id": workspace_id,
        "actor": actor,
        "action": action,
        "detail": detail or {},
    }).execute()


def get_extraction_by_document(document_id: str) -> dict | None:
    from backend.core.db_core import get_extraction_by_document as _core_get
    return _core_get(document_id)


def list_chunks(document_id: str) -> list[dict]:
    from backend.core.db_core import list_chunks as _core_list
    return _core_list(document_id)
