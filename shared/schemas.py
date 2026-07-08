from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class CaseSchema(BaseModel):
    case_id: str
    title: str
    case_type: str
    status: str
    lead_investigator: str
    allegation_summary: str
    risk_score: float
    created_at: datetime


class DocumentSchema(BaseModel):
    document_id: str
    case_id: str
    filename: str
    file_hash: str
    storage_path: str
    document_type: str
    extraction_status: str
    page_count: int
    uploaded_at: datetime


class ExtractionSchema(BaseModel):
    extraction_id: str
    document_id: str
    schema_name: str
    extracted_json: dict[str, Any]
    visual_grounding_json: dict[str, Any]
    extracted_at: datetime


class CitationSchema(BaseModel):
    document_id: str
    page: int
    bbox: list[float]  # [x1, y1, x2, y2] — ADE returns normalised floats 0–1
    quoted_text: str
    chunk_id: str


class ChatRequest(BaseModel):
    message: str
    scope: Literal["case", "document"]
    context_id: str
    history: list[dict[str, Any]] = []


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationSchema] = []


class FindingSchema(BaseModel):
    finding_id: str
    case_id: str
    finding_type: str
    severity: str
    confidence: float
    statement: str
    supporting_document_ids: list[str]
    human_review_status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    dismissal_reason: Optional[str] = None


class EntitySchema(BaseModel):
    entity_id: str
    case_id: str
    entity_type: str
    canonical_name: str
    aliases: list[str] = []
    confidence_score: float
