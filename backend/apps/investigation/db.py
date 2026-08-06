"""Investigation-specific data access — findings, entities, relationships, timeline.

The generic tables (cases, documents, chunks, orgs, storage, audit) live in
`backend.core.db_core`; this module owns only the investigation-domain tables. The shared
connection and dedup helpers are imported from core so there is one client and one hash formula.
"""
from __future__ import annotations

from typing import Optional

from backend.core.db_core import _content_hash, _is_unique_violation, get_client
# Re-export the generic (core) data-access functions so investigation code can use a single
# `db` facade — `from backend.apps.investigation import db` then exposes both core and
# investigation-domain queries. New generic helpers added to core are picked up automatically.
from backend.core.db_core import *  # noqa: F401,F403

try:  # import path differs slightly across supabase-py / postgrest versions
    from postgrest.exceptions import APIError
except Exception:  # pragma: no cover - fall back to a broad catch if the path moves
    APIError = Exception  # type: ignore[assignment, misc]


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


def list_findings(case_id: str) -> list[dict]:
    return get_client().table("findings").select("*").eq("case_id", case_id).execute().data


def get_finding(finding_id: str) -> Optional[dict]:
    rows = get_client().table("findings").select("*").eq("finding_id", finding_id).execute().data
    return rows[0] if rows else None


def update_finding(finding_id: str, patch: dict) -> Optional[dict]:
    rows = get_client().table("findings").update(patch).eq("finding_id", finding_id).execute().data
    return rows[0] if rows else None  # None when the id doesn't exist — caller maps to 404


# -------------------------- Timeline events ----------------------
def insert_timeline_event(data: dict) -> dict:
    """Insert a single manually-created timeline event (no content_hash dedup — user-created rows are always kept)."""
    return get_client().table("timeline_events").insert(data).execute().data[0]


def update_timeline_event(event_id: str, patch: dict) -> dict:
    return get_client().table("timeline_events").update(patch).eq("event_id", event_id).execute().data[0]


def delete_timeline_event(event_id: str) -> None:
    get_client().table("timeline_events").delete().eq("event_id", event_id).execute()


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
