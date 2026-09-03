"""Requirement extraction — RFP documents become structured workspace requirements.

Rule pass first (deterministic, always lands), then LLM pass (adds what rules miss).
Grounding guardrail: every LLM requirement must cite the chunk_id of an excerpt we
actually sent — ungrounded rows are dropped before hitting the database. Page and
source_doc come from OUR chunk row, never from the model output.

If the LLM is unavailable the rule rows still land, so a workspace never comes back
empty because Groq was having a bad afternoon.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from backend.core.text_utils import strip_html as _strip_html

_BATCH_CHAR_BUDGET = 12_000
_MAX_CHUNK_CHARS = 4_000

_OBLIGATION_RE = re.compile(
    r"\b(?:the\s+)?(?:bidder|tenderer|contractor|supplier|applicant)s?\b[^.]{0,200}?"
    r"\b(?:shall|must|is\s+required\s+to|are\s+required\s+to)\b",
    re.IGNORECASE,
)
_MANDATORY_RE = re.compile(r"\b(?:shall|must|mandatory|is\s+required|are\s+required)\b", re.IGNORECASE)

_CATEGORY_HINTS = (
    ("certification", ("licence", "license", "certificate", "certification", "registration",
                       "accreditation", "iso ", "cidb", "ssm")),
    ("financial",     ("bond", "guarantee", "turnover", "audited", "financial statement", "insurance",
                       "net worth", "credit", "bank")),
    ("legal",         ("comply", "compliance", "law", "act ", "regulation", "statutory", "clause",
                       "terms and conditions", "liability")),
    ("technical",     ("specification", "technical", "standard", "capacity", "experience", "personnel",
                       "equipment", "methodology")),
)

# His schema allowed submission_instruction / evaluation_criterion — map to our CHECK constraint.
_CATEGORY_NORMALISE = {
    "submission_instruction": "other",
    "evaluation_criterion": "other",
}
_VALID_CATEGORIES = {"technical", "financial", "legal", "experience", "personnel", "certification", "other"}


def _categorise(text: str) -> str:
    lowered = text.lower()
    for category, hints in _CATEGORY_HINTS:
        if any(h in lowered for h in hints):
            return category
    return "other"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+|\n{2,}", text)
    return [part.strip() for part in parts if part.strip()]


def compute_rule_requirements(chunks: list[dict]) -> list[dict]:
    """Deterministic pass — pure, no DB, no LLM, unit-testable."""
    out: list[dict] = []
    for chunk in chunks:
        text = _strip_html(chunk.get("text") or "")
        if not text.strip():
            continue
        for sentence in _sentences(text):
            if len(sentence) < 20 or len(sentence) > 600:
                continue
            if not _OBLIGATION_RE.search(sentence):
                continue
            out.append({
                "description": sentence,
                "category": _categorise(sentence),
                "mandatory": bool(_MANDATORY_RE.search(sentence)),
                "required_evidence": "",
                "source_doc": chunk.get("document_id", ""),
                "source_page": chunk.get("page"),
                "clause": "",
                "source_text": sentence,
                "confidence": 50,
                "source": "rule",
            })
    return out


def _batch(chunks: list[dict]) -> list[list[dict]]:
    batches: list[list[dict]] = []
    current: list[dict] = []
    budget = 0
    for chunk in chunks:
        size = min(len(chunk.get("text") or ""), _MAX_CHUNK_CHARS)
        if current and budget + size > _BATCH_CHAR_BUDGET:
            batches.append(current)
            current, budget = [], 0
        current.append(chunk)
        budget += size
    if current:
        batches.append(current)
    return batches


def validate_llm_requirements(raw: object, chunk_index: dict[str, dict]) -> list[dict]:
    """Keep only LLM requirements grounded in a chunk we actually sent."""
    if not isinstance(raw, dict):
        return []
    items = raw.get("requirements")
    if not isinstance(items, list):
        return []

    kept: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "").strip()
        if not description:
            continue

        chunk = chunk_index.get(str(item.get("chunk_id") or ""))
        if chunk is None:
            continue  # ungrounded — model cited an excerpt we did not send

        raw_category = str(item.get("category") or "other").strip().lower()
        category = _CATEGORY_NORMALISE.get(raw_category, raw_category)
        if category not in _VALID_CATEGORIES:
            category = "other"

        try:
            confidence_float = max(0.0, min(1.0, float(item.get("confidence", 0.6))))
        except (TypeError, ValueError):
            confidence_float = 0.6
        confidence = round(confidence_float * 100)

        source_text = str(item.get("source_text") or "").strip() or ""
        if source_text:
            haystack = _strip_html(chunk.get("text") or "").lower()
            if source_text.lower() not in haystack:
                source_text = _strip_html(chunk.get("text") or "")[:600]

        kept.append({
            "description": description,
            "category": category,
            "mandatory": bool(item.get("is_mandatory")),
            "required_evidence": str(item.get("required_evidence") or "").strip(),
            "source_doc": chunk.get("document_id", ""),
            "source_page": chunk.get("page"),
            "clause": str(item.get("source_clause") or "").strip(),
            "source_text": source_text,
            "confidence": confidence,
            "source": "llm",
        })
    return kept


def merge(rule_rows: list[dict], llm_rows: list[dict]) -> list[dict]:
    """Rule rows always stand; LLM rows duplicating one are dropped."""
    from .. import db
    seen = {db.requirement_hash(row) for row in rule_rows}
    merged = list(rule_rows)
    for row in llm_rows:
        digest = db.requirement_hash(row)
        if digest in seen:
            continue
        seen.add(digest)
        merged.append(row)
    return merged


def extract(workspace_id: str) -> dict:
    """Extract requirements from all processed documents in a workspace."""
    from backend.core import llm_reasoning
    from .. import db
    from ..prompts import REQUIREMENT_EXTRACTION

    workspace = db.get_tendering_workspace(workspace_id) or {}
    # Re-extract only what humans haven't reviewed yet.
    db.delete_workspace_requirements(workspace_id, pending_only=True)

    # Documents in the pipeline come from the core documents table linked to this workspace.
    core_documents = db.list_core_documents_for_workspace(workspace_id)

    inserted = skipped = ungrounded = 0
    rule_count = llm_count = 0

    for document in core_documents:
        if document.get("extraction_status") != "done":
            continue
        chunks = db.list_chunks(document["document_id"]) or []
        if not chunks:
            continue
        for chunk in chunks:
            chunk["document_id"] = document["document_id"]

        rule_rows = compute_rule_requirements(chunks)
        rule_count += len(rule_rows)

        llm_rows: list[dict] = []
        for batch in _batch(chunks):
            chunk_index = {str(chunk.get("chunk_id")): chunk for chunk in batch}
            payload = {
                "document_name": document.get("filename") or document.get("name"),
                "document_type": document.get("document_type"),
                "excerpts": [
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "page": chunk.get("page"),
                        "text": _strip_html(chunk.get("text") or "")[:_MAX_CHUNK_CHARS],
                    }
                    for chunk in batch
                ],
            }
            answer = llm_reasoning.ask(REQUIREMENT_EXTRACTION, payload, tender_id=workspace_id)
            if answer is None:
                continue
            validated = validate_llm_requirements(answer, chunk_index)
            raw_count = len(answer.get("requirements") or []) if isinstance(answer, dict) else 0
            ungrounded += max(0, raw_count - len(validated))
            llm_rows.extend(validated)

        llm_count += len(llm_rows)

        for row in merge(rule_rows, llm_rows):
            created = db.insert_workspace_requirement({
                **row,
                "req_id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "status": "unchecked",
                "completion_status": "not_started",
                "owner": "",
                "notes": "",
                "matched_doc_ids": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            if created is None:
                skipped += 1
            else:
                inserted += 1

    result = {
        "requirements_inserted": inserted,
        "duplicates_skipped": skipped,
        "ungrounded_dropped": ungrounded,
        "from_rules": rule_count,
        "from_llm": llm_count,
    }
    db.write_workspace_audit(workspace_id, "system", "requirements_extracted", result)
    return result
