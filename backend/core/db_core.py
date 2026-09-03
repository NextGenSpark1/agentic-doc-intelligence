"""Supabase data-access layer.

Every table touch goes through here so the rest of the codebase never builds raw
queries inline. supabase-py v2 is synchronous; we therefore keep these helpers sync
and call them from async endpoints via `asyncio.to_thread`, and run the pipeline in a
FastAPI BackgroundTask (which executes sync work in a threadpool). That keeps the event
loop unblocked without dragging in an async DB driver for the MVP.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any, Optional

from supabase import Client, create_client

from .config import get_settings


def _content_hash(*parts: object) -> str:
    """Stable dedup key for a row. MUST mirror the SQL formula used by the unique indexes in
    schema.sql (``md5(part || chr(0) || part ...)``) so a Python-inserted row and a SQL-backfilled
    row collide correctly. None is treated as '' (matches SQL ``coalesce(x,'')``)."""
    joined = "\x00".join("" if p is None else str(p) for p in parts)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()


def _is_unique_violation(err: Exception) -> bool:
    return getattr(err, "code", None) == "23505" or "duplicate key" in str(err).lower()


@lru_cache
def get_client() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        raise RuntimeError(
            "Supabase credentials missing. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env."
        )
    return create_client(s.supabase_url, s.supabase_service_key)


# ----------------------------- Cases -----------------------------
def insert_case(data: dict) -> dict:
    return get_client().table("cases").insert(data).execute().data[0]


def get_case(case_id: str) -> Optional[dict]:
    rows = get_client().table("cases").select("*").eq("case_id", case_id).execute().data
    return rows[0] if rows else None


def list_cases(
    owner_id: str | None = None,
    org_id: str | None = None,
    created_by: str | None = None,
) -> list[dict]:
    query = get_client().table("cases").select("*").order("created_at", desc=True)
    if org_id:
        query = query.eq("org_id", org_id)
        if created_by:
            # Team-scoped: supervisor sees own cases; member sees their supervisor's cases.
            query = query.eq("created_by", created_by)
    elif owner_id:
        # Legacy path (no org yet): show cases owned by this user + NULL-owner rows.
        query = query.or_(f"owner_id.eq.{owner_id},owner_id.is.null")
    return query.execute().data


def update_case(case_id: str, patch: dict) -> dict:
    return get_client().table("cases").update(patch).eq("case_id", case_id).execute().data[0]


# --------------------------- Documents ---------------------------
def insert_document(data: dict) -> dict:
    return get_client().table("documents").insert(data).execute().data[0]


def update_document(document_id: str, patch: dict) -> dict:
    return get_client().table("documents").update(patch).eq("document_id", document_id).execute().data[0]


def get_document(document_id: str) -> Optional[dict]:
    rows = get_client().table("documents").select("*").eq("document_id", document_id).execute().data
    return rows[0] if rows else None


def list_documents(case_id: str) -> list[dict]:
    return get_client().table("documents").select("*").eq("case_id", case_id).execute().data


def count_documents(case_id: str) -> int:
    """Row count only — no payload transferred (for list views that just need the number)."""
    res = (
        get_client().table("documents").select("document_id", count="exact")
        .eq("case_id", case_id).limit(0).execute()
    )
    return res.count or 0


def count_pending_findings(case_id: str) -> int:
    res = (
        get_client().table("findings").select("finding_id", count="exact")
        .eq("case_id", case_id).eq("human_review_status", "pending").limit(0).execute()
    )
    return res.count or 0


# -------------------------- Extractions --------------------------
def insert_extraction(data: dict) -> dict:
    return get_client().table("extractions").insert(data).execute().data[0]


def get_extraction_by_document(document_id: str) -> Optional[dict]:
    rows = (
        get_client()
        .table("extractions")
        .select("*")
        .eq("document_id", document_id)
        .order("extracted_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def get_document_raw_text(document_id: str) -> str:
    """Reconstruct raw text from indexed chunks in page order."""
    rows = (
        get_client()
        .table("chunks")
        .select("text, page")
        .eq("document_id", document_id)
        .order("page")
        .execute()
        .data
    )
    return "\n\n".join(r["text"] for r in rows if r.get("text"))


def update_extraction(extraction_id: str, patch: dict) -> dict:
    return get_client().table("extractions").update(patch).eq("extraction_id", extraction_id).execute().data[0]


def list_extractions(case_id: str) -> list[dict]:
    # join via documents to scope by case
    docs = list_documents(case_id)
    doc_ids = [d["document_id"] for d in docs]
    if not doc_ids:
        return []
    return get_client().table("extractions").select("*").in_("document_id", doc_ids).execute().data


# ---------------------------- Chunks (RAG) -----------------------
def insert_chunks(rows: list[dict]) -> None:
    if rows:
        get_client().table("chunks").insert(rows).execute()


def list_chunks(document_id: str) -> list[dict]:
    return (
        get_client().table("chunks")
        .select("chunk_id,text,type,page,bbox")
        .eq("document_id", document_id)
        .execute()
        .data or []
    )


def match_chunks(case_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """Vector similarity search via a Postgres RPC (see schema.sql -> match_chunks)."""
    return get_client().rpc(
        "match_chunks",
        {"p_case_id": case_id, "p_query_embedding": query_embedding, "p_match_count": top_k},
    ).execute().data or []


def match_chunks_candidates(
    case_id: str, query_embedding: list[float], query_text: str, pool: int
) -> list[dict]:
    """Hybrid-retrieval candidate pool: dense + keyword arms with each arm's rank.

    Fusion is done by backend/core/retrieval.py, not here — see that module for why.
    Both arms filter on case_id inside SQL (schema.sql -> match_chunks_candidates).
    """
    return get_client().rpc(
        "match_chunks_candidates",
        {
            "p_case_id": case_id,
            "p_query_embedding": query_embedding,
            "p_query_text": query_text,
            "p_pool": pool,
        },
    ).execute().data or []


def match_chunks_in_document(document_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """Vector similarity search scoped to a single document — used for finding traceability."""
    return get_client().rpc(
        "match_chunks_in_document",
        {"p_document_id": document_id, "p_query_embedding": query_embedding, "p_match_count": top_k},
    ).execute().data or []


# ------------------------- Audit log -----------------------------
def write_audit(case_id: str | None, actor: str, action: str, detail: dict | None = None,
                tender_id: str | None = None) -> None:
    """Append one audit row.

    `case_id` and `tender_id` are parallel nullable columns — a row belongs to whichever
    workspace produced it. Keeping both on one helper means there is a single place where audit
    rows are written, so an action can never quietly skip the trail by using a different path.
    """
    get_client().table("audit_log").insert(
        {"case_id": case_id, "tender_id": tender_id, "actor": actor,
         "action": action, "detail": detail or {}}
    ).execute()


# ---------------------------- Storage ----------------------------
def upload_evidence(storage_path: str, content: bytes, content_type: str) -> str:
    s = get_settings()
    get_client().storage.from_(s.storage_bucket).upload(
        storage_path, content, {"content-type": content_type, "upsert": "true"}
    )
    return storage_path


def signed_url(storage_path: str, expires_in: int = 3600) -> str:
    s = get_settings()
    res = get_client().storage.from_(s.storage_bucket).create_signed_url(storage_path, expires_in)
    return res.get("signedURL") or res.get("signedUrl", "")


def delete_case(case_id: str) -> None:
    """Delete a case and all its documents (files + rows) from storage and DB."""
    s = get_settings()
    client = get_client()
    docs = client.table("documents").select("document_id, storage_path").eq("case_id", case_id).execute().data or []
    paths = [d["storage_path"] for d in docs if d.get("storage_path")]
    if paths:
        client.storage.from_(s.storage_bucket).remove(paths)
    client.table("documents").delete().eq("case_id", case_id).execute()
    client.table("cases").delete().eq("case_id", case_id).execute()


def delete_document(document_id: str, storage_path: str) -> None:
    """Delete file from Storage then drop the documents row.

    Related rows (extractions, chunks) are not cascade-deleted here — add
    ON DELETE CASCADE FK constraints in schema.sql and remove this note then.
    """
    s = get_settings()
    get_client().storage.from_(s.storage_bucket).remove([storage_path])
    get_client().table("documents").delete().eq("document_id", document_id).execute()


# ─────────────────────── Organisations ───────────────────────────

def create_org(org_id: str, name: str, plan: str, created_by: str) -> dict:
    return get_client().table("organisations").insert({
        "org_id": org_id, "name": name, "plan": plan, "created_by": created_by,
    }).execute().data[0]


def get_org(org_id: str) -> dict | None:
    rows = get_client().table("organisations").select("*").eq("org_id", org_id).execute().data
    return rows[0] if rows else None


def list_orgs() -> list[dict]:
    return get_client().table("organisations").select("*").order("created_at", desc=True).execute().data


def get_org_member(org_id: str, user_id: str) -> dict | None:
    rows = get_client().table("org_members").select("*").eq("org_id", org_id).eq("user_id", user_id).execute().data
    return rows[0] if rows else None


def get_user_membership(user_id: str) -> dict | None:
    """Return the user's org membership (first org found — users belong to one org)."""
    rows = get_client().table("org_members").select("*, organisations(name, plan)").eq("user_id", user_id).execute().data
    return rows[0] if rows else None


def list_org_members(org_id: str) -> list[dict]:
    return get_client().table("org_members").select("*").eq("org_id", org_id).order("joined_at").execute().data


def add_org_member(org_id: str, user_id: str, email: str, role: str, invited_by: str, full_name: str | None = None) -> dict:
    return get_client().table("org_members").insert({
        "org_id": org_id, "user_id": user_id, "email": email,
        "role": role, "invited_by": invited_by, "full_name": full_name,
    }).execute().data[0]


def remove_org_member(org_id: str, user_id: str) -> None:
    get_client().table("org_members").delete().eq("org_id", org_id).eq("user_id", user_id).execute()


def create_invitation(org_id: str, email: str, role: str, invited_by: str) -> dict:
    return get_client().table("invitations").insert({
        "org_id": org_id, "email": email, "role": role, "invited_by": invited_by,
    }).execute().data[0]


def get_invitation_by_token(token: str) -> dict | None:
    rows = get_client().table("invitations").select("*, organisations(name)").eq("token", token).execute().data
    return rows[0] if rows else None


def accept_invitation(token: str) -> None:
    from datetime import datetime, timezone
    get_client().table("invitations").update({"accepted_at": datetime.now(timezone.utc).isoformat()}).eq("token", token).execute()


def list_org_cases_count(org_id: str) -> int:
    result = get_client().table("cases").select("case_id", count="exact").eq("org_id", org_id).execute()
    return result.count or 0
