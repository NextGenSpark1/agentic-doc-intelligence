"""Tendering data-access layer — all table touches for the tendering platform."""
from __future__ import annotations

from backend.core.db_core import get_client


def _normalize_requirement(req: dict) -> dict:
    """Rename DB columns to match frontend type expectations."""
    if "source_page" in req:
        req["page"] = req.pop("source_page")
    return req


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


def create_workspace(org_id: str, data: dict) -> dict:
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
