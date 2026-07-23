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

try:  # import path differs slightly across supabase-py / postgrest versions
    from postgrest.exceptions import APIError
except Exception:  # pragma: no cover - fall back to a broad catch if the path moves
    APIError = Exception  # type: ignore[assignment, misc]


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


def match_chunks_in_document(document_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """Vector similarity search scoped to a single document — used for finding traceability."""
    return get_client().rpc(
        "match_chunks_in_document",
        {"p_document_id": document_id, "p_query_embedding": query_embedding, "p_match_count": top_k},
    ).execute().data or []


# ---------------------------- Entities ---------------------------
def upsert_entity(data: dict) -> dict:
    # on_conflict on (case_id, entity_type, canonical_name) keeps entities deduped
    return (
        get_client()
        .table("entities")
        .upsert(data, on_conflict="case_id,entity_type,canonical_name")
        .execute()
        .data[0]
    )


def list_entities(case_id: str) -> list[dict]:
    return get_client().table("entities").select("*").eq("case_id", case_id).execute().data


# ------------------------- Relationships -------------------------
def insert_relationship(data: dict) -> Optional[dict]:
    """Insert an edge, skipping if the same edge (case + source + target + type) already exists.
    Analysis re-runs delete + re-insert; without this a concurrent re-run can double-insert
    before the delete lands. The unique index (case_id, content_hash) in schema.sql is the
    race-proof backstop; this check covers the common path and works before that migration runs.
    Returns the inserted row, or None if a matching edge was already present."""
    row = {**data, "content_hash": _content_hash(
        (data.get("source_name") or "").lower(),
        (data.get("target_name") or "").lower(),
        (data.get("relationship_type") or "").lower(),
    )}
    client = get_client()
    existing = (
        client.table("relationships").select("relationship_id")
        .eq("case_id", data["case_id"]).eq("content_hash", row["content_hash"])
        .limit(1).execute().data
    )
    if existing:
        return None
    try:
        return client.table("relationships").insert(row).execute().data[0]
    except APIError as e:
        if _is_unique_violation(e):
            return None  # lost a race to a concurrent re-run; the existing edge stands
        raise


def list_relationships(case_id: str) -> list[dict]:
    return get_client().table("relationships").select("*").eq("case_id", case_id).execute().data


# ---------------------------- Findings ---------------------------
def insert_finding(data: dict) -> Optional[dict]:
    """Insert a finding, skipping if an identical one (same finding_type + statement) already
    exists for this case in *pending* status. Guards against duplicate rows when analysis is
    re-run while a previous run's rows haven't been cleared yet. The partial unique index
    (case_id, content_hash) WHERE pending in schema.sql is the race-proof backstop; this check
    covers the common path and works before that migration runs. Confirmed/dismissed findings
    are intentionally out of scope, so a re-run can still resurface a previously-reviewed issue.
    Returns the inserted row, or None if a matching pending finding was already present."""
    row = {**data, "content_hash": _content_hash(
        (data.get("finding_type") or "").lower(),
        data.get("statement") or "",
    )}
    client = get_client()
    existing = (
        client.table("findings").select("finding_id")
        .eq("case_id", data["case_id"]).eq("content_hash", row["content_hash"])
        .eq("human_review_status", "pending")
        .limit(1).execute().data
    )
    if existing:
        return None
    try:
        return client.table("findings").insert(row).execute().data[0]
    except APIError as e:
        if _is_unique_violation(e):
            return None  # lost a race to a concurrent re-run; the existing finding stands
        raise


def insert_timeline_events(events: list[dict]) -> None:
    """Bulk-insert timeline events, skipping any (case + date + label + document) already present.
    Mirrors the finding/relationship dedup for the raw timeline insert. Normally the caller has
    just deleted the case's events, so the pre-filter is a no-op; it only bites under a
    concurrent re-run, where the unique index (case_id, content_hash) is the final backstop."""
    if not events:
        return
    client = get_client()
    rows = [{**e, "content_hash": _content_hash(
        e.get("event_date") or "", e.get("label") or "", e.get("document_id") or "")}
        for e in events]
    present = {
        r["content_hash"] for r in (
            client.table("timeline_events").select("content_hash")
            .eq("case_id", events[0]["case_id"]).execute().data or []
        )
    }
    fresh = [r for r in rows if r["content_hash"] not in present]
    if not fresh:
        return
    try:
        client.table("timeline_events").insert(fresh).execute()
    except APIError as e:
        if not _is_unique_violation(e):
            raise
        # A concurrent re-run inserted overlapping rows between our read and write; fall back to
        # per-row inserts so the non-colliding events still land.
        for r in fresh:
            try:
                client.table("timeline_events").insert(r).execute()
            except APIError as inner:
                if not _is_unique_violation(inner):
                    raise


def list_findings(case_id: str) -> list[dict]:
    return get_client().table("findings").select("*").eq("case_id", case_id).execute().data


def get_finding(finding_id: str) -> Optional[dict]:
    rows = get_client().table("findings").select("*").eq("finding_id", finding_id).execute().data
    return rows[0] if rows else None


def update_finding(finding_id: str, patch: dict) -> Optional[dict]:
    rows = get_client().table("findings").update(patch).eq("finding_id", finding_id).execute().data
    return rows[0] if rows else None  # None when the id doesn't exist — caller maps to 404


# ------------------------- Audit log -----------------------------
def write_audit(case_id: str, actor: str, action: str, detail: dict | None = None) -> None:
    get_client().table("audit_log").insert(
        {"case_id": case_id, "actor": actor, "action": action, "detail": detail or {}}
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
