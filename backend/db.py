"""Supabase data-access layer.

Every table touch goes through here so the rest of the codebase never builds raw
queries inline. supabase-py v2 is synchronous; we therefore keep these helpers sync
and call them from async endpoints via `asyncio.to_thread`, and run the pipeline in a
FastAPI BackgroundTask (which executes sync work in a threadpool). That keeps the event
loop unblocked without dragging in an async DB driver for the MVP.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from supabase import Client, create_client

from .config import get_settings


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


def list_cases() -> list[dict]:
    return get_client().table("cases").select("*").order("created_at", desc=True).execute().data


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


# -------------------------- Extractions --------------------------
def insert_extraction(data: dict) -> dict:
    return get_client().table("extractions").insert(data).execute().data[0]


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


def match_chunks(case_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    """Vector similarity search via a Postgres RPC (see schema.sql -> match_chunks)."""
    return get_client().rpc(
        "match_chunks",
        {"p_case_id": case_id, "p_query_embedding": query_embedding, "p_match_count": top_k},
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
def insert_relationship(data: dict) -> dict:
    return get_client().table("relationships").insert(data).execute().data[0]


def list_relationships(case_id: str) -> list[dict]:
    return get_client().table("relationships").select("*").eq("case_id", case_id).execute().data


# ---------------------------- Findings ---------------------------
def insert_finding(data: dict) -> dict:
    return get_client().table("findings").insert(data).execute().data[0]


def list_findings(case_id: str) -> list[dict]:
    return get_client().table("findings").select("*").eq("case_id", case_id).execute().data


def update_finding(finding_id: str, patch: dict) -> dict:
    return get_client().table("findings").update(patch).eq("finding_id", finding_id).execute().data[0]


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


def delete_document(document_id: str, storage_path: str) -> None:
    """Delete file from Storage then drop the documents row.

    Related rows (extractions, chunks) are not cascade-deleted here — add
    ON DELETE CASCADE FK constraints in schema.sql and remove this note then.
    """
    s = get_settings()
    get_client().storage.from_(s.storage_bucket).remove([storage_path])
    get_client().table("documents").delete().eq("document_id", document_id).execute()
