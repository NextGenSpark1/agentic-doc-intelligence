"""Investigation Intelligence API. 

Pipeline stages:  classify -> extract -> resolve_entities -> build_relationships
                  -> reconstruct_timeline -> detect_anomalies -> summarise

Run from the repo root so `shared` is importable:
    uvicorn backend.main:app --reload
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Body, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.schemas import ChatRequest, ChatResponse, CitationSchema  # platform contract

from . import db, llm, orgs as orgs_module, pipeline
from .auth import get_current_user
from .config import get_settings

app = FastAPI(title="Investigation Intelligence API", version="0.1.0")
app.include_router(orgs_module.router)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s{2,}")


def _strip_html(text: str) -> str:
    """Remove HTML tags left by ADE and collapse whitespace."""
    cleaned = _HTML_TAG_RE.sub(" ", text or "")
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


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
    schema_fields: list[dict] = []


class CasePatch(BaseModel):
    title: str | None = None
    case_type: str | None = None
    status: str | None = None
    lead_investigator: str | None = None
    allegation_summary: str | None = None
    schema_fields: list[dict] | None = None


class FindingReview(BaseModel):
    status: str  # "confirmed" | "dismissed"
    reviewed_by: str
    dismissal_reason: str | None = None


# ------------------------------ health ----------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": app.title, "version": app.version}


# ------------------------------ cases -----------------------------
def _assert_case_access(case: dict, user_id: str, membership: dict | None = None) -> None:
    """Raise 403 if the requesting user should not access this case.

    With team isolation: org_admin sees all org cases; supervisor sees their own;
    member sees their supervisor's. Without membership (no org yet), falls back to owner_id.
    """
    if membership:
        if case.get("org_id") != membership.get("org_id"):
            raise HTTPException(403, "access denied")
        role = membership.get("role")
        if role == "org_admin":
            return
        case_creator = case.get("created_by")
        if role == "supervisor":
            if case_creator and case_creator != user_id:
                raise HTTPException(403, "access denied")
        elif role == "member":
            supervisor_id = membership.get("invited_by")
            if case_creator and case_creator != supervisor_id:
                raise HTTPException(403, "access denied")
        return
    # Legacy: no org membership yet — use owner_id isolation
    owner = case.get("owner_id")
    if owner and owner != user_id:
        raise HTTPException(403, "access denied")


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
    pending = 0
    enriched = []
    for c in cases:
        findings = await asyncio.to_thread(db.list_findings, c["case_id"])
        pending += sum(1 for f in findings if f.get("human_review_status") == "pending")
        docs = await asyncio.to_thread(db.list_documents, c["case_id"])
        enriched.append({**c, "doc_count": len(docs)})
    open_cases = sum(1 for c in enriched if c.get("status", "").lower() in ("active", "pending review"))
    return {"cases": enriched, "stats": {"open_cases": open_cases, "findings_pending_review": pending}}


@app.get("/cases/{case_id}")
async def get_case(case_id: str, user: dict = Depends(get_current_user)):
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    _assert_case_access(case, user["user_id"], membership)
    return case


@app.patch("/cases/{case_id}")
async def update_case(case_id: str, body: CasePatch, user: dict = Depends(get_current_user)):
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    _assert_case_access(case, user["user_id"], membership)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(400, "no fields to update")
    updated = await asyncio.to_thread(db.update_case, case_id, patch)
    return updated


@app.delete("/cases/{case_id}", status_code=204)
async def delete_case(case_id: str, user: dict = Depends(get_current_user)):
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    _assert_case_access(case, user["user_id"], membership)
    await asyncio.to_thread(db.delete_case, case_id)


class GraphStatePayload(BaseModel):
    node_positions: dict = {}
    manual_edges: list = []


class ReportRequest(BaseModel):
    sections: list[str] = ["Executive Summary", "Background", "Key Findings", "Risk Assessment", "Recommendations"]
    instructions: str = ""


@app.get("/cases/{case_id}/graph-state")
async def get_graph_state(case_id: str, user: dict = Depends(get_current_user)):
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    _assert_case_access(case, user["user_id"], membership)
    return case.get("graph_state") or {}


@app.put("/cases/{case_id}/graph-state", status_code=204)
async def save_graph_state(case_id: str, body: GraphStatePayload, user: dict = Depends(get_current_user)):
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    _assert_case_access(case, user["user_id"], membership)
    await asyncio.to_thread(db.update_case, case_id, {"graph_state": body.model_dump()})


# ---------------------------- documents ---------------------------
@app.post("/cases/{case_id}/documents", status_code=201)
async def upload_document(case_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
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
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    if doc.get("extraction_status") not in ("uploaded", "failed"):
        raise HTTPException(409, "extraction already in progress or completed")
    await asyncio.to_thread(db.update_document, document_id, {"extraction_status": "queued"})
    background.add_task(pipeline.process_document, document_id)
    return {"status": "queued", "document_id": document_id}


@app.get("/cases/{case_id}/documents")
async def list_documents(case_id: str, user: dict = Depends(get_current_user)):
    return {"documents": await asyncio.to_thread(db.list_documents, case_id)}


@app.delete("/cases/{case_id}/documents/{document_id}", status_code=204)
async def delete_document(case_id: str, document_id: str, user: dict = Depends(get_current_user)):
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    await asyncio.to_thread(db.delete_document, document_id, doc["storage_path"])


@app.get("/cases/{case_id}/documents/{document_id}/extraction")
async def get_document_extraction(case_id: str, document_id: str, user: dict = Depends(get_current_user)):
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
    doc = await asyncio.to_thread(db.get_document, document_id)
    if not doc or doc.get("case_id") != case_id:
        raise HTTPException(404, "document not found")
    chunks = await asyncio.to_thread(db.list_chunks, document_id)
    return {"chunks": [{"chunk_id": c["chunk_id"], "text": c["text"], "type": c.get("type") or "text", "page": c["page"], "bbox": c["bbox"] or []} for c in chunks]}


# ------------------------- case analysis --------------------------
@app.post("/cases/{case_id}/analysis", status_code=202)
async def run_analysis(case_id: str, background: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Trigger the agentic layer (Phase 4) across all extracted documents."""
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    await asyncio.to_thread(db.update_case, case_id, {"updated_at": datetime.now(timezone.utc).isoformat()})
    background.add_task(pipeline.run_case_analysis, case_id)
    return {"status": "analysis_started", "case_id": case_id}


@app.get("/cases/{case_id}/entities")
async def get_entities(case_id: str, user: dict = Depends(get_current_user)):
    return {
        "entities": await asyncio.to_thread(db.list_entities, case_id),
        "relationships": await asyncio.to_thread(db.list_relationships, case_id),
    }


@app.get("/cases/{case_id}/timeline")
async def get_timeline(case_id: str, user: dict = Depends(get_current_user)):
    rows = await asyncio.to_thread(
        lambda: db.get_client().table("timeline_events").select("*")
        .eq("case_id", case_id).order("event_date").execute().data
    )
    return {"events": rows}


@app.get("/cases/{case_id}/findings")
async def get_findings(case_id: str, user: dict = Depends(get_current_user)):
    return {"findings": await asyncio.to_thread(db.list_findings, case_id)}


@app.post("/cases/{case_id}/report")
async def generate_report(
    case_id: str,
    user: dict = Depends(get_current_user),
    body: ReportRequest = Body(default=None),
):
    """Generate a markdown investigation report from confirmed findings."""
    if body is None:
        body = ReportRequest()
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")

    all_findings = await asyncio.to_thread(db.list_findings, case_id)
    confirmed = [f for f in all_findings if f.get("human_review_status") == "confirmed"]
    docs = await asyncio.to_thread(db.list_documents, case_id)
    doc_name_map = {d["document_id"]: d["filename"] for d in docs}

    if not confirmed:
        findings_text = "No confirmed findings available. All findings are pending review."
    else:
        lines = []
        for f in confirmed:
            doc_names = [doc_name_map.get(d, d) for d in (f.get("supporting_document_ids") or [])]
            source_note = f" [Source: {', '.join(doc_names)}]" if doc_names else ""
            lines.append(f"- [{f['severity'].upper()}] {f['statement']}{source_note}")
        findings_text = "\n".join(lines)

    sections_str = ", ".join(body.sections) if body.sections else "Executive Summary, Background, Key Findings, Risk Assessment, Recommendations"
    custom_note = f"\n\nAdditional instructions from the investigator: {body.instructions.strip()}" if body.instructions.strip() else ""

    prompt = (
        f"You are producing a formal forensic investigation report.\n\n"
        f"Case Title: {case['title']}\n"
        f"Case Type: {case['case_type']}\n"
        f"Lead Investigator: {case['lead_investigator']}\n"
        f"Allegation: {case.get('allegation_summary', 'N/A')}\n\n"
        f"Confirmed Findings (human-reviewed and approved):\n{findings_text}\n\n"
        f"Write a professional investigation report in markdown. "
        f"Include ONLY these sections (in this order): {sections_str}. "
        "Ground every statement in the confirmed findings above — do not speculate, do not add facts not present. "
        "Use professional forensic language. Be specific: include amounts, dates, entity names where available. "
        "In the Key Findings section, cite the source document name for each finding in parentheses. "
        "Do not include confidence percentages. Keep the Executive Summary to 3-4 sentences. "
        f"Recommendations should be actionable.{custom_note}"
    )

    try:
        markdown = llm.complete(
            tier="reasoning",
            messages=[
                {"role": "system", "content": "You are a senior forensic analyst producing an investigation report."},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception:
        markdown = f"""# Investigation Report — {case['title']}

## Executive Summary
This report covers case **{case['case_id']}** ({case['case_type']}).

## Confirmed Findings
{findings_text}

## Note
LLM generation failed. This is a fallback template. Configure LLM_API_KEY to enable AI-generated reports.
"""

    return {"markdown": markdown, "finding_count": len(confirmed)}


@app.patch("/findings/{finding_id}/review")
async def review_finding(finding_id: str, body: FindingReview, user: dict = Depends(get_current_user)):
    """Phase 5 — human-in-the-loop. Investigator confirms or dismisses a finding."""
    if body.status not in ("confirmed", "dismissed", "pending"):
        raise HTTPException(400, "status must be 'confirmed', 'dismissed', or 'pending'")
    patch = {
        "human_review_status": body.status,
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "dismissal_reason": body.dismissal_reason,
    }
    updated = await asyncio.to_thread(db.update_finding, finding_id, patch)
    case_id = updated.get("case_id", "unknown")
    await asyncio.to_thread(db.update_case, case_id, {"updated_at": datetime.now(timezone.utc).isoformat()})
    if body.status != "pending":
        await asyncio.to_thread(db.write_audit, case_id, body.reviewed_by, f"finding_{body.status}", {
            "finding_id": finding_id,
            "dismissal_reason": body.dismissal_reason,
        })
    return updated


# ------------------------------ chat (RAG) ------------------------
@app.post("/cases/{case_id}/chat", response_model=ChatResponse)
async def chat(case_id: str, body: ChatRequest, user: dict = Depends(get_current_user)):
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

    # 2. Build grounded context — RAG chunks + structured case intelligence
    doc_context = "\n\n".join(f"[{i+1}] {_strip_html(c['text'])}" for i, c in enumerate(chunks))

    # Load structured intelligence already built on this case
    try:
        entities = await asyncio.to_thread(db.list_entities, case_id)
        all_findings = await asyncio.to_thread(db.list_findings, case_id)
        confirmed_findings = [f for f in all_findings if f.get("human_review_status") == "confirmed"]
        relationships = await asyncio.to_thread(db.list_relationships, case_id)
    except Exception:
        entities, confirmed_findings, relationships = [], [], []

    structured_parts = []
    if entities:
        ent_lines = [f"  - {e.get('entity_type','?').upper()}: {e.get('canonical_name','')} (aliases: {', '.join(e.get('aliases') or [])})" for e in entities[:30]]
        structured_parts.append("ENTITIES IDENTIFIED IN CASE:\n" + "\n".join(ent_lines))
    if confirmed_findings:
        f_lines = [f"  - [{f.get('severity','?').upper()}] {f.get('statement','')}" for f in confirmed_findings[:20]]
        structured_parts.append("CONFIRMED FINDINGS (human-reviewed):\n" + "\n".join(f_lines))
    if relationships:
        r_lines = [f"  - {r.get('source_name','')} → {r.get('relationship_type','')} → {r.get('target_name','')}" for r in relationships[:30]]
        structured_parts.append("RELATIONSHIPS:\n" + "\n".join(r_lines))

    structured_context = "\n\n".join(structured_parts)

    # Keep last 6 history turns (3 exchanges) to stay within token limits
    recent_history = [
        {"role": m["role"], "content": str(m.get("content", ""))}
        for m in (body.history or [])[-6:]
        if m.get("role") in ("user", "assistant")
    ]
    system_prompt = (
        "You are an AI assistant for forensic investigators. "
        "You have access to two types of context: (1) relevant document excerpts retrieved for this question, "
        "and (2) structured intelligence already extracted from the full case (entities, confirmed findings, relationships). "
        "Use both to answer. Cite document excerpts inline with their number [1], [2] etc. "
        "When referencing findings or entities from the structured intelligence, say so explicitly. "
        "Be precise and factual — if something is not supported by the provided context, say so. "
        "Never speculate beyond what the evidence states.\n\n"
    )
    if structured_context:
        system_prompt += f"CASE INTELLIGENCE:\n{structured_context}\n\n"
    system_prompt += f"RELEVANT DOCUMENT EXCERPTS:\n{doc_context}"

    try:
        answer = llm.complete(
            tier="reasoning",
            messages=[
                {"role": "system", "content": system_prompt},
                *recent_history,
                {"role": "user", "content": body.message},
            ],
        )
    except Exception:
        answer = "LLM is not configured; showing the most relevant passages instead."

    citations = [
        CitationSchema(
            document_id=c.get("document_id", ""),
            page=c.get("page") or 0,
            bbox=c.get("bbox") or [0, 0, 0, 0],
            quoted_text=_strip_html(c.get("text") or "")[:240],
            chunk_id=c.get("chunk_id", ""),
        )
        for c in chunks
    ]
    return ChatResponse(answer=answer, citations=citations)
