"""Tendering data-access layer — all table touches for the tendering platform."""
from __future__ import annotations

from backend.core.db_core import get_client


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
    return (
        get_client()
        .table("workspace_requirements")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("created_at")
        .execute()
        .data
    ) or []


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
