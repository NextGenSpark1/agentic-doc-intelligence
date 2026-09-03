"""Tendering data access — tenders, requirements, vault, evidence links, tasks.

The generic tables (documents, chunks, extractions, orgs, storage, audit) live in
`backend.core.db_core` and are re-exported here so tender code has one `db` facade, exactly as
`apps.investigation.db` does. This module owns only the tender-domain tables.

Tender documents reuse the shared `documents` and `chunks` tables via a nullable `tender_id`,
so the whole extract/chunk/embed pipeline is reused rather than reimplemented.
"""
from __future__ import annotations

from typing import Optional

from backend.core.db_core import _content_hash, _is_unique_violation, get_client
# Re-export the generic (core) data-access functions. New generic helpers added to core are
# picked up automatically.
from backend.core.db_core import *  # noqa: F401,F403

try:  # import path differs slightly across supabase-py / postgrest versions
    from postgrest.exceptions import APIError
except Exception:  # pragma: no cover - fall back to a broad catch if the path moves
    APIError = Exception  # type: ignore[assignment, misc]


# ------------------------------ tenders ------------------------------
def insert_tender(data: dict) -> dict:
    return get_client().table("tenders").insert(data).execute().data[0]


def get_tender(tender_id: str) -> Optional[dict]:
    rows = get_client().table("tenders").select("*").eq("tender_id", tender_id).execute().data
    return rows[0] if rows else None


def update_tender(tender_id: str, patch: dict) -> Optional[dict]:
    rows = get_client().table("tenders").update(patch).eq("tender_id", tender_id).execute().data
    return rows[0] if rows else None


def delete_tender(tender_id: str) -> None:
    get_client().table("tenders").delete().eq("tender_id", tender_id).execute()


def list_tenders(org_id: str | None = None, created_by: str | None = None,
                 owner_id: str | None = None) -> list[dict]:
    """Team-scoped tender listing, mirroring `core.db_core.list_cases`.

    Same scoping rules as cases so the two products do not drift into different visibility
    models: org filter first, then the team filter the caller's role implies.
    """
    query = get_client().table("tenders").select("*").order("created_at", desc=True)
    if org_id:
        query = query.eq("org_id", org_id)
        if created_by:
            query = query.eq("created_by", created_by)
    elif owner_id:
        query = query.eq("owner_id", owner_id)
    return query.execute().data or []


# ------------------------- tender documents -------------------------
def list_tender_documents(tender_id: str) -> list[dict]:
    return (
        get_client().table("documents").select("*")
        .eq("tender_id", tender_id).order("uploaded_at", desc=True)
        .execute().data or []
    )


def count_tender_documents(tender_id: str) -> int:
    res = (
        get_client().table("documents").select("document_id", count="exact")
        .eq("tender_id", tender_id).execute()
    )
    return res.count or 0


def write_tender_audit(tender_id: str, actor: str, action: str, detail: dict | None = None) -> None:
    """Audit a tender action.

    A thin alias over core's `write_audit` that fills the tender column instead of the case
    one, so tender code never has to remember which keyword to pass — and audit rows still all
    go through the single core helper.
    """
    from backend.core.db_core import write_audit as _write_audit

    _write_audit(None, actor, action, detail, tender_id=tender_id)


# --------------------------- requirements ---------------------------
def requirement_hash(data: dict) -> str:
    """Dedup key for a requirement.

    Category is included alongside the description because the same sentence can legitimately
    be both a submission instruction and a technical obligation; collapsing those would lose a
    distinction the compliance matrix depends on.
    """
    return _content_hash(
        (data.get("description") or "").strip().lower(),
        (data.get("category") or "").strip().lower(),
        str(data.get("source_document_id") or ""),
    )


def insert_requirement(data: dict) -> Optional[dict]:
    """Insert a requirement, skipping one already present for this tender in *pending* status.

    Mirrors `investigation.db.insert_finding`: a re-run must not double-insert unreviewed rows,
    while confirmed/dismissed rows stay out of scope so a re-run can resurface something a human
    already ruled on. The partial unique index is the race-proof backstop; this check covers the
    common path and works before that migration has been applied.
    """
    row = {**data, "content_hash": requirement_hash(data)}
    client = get_client()
    existing = (
        client.table("requirements").select("requirement_id")
        .eq("tender_id", data["tender_id"]).eq("content_hash", row["content_hash"])
        .eq("human_review_status", "pending")
        .limit(1).execute().data
    )
    if existing:
        return None
    try:
        return client.table("requirements").insert(row).execute().data[0]
    except APIError as e:
        if _is_unique_violation(e):
            return None  # lost a race to a concurrent re-run; the existing row stands
        raise


def list_requirements(tender_id: str, category: str | None = None,
                      review_status: str | None = None) -> list[dict]:
    q = get_client().table("requirements").select("*").eq("tender_id", tender_id)
    if category:
        q = q.eq("category", category)
    if review_status:
        q = q.eq("human_review_status", review_status)
    return q.execute().data or []


def get_requirement(requirement_id: str) -> Optional[dict]:
    rows = (
        get_client().table("requirements").select("*")
        .eq("requirement_id", requirement_id).execute().data
    )
    return rows[0] if rows else None


def update_requirement(requirement_id: str, patch: dict) -> Optional[dict]:
    rows = (
        get_client().table("requirements").update(patch)
        .eq("requirement_id", requirement_id).execute().data
    )
    return rows[0] if rows else None  # None when the id doesn't exist — caller maps to 404


def delete_requirements(tender_id: str, pending_only: bool = True) -> None:
    """Clear requirements before re-extraction.

    Defaults to pending-only so a re-run never destroys human review decisions.
    """
    q = get_client().table("requirements").delete().eq("tender_id", tender_id)
    if pending_only:
        q = q.eq("human_review_status", "pending")
    q.execute()


# ------------------------ supplier vault (org) ------------------------
def insert_supplier_document(data: dict) -> dict:
    return get_client().table("supplier_documents").insert(data).execute().data[0]


def get_supplier_document(supplier_document_id: str) -> Optional[dict]:
    rows = (
        get_client().table("supplier_documents").select("*")
        .eq("supplier_document_id", supplier_document_id).execute().data
    )
    return rows[0] if rows else None


def list_supplier_documents(org_id: str, include_superseded: bool = False) -> list[dict]:
    """List an org's vault. Always org-scoped — there is no unscoped variant on purpose."""
    q = get_client().table("supplier_documents").select("*").eq("org_id", org_id)
    if not include_superseded:
        q = q.is_("superseded_by", "null")
    return q.order("created_at", desc=True).execute().data or []


def update_supplier_document(supplier_document_id: str, patch: dict) -> Optional[dict]:
    rows = (
        get_client().table("supplier_documents").update(patch)
        .eq("supplier_document_id", supplier_document_id).execute().data
    )
    return rows[0] if rows else None


def insert_supplier_chunks(rows: list[dict]) -> None:
    if rows:
        get_client().table("supplier_document_chunks").insert(rows).execute()


def match_supplier_docs(org_id: str, query_embedding: list[float], top_k: int,
                        include_expired: bool = False) -> list[dict]:
    """Vector search over an org's vault.

    Rule 4: the org filter lives inside the SQL function (see schema_tendering.sql), not here —
    so org isolation cannot be lost by an application-layer mistake. This wrapper passes org_id
    through; it is not what enforces it.
    """
    return get_client().rpc(
        "match_supplier_docs",
        {
            "p_org_id": org_id,
            "p_query_embedding": query_embedding,
            "p_match_count": top_k,
            "p_include_expired": include_expired,
        },
    ).execute().data or []


def match_tender_chunks(tender_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """Vector search over one tender's own documents (not the vault)."""
    return get_client().rpc(
        "match_tender_chunks",
        {"p_tender_id": tender_id, "p_query_embedding": query_embedding, "p_match_count": top_k},
    ).execute().data or []


# --------------------------- evidence links ---------------------------
def upsert_evidence_link(data: dict) -> Optional[dict]:
    """Insert or update the link between a requirement and a vault document.

    Unique on (requirement_id, supplier_document_id), so re-running matching refreshes a
    proposal rather than duplicating it. A link a human has already reviewed is left alone —
    re-running the matcher must not silently reset someone's decision to pending.
    """
    client = get_client()
    existing = (
        client.table("evidence_links").select("*")
        .eq("requirement_id", data["requirement_id"])
        .eq("supplier_document_id", data["supplier_document_id"])
        .limit(1).execute().data
    )
    if existing:
        current = existing[0]
        if current.get("human_review_status") != "pending":
            return None  # reviewed by a human — leave it alone
        patch = {k: data[k] for k in ("match_score", "rationale", "matched_chunk_id") if k in data}
        rows = (
            client.table("evidence_links").update(patch)
            .eq("evidence_link_id", current["evidence_link_id"]).execute().data
        )
        return rows[0] if rows else None
    try:
        return client.table("evidence_links").insert(data).execute().data[0]
    except APIError as e:
        if _is_unique_violation(e):
            return None  # lost a race to a concurrent run
        raise


def list_evidence_links(requirement_id: str) -> list[dict]:
    return (
        get_client().table("evidence_links").select("*")
        .eq("requirement_id", requirement_id).order("match_score", desc=True)
        .execute().data or []
    )


def list_evidence_links_for_tender(tender_id: str) -> list[dict]:
    """Every evidence link on a tender, in one round trip.

    Joins through requirements so the compliance matrix and readiness review do not issue one
    query per requirement.
    """
    requirement_ids = [
        r["requirement_id"] for r in
        (get_client().table("requirements").select("requirement_id")
         .eq("tender_id", tender_id).execute().data or [])
    ]
    if not requirement_ids:
        return []
    return (
        get_client().table("evidence_links").select("*")
        .in_("requirement_id", requirement_ids).execute().data or []
    )


def get_evidence_link(evidence_link_id: str) -> Optional[dict]:
    rows = (
        get_client().table("evidence_links").select("*")
        .eq("evidence_link_id", evidence_link_id).execute().data
    )
    return rows[0] if rows else None


def update_evidence_link(evidence_link_id: str, patch: dict) -> Optional[dict]:
    rows = (
        get_client().table("evidence_links").update(patch)
        .eq("evidence_link_id", evidence_link_id).execute().data
    )
    return rows[0] if rows else None


# ------------------------------- tasks -------------------------------
def insert_task(data: dict) -> dict:
    return get_client().table("tasks").insert(data).execute().data[0]


def list_tasks(tender_id: str) -> list[dict]:
    return get_client().table("tasks").select("*").eq("tender_id", tender_id).execute().data or []


def get_task(task_id: str) -> Optional[dict]:
    rows = get_client().table("tasks").select("*").eq("task_id", task_id).execute().data
    return rows[0] if rows else None


def update_task(task_id: str, patch: dict) -> Optional[dict]:
    rows = get_client().table("tasks").update(patch).eq("task_id", task_id).execute().data
    return rows[0] if rows else None


def delete_task(task_id: str) -> None:
    get_client().table("tasks").delete().eq("task_id", task_id).execute()
