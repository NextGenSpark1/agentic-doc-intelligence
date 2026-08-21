"""Document Intelligence API — core app.

Owns the shared, product-agnostic surface: health, cases, documents, graph-state, orgs,
plus the case-access guard and the small text helpers reused across products. Each product
mounts its own router on top (investigation today; tendering next) — see the include_router
calls at the bottom. Route paths are unchanged from the pre-split monolith.

Run from the repo root so `shared` is importable:
    uvicorn backend.core.main:app --reload
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.core import db_core as db, llm, orgs as orgs_module
from backend.core.access import load_case_or_403 as _load_case_or_403
from backend.core.auth import get_current_user
from backend.core.config import get_settings

app = FastAPI(title="Document Intelligence API", version="0.1.0")
app.include_router(orgs_module.router)


def _fmt_field_value(v) -> str:
    """Flatten a field value to a readable string — lists become comma-separated, truncated."""
    if isinstance(v, list):
        items = [str(x).strip() for x in v if x is not None and str(x).strip()]
        if not items:
            return "—"
        joined = ", ".join(items[:5])
        return joined + (f" (+{len(items) - 5} more)" if len(items) > 5 else "")
    return str(v).strip()


def _fields_for_llm(fields: dict) -> str:
    """Produce a concise key: value block for the LLM prompt, capping long lists."""
    lines = []
    for k, v in fields.items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        if isinstance(v, list):
            items = [str(x).strip() for x in v if x is not None and str(x).strip()]
            if not items:
                continue
            # Cap at 10 items and truncate individual long strings to avoid blowing the context
            sample = [s[:120] for s in items[:10]]
            display = ", ".join(sample) + (f" … ({len(items)} total)" if len(items) > 10 else "")
        else:
            display = str(v)[:300]
        lines.append(f"{k.replace('_', ' ').title()}: {display}")
    return "\n".join(lines)


def _fallback_summary(fields: dict, schema_name: str) -> str:
    """Build a readable sentence from extracted fields when the LLM is unavailable."""
    present = {k: v for k, v in fields.items()
               if v is not None and v != "" and v != [] and v != {}}
    if not present:
        return f"Document processed as '{schema_name}'. No field data extracted."

    parts: list[str] = []
    if "vendor_name" in present:
        parts.append(f"Invoice from {present['vendor_name']}")
    if "awarded_vendor" in present:
        parts.append(f"Procurement awarded to {present['awarded_vendor']}")
    if "amount" in present:
        currency = present.get("currency", "")
        parts.append(f"for {currency} {present['amount']}".strip())
    if "payment_date" in present:
        parts.append(f"dated {present['payment_date']}")
    if "invoice_number" in present:
        parts.append(f"ref {present['invoice_number']}")
    if "tender_id" in present:
        parts.append(f"tender {present['tender_id']}")

    if parts:
        return (". ".join(parts[:3])).capitalize() + "."

    # Generic: pick 3 meaningful scalar/short fields and format them readably
    label_map = {
        "reporting_entity": "Entity", "period_covered": "Period",
        "total_assets": "Total assets", "total_liabilities": "Total liabilities",
        "net_profit": "Net profit", "revenue": "Revenue",
    }
    lines: list[str] = []
    for k, v in list(present.items()):
        label = label_map.get(k, k.replace("_", " ").title())
        lines.append(f"{label}: {_fmt_field_value(v)}")
        if len(lines) == 3:
            break
    doc_type = schema_name.replace("_", " ").title()
    return f"{doc_type}. " + ". ".join(lines) + "."


# CORS origins come from settings (CORS_ALLOW_ORIGINS env, default "*" for local dev).
# Set it to the real dashboard origin(s) before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------- request models -------------------------
class CaseCreate(BaseModel):
    title: str
    case_type: str
    lead_investigator: str
    allegation_summary: str = ""
    schema_fields: list[dict] = []


class CasePatch(BaseModel):
    title: str | None = None
    case_type: str | None = None
    status: str | None = None
    lead_investigator: str | None = None
    allegation_summary: str | None = None
    schema_fields: list[dict] | None = None


class GraphStatePayload(BaseModel):
    node_positions: dict = {}
    manual_edges: list = []


# ------------------------------ health ----------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": app.title, "version": app.version}


# ------------------------------ cases -----------------------------
@app.post("/cases", status_code=201)
async def create_case(body: CaseCreate, user: dict = Depends(get_current_user)):
    case_id = f"INV-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    org_id = membership["org_id"] if membership else None
    record = {
        "case_id": case_id,
        "title": body.title,
        "case_type": body.case_type,
        "status": "Intake",
        "lead_investigator": body.lead_investigator,
        "allegation_summary": body.allegation_summary,
        "schema_fields": body.schema_fields,
        "owner_id": user["user_id"],
        "org_id": org_id,
        "created_by": user["user_id"],
        "risk_score": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    created = await asyncio.to_thread(db.insert_case, record)
    await asyncio.to_thread(db.write_audit, case_id, body.lead_investigator, "case_created", {})
    return created


@app.get("/cases")
async def list_cases(user: dict = Depends(get_current_user)):
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    if not membership:
        cases = await asyncio.to_thread(db.list_cases, owner_id=user["user_id"])
    else:
        role = membership["role"]
        org_id = membership["org_id"]
        if role == "org_admin":
            created_by = None          # admin sees every case in the org
        elif role == "supervisor":
            created_by = user["user_id"]  # supervisor sees cases they created
        else:
            created_by = membership.get("invited_by")  # member sees their supervisor's cases
        cases = await asyncio.to_thread(db.list_cases, org_id=org_id, created_by=created_by)

    # Enrich each case concurrently with count-only queries (no rows transferred) — the old loop
    # did two serial DB round-trips per case and pulled every finding row just to count pending.
    async def enrich(c: dict) -> tuple[dict, int]:
        doc_count, pending = await asyncio.gather(
            asyncio.to_thread(db.count_documents, c["case_id"]),
            asyncio.to_thread(db.count_pending_findings, c["case_id"]),
        )
        return {**c, "doc_count": doc_count}, pending

    results = await asyncio.gather(*(enrich(c) for c in cases))
    enriched = [r[0] for r in results]
    pending = sum(r[1] for r in results)
    open_cases = sum(1 for c in enriched if c.get("status", "").lower() in ("active", "pending review"))
    return {"cases": enriched, "stats": {"open_cases": open_cases, "findings_pending_review": pending}}


@app.get("/cases/{case_id}")
async def get_case(case_id: str, user: dict = Depends(get_current_user)):
    return await _load_case_or_403(case_id, user)


@app.patch("/cases/{case_id}")
async def update_case(case_id: str, body: CasePatch, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(400, "no fields to update")
    updated = await asyncio.to_thread(db.update_case, case_id, patch)
    return updated


@app.delete("/cases/{case_id}", status_code=204)
async def delete_case(case_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    await asyncio.to_thread(db.delete_case, case_id)


@app.get("/cases/{case_id}/graph-state")
async def get_graph_state(case_id: str, user: dict = Depends(get_current_user)):
    case = await _load_case_or_403(case_id, user)
    return case.get("graph_state") or {}


@app.put("/cases/{case_id}/graph-state", status_code=204)
async def save_graph_state(case_id: str, body: GraphStatePayload, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    await asyncio.to_thread(db.update_case, case_id, {"graph_state": body.model_dump()})


# ---------------------------- documents ---------------------------
@app.post("/cases/{case_id}/documents", status_code=201)
async def upload_document(case_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    case = await _load_case_or_403(case_id, user)

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    document_id = str(uuid.uuid4())
    storage_path = f"{case_id}/{document_id}/{file.filename}"

    await asyncio.to_thread(
        db.upload_evidence, storage_path, content, file.content_type or "application/octet-stream"
    )
    record = {
        "document_id": document_id,
        "case_id": case_id,
        "filename": file.filename,
        "file_hash": file_hash,
        "storage_path": storage_path,
        "document_type": "unclassified",
        "extraction_status": "uploaded",
        "page_count": 0,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    created = await asyncio.to_thread(db.insert_document, record)

    # Auto-promote case from intake → active when the first document arrives
    case_patch: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if case.get("status", "").lower() == "intake":
        case_patch["status"] = "active"
    await asyncio.to_thread(db.update_case, case_id, case_patch)

    return created


@app.post("/cases/{case_id}/documents/{document_id}/extract", status_code=202)
async def trigger_extraction(case_id: str, document_id: str, background: BackgroundTasks, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    if doc.get("extraction_status") not in ("uploaded", "failed"):
        raise HTTPException(409, "extraction already in progress or completed")
    await asyncio.to_thread(db.update_document, document_id, {"extraction_status": "queued"})
    # Investigation's per-document pipeline (extract + classify). When Tendering lands, this
    # will dispatch by product/case_type rather than importing investigation directly.
    from backend.apps.investigation import pipeline
    background.add_task(pipeline.process_document, document_id)
    return {"status": "queued", "document_id": document_id}


@app.get("/cases/{case_id}/documents")
async def list_documents(case_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    return {"documents": await asyncio.to_thread(db.list_documents, case_id)}


@app.delete("/cases/{case_id}/documents/{document_id}", status_code=204)
async def delete_document(case_id: str, document_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    await asyncio.to_thread(db.delete_document, document_id, doc["storage_path"])


@app.get("/cases/{case_id}/documents/{document_id}/extraction")
async def get_document_extraction(case_id: str, document_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    extraction = await asyncio.to_thread(db.get_extraction_by_document, document_id)
    if not extraction:
        raise HTTPException(404, "no extraction available for this document")
    raw_text = await asyncio.to_thread(db.get_document_raw_text, document_id)
    return {
        "extraction_id": extraction["extraction_id"],
        "document_id": extraction["document_id"],
        "schema_name": extraction["schema_name"],
        "extracted_json": extraction.get("extracted_json") or {},
        "visual_grounding_json": extraction.get("visual_grounding_json") or {},
        "extracted_at": extraction["extracted_at"],
        "raw_text": raw_text,
    }


@app.get("/cases/{case_id}/documents/{document_id}/summary")
async def get_document_summary(case_id: str, document_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    extraction = await asyncio.to_thread(db.get_extraction_by_document, document_id)
    if not extraction:
        raise HTTPException(404, "no extraction available for this document")

    # Return cached summary — regenerate if it's stale (old fallback or old preamble format)
    cached = extraction.get("summary") or ""
    _stale = (
        cached.startswith("Extracted ")
        or bool(re.match(r"here(?:'s| is)(?: a)? (?:summary|brief)", cached, re.IGNORECASE))
    )
    if cached and not _stale:
        return {"summary": cached}

    fields = extraction.get("extracted_json") or {}
    schema_name = extraction.get("schema_name", "")
    fields_text = _fields_for_llm(fields)

    try:
        summary = llm.complete(
            tier="fast",
            messages=[
                {"role": "system", "content": (
                    "You are assisting a forensic investigator. Write a concise 2-3 sentence "
                    "factual summary of the document using only the extracted fields provided. "
                    "Start directly with the facts — no preamble, no 'Here is a summary', "
                    "no meta-commentary. Include key names, amounts, dates, and identifiers."
                )},
                {"role": "user", "content": f"Document type: {schema_name}\n\nExtracted fields:\n{fields_text}"},
            ],
        )
        # Strip any LLM preamble the model still produces despite instructions
        summary = re.sub(
            r"^(?:here(?:'s| is)(?: a)? (?:summary|brief summary)[^:]*:\s*|summary:\s*)",
            "", summary, flags=re.IGNORECASE,
        ).strip()
    except Exception:
        summary = _fallback_summary(fields, schema_name)

    # Cache — wrapped so a missing 'summary' column doesn't break the response
    try:
        await asyncio.to_thread(db.update_extraction, extraction["extraction_id"], {"summary": summary})
    except Exception:
        pass

    return {"summary": summary}


@app.get("/cases/{case_id}/documents/{document_id}/file-url")
async def get_document_file_url(case_id: str, document_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    url = await asyncio.to_thread(db.signed_url, doc["storage_path"])
    if not url:
        raise HTTPException(
            500,
            "could not generate signed URL — verify storage_bucket config and Supabase storage permissions",
        )
    return {"url": url}


@app.get("/cases/{case_id}/documents/{document_id}/chunks")
async def get_document_chunks(case_id: str, document_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    chunks = await asyncio.to_thread(db.list_chunks, document_id)
    return {"chunks": [{"chunk_id": c["chunk_id"], "text": c["text"], "type": c.get("type") or "text", "page": c["page"], "bbox": c["bbox"] or []} for c in chunks]}


# ------------------- product routers (mounted last) -------------------
# Same URL paths as before the core/apps split — the deployed frontend is unaffected.
from backend.apps.investigation.routes import router as investigation_router  # noqa: E402

app.include_router(investigation_router)
