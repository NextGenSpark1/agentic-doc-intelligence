"""Tendering data-access layer — all table touches for the tendering platform."""
from __future__ import annotations

from backend.core.db_core import _is_unique_violation, get_client


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
        "readiness_score", "description", "team_members", "ai_summary",
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
    rows = (
        get_client()
        .table("workspace_documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("uploaded_at", desc=True)
        .execute()
        .data
    ) or []

    # Enrich with extraction_status / page_count from the core documents table.
    linked_ids = [row["document_id"] for row in rows if row.get("document_id")]
    if linked_ids:
        try:
            core_docs = (
                get_client()
                .table("documents")
                .select("document_id, extraction_status, page_count, storage_path")
                .in_("document_id", linked_ids)
                .execute()
                .data
            ) or []
            core_map = {doc["document_id"]: doc for doc in core_docs}
        except Exception:
            core_map = {}
        for row in rows:
            core = core_map.get(row.get("document_id", ""))
            if core:
                row["extraction_status"] = core.get("extraction_status", "uploaded")
                row["page_count"] = core.get("page_count")
            else:
                row.setdefault("extraction_status", "uploaded")

    return rows


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


def get_workspace_document(doc_id: str) -> dict | None:
    rows = (
        get_client()
        .table("workspace_documents")
        .select("*")
        .eq("id", doc_id)
        .execute()
        .data
    )
    return rows[0] if rows else None


def link_core_document_to_workspace_doc(workspace_doc_id: str, core_document_id: str) -> None:
    """Set the document_id FK on a workspace_documents row after the core doc is created."""
    get_client().table("workspace_documents").update(
        {"document_id": core_document_id}
    ).eq("id", workspace_doc_id).execute()


def delete_workspace(workspace_id: str) -> None:
    """Delete a workspace and all its child rows (documents, requirements, bid decisions)."""
    get_client().table("tender_workspaces").delete().eq("id", workspace_id).execute()


def delete_workspace_document(doc_id: str) -> None:
    """Delete workspace document row and its linked core document (chunks cascade)."""
    row = get_workspace_document(doc_id)
    if not row:
        return
    core_document_id = row.get("document_id")
    get_client().table("workspace_documents").delete().eq("id", doc_id).execute()
    if core_document_id:
        from backend.core import db_core as _core
        core_doc = _core.get_document(core_document_id)
        if core_doc:
            _core.delete_document(core_document_id, core_doc.get("storage_path", ""))


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


def delete_library_document(doc_id: str) -> None:
    """Delete a library document and every vault row derived from it.

    `supplier_documents.library_doc_id` is a plain TEXT column with no foreign key, so the
    database will not cascade. Without this, deleting a document from the library left its
    vault chunks in `match_supplier_chunks` — a document the user removed could still be
    proposed as bid evidence, citing a library_doc_id the UI can no longer resolve.

    Vault rows are deleted before the library row so a failure part-way through leaves the
    library entry visible (and retryable) rather than leaving orphaned, still-searchable
    evidence behind. Chunks are deleted explicitly rather than relying on a cascade from
    `supplier_documents`, because these two tables have no committed DDL and the constraint
    cannot be verified from the repo.
    """
    client = get_client()
    supplier_docs = (
        client.table("supplier_documents")
        .select("supplier_document_id")
        .eq("library_doc_id", str(doc_id))
        .execute()
        .data
    ) or []

    for supplier_doc in supplier_docs:
        supplier_document_id = supplier_doc["supplier_document_id"]
        client.table("supplier_document_chunks").delete().eq(
            "supplier_document_id", supplier_document_id
        ).execute()
        client.table("supplier_documents").delete().eq(
            "supplier_document_id", supplier_document_id
        ).execute()

    client.table("library_documents").delete().eq("doc_id", doc_id).execute()


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
    docs = (
        get_client()
        .table("library_documents")
        .select("*")
        .eq("org_id", org_id)
        .order("uploaded_at", desc=True)
        .execute()
        .data
    ) or []
    if not docs:
        return docs
    doc_ids = [str(doc["doc_id"]) for doc in docs]
    try:
        supplier_rows = (
            get_client()
            .table("supplier_documents")
            .select("library_doc_id, supplier_document_id, extraction_status")
            .in_("library_doc_id", doc_ids)
            .execute()
            .data
        ) or []
        supplier_map = {str(row["library_doc_id"]): row for row in supplier_rows}
    except Exception:
        supplier_map = {}
    for doc in docs:
        supplier = supplier_map.get(str(doc["doc_id"]))
        doc["extraction_status"] = supplier["extraction_status"] if supplier else None
    return docs


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


def match_workspace_chunks(workspace_id: str, query_embedding: list[float], top_k: int = 8) -> list[dict]:
    return (
        get_client()
        .rpc("match_workspace_chunks", {
            "p_workspace_id": workspace_id,
            "p_query_embedding": query_embedding,
            "p_match_count": top_k,
        })
        .execute()
        .data
    ) or []


_DELETE_BATCH = 100  # keeps the IN (...) list well inside PostgREST's URL-length limit


def delete_workspace_requirements(workspace_id: str, pending_only: bool = False) -> None:
    """Delete requirements for a workspace.

    With pending_only, deletes only requirements nobody has worked on yet, so re-running
    analysis can refresh them. A requirement counts as worked on if its status is no longer
    'unchecked', or if a person has given it an owner, written notes, or confirmed or dismissed
    evidence for it. Those are kept.

    "Status is unchecked" alone used to be the test, which deleted an unchecked requirement's
    owner and notes on every run — and, since evidence_links cascade on delete, would also
    erase any evidence a person had confirmed for it.
    """
    client = get_client()
    if not pending_only:
        client.table("workspace_requirements").delete().eq("workspace_id", workspace_id).execute()
        return

    unchecked = (
        client.table("workspace_requirements")
        .select("req_id, owner, notes")
        .eq("workspace_id", workspace_id)
        .eq("status", "unchecked")
        .execute()
        .data
    ) or []
    if not unchecked:
        return

    reviewed_evidence = (
        client.table("evidence_links")
        .select("req_id")
        .eq("workspace_id", workspace_id)
        .in_("human_review_status", ["confirmed", "dismissed"])
        .execute()
        .data
    ) or []
    has_reviewed_evidence = {str(link["req_id"]) for link in reviewed_evidence}

    deletable = [
        str(requirement["req_id"])
        for requirement in unchecked
        if not (requirement.get("owner") or "").strip()
        and not (requirement.get("notes") or "").strip()
        and str(requirement["req_id"]) not in has_reviewed_evidence
    ]
    for start in range(0, len(deletable), _DELETE_BATCH):
        client.table("workspace_requirements").delete().in_(
            "req_id", deletable[start:start + _DELETE_BATCH]
        ).execute()


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
    """Save an AI evidence proposal without ever overwriting a person's decision.

    One row per (req_id, doc_id). If a row already exists:
      * still pending         -> refresh the AI's fields (score, rationale, matched chunk)
      * confirmed / dismissed -> left untouched, because a person has already decided

    Returns the row written, or None when an existing row was left unchanged.

    This used to be a plain upsert carrying human_review_status="pending", so every analysis
    run would have reset a confirmed or dismissed link back to pending. It also caught every
    exception and returned None, so a broken insert was counted as "skipped" and looked the
    same as "no matches". Database errors now propagate and the caller reports them.
    """
    client = get_client()
    existing = (
        client.table("evidence_links")
        .select("id, human_review_status")
        .eq("req_id", data["req_id"])
        .eq("doc_id", data["doc_id"])
        .limit(1)
        .execute()
        .data
    )
    if existing:
        if existing[0].get("human_review_status") != "pending":
            return None
        refresh = {key: data[key] for key in ("score", "rationale", "matched_chunk_id") if key in data}
        rows = (
            client.table("evidence_links")
            .update(refresh)
            .eq("id", existing[0]["id"])
            .execute()
            .data
        )
        return rows[0] if rows else None
    try:
        return client.table("evidence_links").insert(data).execute().data[0]
    except Exception as err:
        if _is_unique_violation(err):
            return None  # a concurrent run inserted this pair first; its row stands
        raise


def write_workspace_audit(workspace_id: str, actor: str, action: str, detail: dict | None = None) -> None:
    """Audit a workspace action.

    A thin alias over core's `write_audit` that fills the workspace column instead of the case
    one, so tendering code never has to remember which keyword to pass — and every audit row
    in both products still goes through one helper.
    """
    from backend.core.db_core import write_audit as _write_audit

    _write_audit(None, actor, action, detail, workspace_id=workspace_id)


def get_extraction_by_document(document_id: str) -> dict | None:
    from backend.core.db_core import get_extraction_by_document as _core_get
    return _core_get(document_id)


def list_chunks(document_id: str) -> list[dict]:
    from backend.core.db_core import list_chunks as _core_list
    return _core_list(document_id)


# ─────────────────────── Vault (supplier document store) ─────────────────────

def create_supplier_document(org_id: str, data: dict) -> dict:
    import uuid as _uuid
    row = (
        get_client()
        .table("supplier_documents")
        .insert({
            "supplier_document_id": str(_uuid.uuid4()),
            "org_id": org_id,
            "title": data.get("title", ""),
            "doc_type": data.get("doc_type") or data.get("category") or "other",
            "storage_path": data.get("storage_path", ""),
            "filename": data.get("filename", ""),
            "issued_date": data.get("issued_date") or data.get("issue_date"),
            "expiry_date": data.get("expiry_date"),
            "version": data.get("version", 1),
            "library_doc_id": data.get("library_doc_id"),
            "extraction_status": "uploaded",
        })
        .execute()
        .data
    )
    return row[0]


def get_supplier_document_by_library_doc(library_doc_id: str) -> dict | None:
    rows = (
        get_client()
        .table("supplier_documents")
        .select("*")
        .eq("library_doc_id", library_doc_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def get_supplier_document(supplier_document_id: str) -> dict | None:
    rows = (
        get_client()
        .table("supplier_documents")
        .select("*")
        .eq("supplier_document_id", supplier_document_id)
        .execute()
        .data
    )
    return rows[0] if rows else None


def update_supplier_document(supplier_document_id: str, patch: dict) -> dict | None:
    row = (
        get_client()
        .table("supplier_documents")
        .update(patch)
        .eq("supplier_document_id", supplier_document_id)
        .execute()
        .data
    )
    return row[0] if row else None


def match_supplier_docs(org_id: str, query_embedding: list[float], top_k: int = 12) -> list[dict]:
    return (
        get_client()
        .rpc("match_supplier_chunks", {
            "p_org_id": org_id,
            "p_query_embedding": query_embedding,
            "p_match_count": top_k,
        })
        .execute()
        .data
    ) or []


def insert_supplier_chunks(rows: list[dict]) -> None:
    if not rows:
        return
    get_client().table("supplier_document_chunks").insert(rows).execute()


def delete_supplier_chunks(supplier_document_id: str) -> None:
    """Remove every indexed chunk for one vault document, ahead of a re-index."""
    get_client().table("supplier_document_chunks").delete().eq(
        "supplier_document_id", supplier_document_id
    ).execute()
