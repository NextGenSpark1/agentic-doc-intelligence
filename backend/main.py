"""Investigation Intelligence API. 

Pipeline stages:  classify -> extract -> resolve_entities -> build_relationships
                  -> reconstruct_timeline -> detect_anomalies -> summarise

Run from the repo root so `shared` is importable:
    uvicorn backend.main:app --reload
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.schemas import ChatRequest, ChatResponse, CitationSchema  # platform contract

from . import db, llm, pipeline
from .config import get_settings

app = FastAPI(title="Investigation Intelligence API", version="0.1.0")

# Dashboard calls the API server-side, so CORS isn't strictly required, but this keeps
# local browser tools working. Tighten allow_origins before any real deployment.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ------------------------- request models -------------------------
class CaseCreate(BaseModel):
    title: str
    case_type: str
    lead_investigator: str
    allegation_summary: str = ""


class FindingReview(BaseModel):
    status: str  # "confirmed" | "dismissed"
    reviewed_by: str
    dismissal_reason: str | None = None


# ------------------------------ health ----------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": app.title, "version": app.version}


# ------------------------------ cases -----------------------------
@app.post("/cases", status_code=201)
async def create_case(body: CaseCreate):
    case_id = f"INV-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"
    record = {
        "case_id": case_id,
        "title": body.title,
        "case_type": body.case_type,
        "status": "Intake",
        "lead_investigator": body.lead_investigator,
        "allegation_summary": body.allegation_summary,
        "risk_score": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    created = await asyncio.to_thread(db.insert_case, record)
    await asyncio.to_thread(db.write_audit, case_id, body.lead_investigator, "case_created", {})
    return created


@app.get("/cases")
async def list_cases():
    cases = await asyncio.to_thread(db.list_cases)
    # Stats for the Cases page header cards
    docs_total = 0
    pending = 0
    for c in cases:
        findings = await asyncio.to_thread(db.list_findings, c["case_id"])
        pending += sum(1 for f in findings if f.get("human_review_status") == "pending")
    return {"cases": cases, "stats": {"open_cases": len(cases), "findings_pending_review": pending}}


@app.get("/cases/{case_id}")
async def get_case(case_id: str):
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    return case


# ---------------------------- documents ---------------------------
@app.post("/cases/{case_id}/documents", status_code=202)
async def upload_document(case_id: str, background: BackgroundTasks, file: UploadFile = File(...)):
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")

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
        "extraction_status": "queued",
        "page_count": 0,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    created = await asyncio.to_thread(db.insert_document, record)

    # Phase 1 -> kick off Phases 2-3 in the background; respond immediately.
    background.add_task(pipeline.process_document, document_id)
    return created


@app.get("/cases/{case_id}/documents")
async def list_documents(case_id: str):
    return {"documents": await asyncio.to_thread(db.list_documents, case_id)}


# ------------------------- case analysis --------------------------
@app.post("/cases/{case_id}/analysis", status_code=202)
async def run_analysis(case_id: str, background: BackgroundTasks):
    """Trigger the agentic layer (Phase 4) across all extracted documents."""
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    background.add_task(pipeline.run_case_analysis, case_id)
    return {"status": "analysis_started", "case_id": case_id}


@app.get("/cases/{case_id}/entities")
async def get_entities(case_id: str):
    return {
        "entities": await asyncio.to_thread(db.list_entities, case_id),
        "relationships": await asyncio.to_thread(db.list_relationships, case_id),
    }


@app.get("/cases/{case_id}/timeline")
async def get_timeline(case_id: str):
    rows = await asyncio.to_thread(
        lambda: db.get_client().table("timeline_events").select("*")
        .eq("case_id", case_id).order("event_date").execute().data
    )
    return {"events": rows}


@app.get("/cases/{case_id}/findings")
async def get_findings(case_id: str):
    return {"findings": await asyncio.to_thread(db.list_findings, case_id)}


@app.patch("/findings/{finding_id}/review")
async def review_finding(finding_id: str, body: FindingReview):
    """Phase 5 — human-in-the-loop. Investigator confirms or dismisses a finding."""
    if body.status not in ("confirmed", "dismissed"):
        raise HTTPException(400, "status must be 'confirmed' or 'dismissed'")
    patch = {
        "human_review_status": body.status,
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "dismissal_reason": body.dismissal_reason,
    }
    updated = await asyncio.to_thread(db.update_finding, finding_id, patch)
    return updated


# ------------------------------ chat (RAG) ------------------------
@app.post("/cases/{case_id}/chat", response_model=ChatResponse)
async def chat(case_id: str, body: ChatRequest):
    """Grounded Q&A over a case's documents. Retrieved chunks become the citations,
    each carrying the page + bbox from ADE's visual grounding."""
    settings = get_settings()

    # 1. Retrieve relevant chunks (vector search; keyword fallback)
    try:
        query_vec = llm.embed([body.message])[0]
        chunks = await asyncio.to_thread(
            db.match_chunks, case_id, query_vec, settings.rag_top_k
        )
    except Exception:
        chunks = await asyncio.to_thread(
            lambda: db.get_client().table("chunks").select("*")
            .eq("case_id", case_id).ilike("text", f"%{body.message[:40]}%")
            .limit(settings.rag_top_k).execute().data
        )

    if not chunks:
        return ChatResponse(answer="I couldn't find anything relevant in this case's documents yet.",
                            citations=[])

    # 2. Build grounded context and answer
    context = "\n\n".join(f"[{i+1}] {c['text']}" for i, c in enumerate(chunks))
    try:
        answer = llm.complete(
            tier="reasoning",
            messages=[
                {"role": "system", "content":
                    "Answer the investigator's question using ONLY the numbered context. "
                    "Cite sources inline as [n]. If the answer isn't in the context, say so."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {body.message}"},
            ],
        )
    except Exception:
        answer = "LLM is not configured; showing the most relevant passages instead."

    citations = [
        CitationSchema(
            document_id=c.get("document_id", ""),
            page=c.get("page") or 0,
            bbox=c.get("bbox") or [0, 0, 0, 0],
            quoted_text=(c.get("text") or "")[:240],
            chunk_id=c.get("chunk_id", ""),
        )
        for c in chunks
    ]
    return ChatResponse(answer=answer, citations=citations)
