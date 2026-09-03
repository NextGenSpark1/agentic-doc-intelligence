"""Investigation product routes — findings, entities, timeline, report, review, chat.

Mounted on the core app (`backend.core.main`) with the same URL paths as before the core/apps
split, so the deployed frontend is unaffected. Case access is enforced via core's
`load_case_or_403`; everything domain-specific (findings/entities/relationships/timeline) is
read through the investigation `db` facade.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel

from shared.schemas import ChatRequest, ChatResponse, CitationSchema  # platform contract

from backend.core import llm, retrieval
from backend.core.access import load_case_or_403 as _load_case_or_403
from backend.core.auth import get_current_user
from backend.core.config import get_settings
from backend.core.text_utils import keyword_or_filter as _keyword_or_filter, strip_html as _strip_html
from . import db, pipeline

router = APIRouter()


# ------------------------- request models -------------------------
class FindingReview(BaseModel):
    status: str  # "confirmed" | "dismissed"
    reviewed_by: str
    dismissal_reason: str | None = None


class ReportRequest(BaseModel):
    sections: list[str] = ["Executive Summary", "Background", "Key Findings", "Risk Assessment", "Recommendations"]
    instructions: str = ""


class TimelineEventCreate(BaseModel):
    event_date: str
    label: str
    document_id: str | None = None


class TimelineEventPatch(BaseModel):
    event_date: str | None = None
    label: str | None = None
    document_id: str | None = None


# ------------------------- case analysis --------------------------
@router.post("/cases/{case_id}/analysis", status_code=202)
async def run_analysis(case_id: str, background: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Trigger the agentic layer (Phase 4) across all extracted documents."""
    await _load_case_or_403(case_id, user)
    await asyncio.to_thread(db.update_case, case_id, {"updated_at": datetime.now(timezone.utc).isoformat()})
    background.add_task(pipeline.run_case_analysis, case_id)
    return {"status": "analysis_started", "case_id": case_id}


@router.get("/cases/{case_id}/entities")
async def get_entities(case_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    return {
        "entities": await asyncio.to_thread(db.list_entities, case_id),
        "relationships": await asyncio.to_thread(db.list_relationships, case_id),
    }


@router.get("/cases/{case_id}/timeline")
async def get_timeline(case_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    rows = await asyncio.to_thread(
        lambda: db.get_client().table("timeline_events").select("*")
        .eq("case_id", case_id).order("event_date").execute().data
    )
    return {"events": rows}


@router.post("/cases/{case_id}/timeline", status_code=201)
async def create_timeline_event(case_id: str, body: TimelineEventCreate, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    record = {
        "event_id": str(uuid.uuid4()),
        "case_id": case_id,
        "event_date": body.event_date,
        "label": body.label,
        "document_id": body.document_id,
        "source": "manual",
        "reasoning": None,
    }
    return await asyncio.to_thread(db.insert_timeline_event, record)


@router.patch("/cases/{case_id}/timeline/{event_id}")
async def update_timeline_event(case_id: str, event_id: str, body: TimelineEventPatch, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(400, "no fields to update")
    return await asyncio.to_thread(db.update_timeline_event, event_id, patch)


@router.delete("/cases/{case_id}/timeline/{event_id}", status_code=204)
async def delete_timeline_event(case_id: str, event_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    await asyncio.to_thread(db.delete_timeline_event, event_id)


@router.get("/cases/{case_id}/findings")
async def get_findings(case_id: str, user: dict = Depends(get_current_user)):
    await _load_case_or_403(case_id, user)
    return {"findings": await asyncio.to_thread(db.list_findings, case_id)}


@router.post("/cases/{case_id}/report")
async def generate_report(
    case_id: str,
    user: dict = Depends(get_current_user),
    body: ReportRequest = Body(default=None),
):
    """Generate a markdown investigation report from confirmed findings."""
    if body is None:
        body = ReportRequest()
    case = await _load_case_or_403(case_id, user)

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


@router.patch("/findings/{finding_id}/review")
async def review_finding(finding_id: str, body: FindingReview, user: dict = Depends(get_current_user)):
    """Phase 5 — human-in-the-loop. Investigator confirms or dismisses a finding."""
    if body.status not in ("confirmed", "dismissed", "pending"):
        raise HTTPException(400, "status must be 'confirmed', 'dismissed', or 'pending'")
    existing = await asyncio.to_thread(db.get_finding, finding_id)
    if not existing:
        raise HTTPException(404, "finding not found")
    # Enforce case access — this route isn't case-scoped in its path, so without this any user
    # could review another org's findings by finding_id.
    await _load_case_or_403(existing["case_id"], user)
    patch = {
        "human_review_status": body.status,
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "dismissal_reason": body.dismissal_reason,
    }
    updated = await asyncio.to_thread(db.update_finding, finding_id, patch)
    if not updated:
        raise HTTPException(404, "finding not found")
    case_id = updated.get("case_id", "unknown")
    await asyncio.to_thread(db.update_case, case_id, {"updated_at": datetime.now(timezone.utc).isoformat()})
    if body.status != "pending":
        await asyncio.to_thread(db.write_audit, case_id, body.reviewed_by, f"finding_{body.status}", {
            "finding_id": finding_id,
            "dismissal_reason": body.dismissal_reason,
        })
    return updated


# ------------------------------ chat (RAG) ------------------------
def _retrieve_chunks(case_id: str, question: str, query_vec: list[float], settings) -> list[dict]:
    """Retrieve context chunks, degrading rather than failing.

    Hybrid (dense + keyword, RRF-fused) when enabled; pure dense otherwise. A hybrid failure
    — most likely the match_chunks_candidates migration not having been run — must not take
    chat down, so it is logged to the audit trail and retrieval falls back to dense. That
    mirrors how the pipeline treats a failing LLM tier: degrade visibly, never silently.
    """
    if settings.rag_hybrid_enabled:
        try:
            return retrieval.hybrid_search(
                case_id=case_id,
                query_text=question,
                query_embedding=query_vec,
                top_k=settings.rag_top_k,
                pool=settings.rag_hybrid_pool,
                rrf_k=settings.rag_rrf_k,
                dense_weight=settings.rag_dense_weight,
                keyword_weight=settings.rag_keyword_weight,
            )
        except Exception as exc:
            try:
                db.write_audit(case_id, "system", "hybrid_retrieval_failed",
                               {"error": f"{type(exc).__name__}: {exc}"})
            except Exception:
                pass  # never let audit logging break the request path
    return db.match_chunks(case_id, query_vec, settings.rag_top_k)


@router.post("/cases/{case_id}/chat", response_model=ChatResponse)
async def chat(case_id: str, body: ChatRequest, user: dict = Depends(get_current_user)):
    """Grounded Q&A over a case's documents. Retrieved chunks become the citations,
    each carrying the page + bbox from ADE's visual grounding."""
    await _load_case_or_403(case_id, user)
    settings = get_settings()

    # 1. Retrieve relevant chunks (hybrid or dense; literal keyword scan as last resort)
    try:
        query_vec = llm.embed([body.message])[0]
        chunks = await asyncio.to_thread(
            _retrieve_chunks, case_id, body.message, query_vec, settings
        )
    except Exception:
        # Vector search unavailable — fall back to matching any salient word from the question.
        keyword_filter = _keyword_or_filter(body.message)

        def _keyword_search():
            q = db.get_client().table("chunks").select("*").eq("case_id", case_id)
            q = q.or_(keyword_filter) if keyword_filter else q.ilike("text", f"%{body.message[:40]}%")
            return q.limit(settings.rag_top_k).execute().data

        chunks = await asyncio.to_thread(_keyword_search)

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
