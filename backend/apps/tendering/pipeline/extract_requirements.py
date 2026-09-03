"""Requirement extraction — one tender document becomes many structured obligations.

Follows the codebase's established discipline: **a deterministic rule pass and an LLM pass run
together, then merge.** The rule pass catches unambiguous obligation language and always
stands; the LLM pass adds the requirements that need reading comprehension; an LLM row that
duplicates a rule row is dropped in favour of the rule row. If the LLM is unavailable — bad
key, rate limit, provider down — the rule rows still land, so a tender never comes back
completely empty because Groq was having a bad afternoon.

**The grounding guardrail here is stricter than the pipeline's usual one.** `llm_reasoning.ask`
validates at document level; this validates at *chunk* level: a requirement must carry the
exact `chunk_id` of an excerpt actually sent to the model, or it is discarded before
persistence. That is what makes `source_page` trustworthy — the page is read from our chunk
row, never from anything the model said.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from backend.core.text_utils import strip_html as _strip_html

# Chunks are batched by character budget rather than count: tender chunks range from a
# one-line table cell to a full page of conditions, so a fixed count either wastes context
# or overflows it.
_BATCH_CHAR_BUDGET = 12_000
_MAX_CHUNK_CHARS = 4_000

# Rule pass. Deliberately high-precision / low-recall — it exists as a floor under an LLM
# outage, not as a competing extractor. Only unambiguous obligation language on the bidder.
_OBLIGATION_RE = re.compile(
    r"\b(?:the\s+)?(?:bidder|tenderer|contractor|supplier|applicant)s?\b[^.]{0,200}?"
    r"\b(?:shall|must|is\s+required\s+to|are\s+required\s+to)\b",
    re.IGNORECASE,
)
_MANDATORY_RE = re.compile(r"\b(?:shall|must|mandatory|is\s+required|are\s+required)\b", re.IGNORECASE)

_CATEGORY_HINTS = (
    ("certification", ("licence", "license", "certificate", "certification", "registration",
                       "accreditation", "iso ", "cidb", "ssm")),
    ("financial", ("bond", "guarantee", "turnover", "audited", "financial statement", "insurance",
                   "net worth", "credit", "bank")),
    ("submission_instruction", ("submit", "submission", "envelope", "copies", "portal", "sealed",
                                "deadline", "closing", "format", "signed")),
    ("evaluation_criterion", ("evaluat", "scoring", "score", "weightage", "weighting", "marks")),
    ("legal", ("comply", "compliance", "law", "act ", "regulation", "statutory", "clause",
               "terms and conditions", "liability")),
    ("technical", ("specification", "technical", "standard", "capacity", "experience", "personnel",
                   "equipment", "methodology")),
)


def _categorise(text: str) -> str:
    """Best-effort category for a rule-extracted requirement.

    The LLM assigns its own category; this only labels rule rows, where guessing wrong is
    cheap — a human reviews every row before it counts, and category is editable.
    """
    lowered = text.lower()
    for category, hints in _CATEGORY_HINTS:
        if any(h in lowered for h in hints):
            return category
    return "other"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+|\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def compute_rule_requirements(chunks: list[dict]) -> list[dict]:
    """Deterministic pass over a document's chunks. Pure — no DB, no LLM, unit-testable."""
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
                "is_mandatory": bool(_MANDATORY_RE.search(sentence)),
                "required_evidence": None,
                "source_document_id": chunk.get("document_id"),
                "source_page": chunk.get("page"),
                "source_clause": None,
                "source_text": sentence,
                "confidence": 0.5,   # provable language, unproven judgement
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
    """Keep only requirements grounded in an excerpt we actually sent.

    `chunk_index` maps chunk_id -> the chunk row. A returned requirement whose chunk_id is not
    in that map was not read from anything we supplied, so it is dropped — the same discipline
    the investigation stages apply to document ids, tightened to chunk level.

    Page and document id are taken from OUR chunk row, never from the model's output. The model
    identifies *which excerpt*; we decide where that excerpt lives.
    """
    if not isinstance(raw, dict):
        return []
    items = raw.get("requirements")
    if not isinstance(items, list):
        return []

    from ..schemas import REQUIREMENT_CATEGORIES

    kept: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "").strip()
        if not description:
            continue

        chunk = chunk_index.get(str(item.get("chunk_id") or ""))
        if chunk is None:
            continue  # ungrounded — the model cited an excerpt we did not send

        category = str(item.get("category") or "other").strip().lower()
        if category not in REQUIREMENT_CATEGORIES:
            category = "other"

        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.6))))
        except (TypeError, ValueError):
            confidence = 0.6

        source_text = str(item.get("source_text") or "").strip() or None
        # The model was told to copy source_text verbatim. If it is not actually present in the
        # excerpt, it was rewritten or invented — fall back to the excerpt itself rather than
        # storing a quote that does not appear in the document.
        if source_text:
            haystack = _strip_html(chunk.get("text") or "").lower()
            if source_text.lower() not in haystack:
                source_text = _strip_html(chunk.get("text") or "")[:600] or None

        kept.append({
            "description": description,
            "category": category,
            "is_mandatory": bool(item.get("is_mandatory")),
            "required_evidence": (str(item.get("required_evidence")).strip()
                                  if item.get("required_evidence") else None),
            "source_document_id": chunk.get("document_id"),
            "source_page": chunk.get("page"),
            "source_clause": (str(item.get("source_clause")).strip()
                              if item.get("source_clause") else None),
            "source_text": source_text,
            "confidence": confidence,
            "source": "llm",
        })
    return kept


def merge(rule_rows: list[dict], llm_rows: list[dict]) -> list[dict]:
    """Rule rows always stand; an LLM row duplicating one is dropped in favour of the rule row.

    Mirrors `detect_anomalies._dedupe_llm_findings` — the provable row wins, and the LLM's
    contribution is what the rules could not see.
    """
    from .. import db

    seen = {db.requirement_hash(r) for r in rule_rows}
    merged = list(rule_rows)
    for row in llm_rows:
        digest = db.requirement_hash(row)
        if digest in seen:
            continue
        seen.add(digest)
        merged.append(row)
    return merged


def extract(tender_id: str) -> dict:
    """Extract requirements for every document in a tender.

    Returns counts rather than rows — the caller is a BackgroundTask whose result is written
    to the audit log, and dumping every requirement into an audit row helps nobody.
    """
    from backend.core import llm_reasoning

    from .. import db
    from ..prompts import REQUIREMENT_EXTRACTION
    from ..schemas import RequirementRecord

    tender = db.get_tender(tender_id) or {}
    documents = db.list_tender_documents(tender_id)
    # Only re-extract what a human has not yet ruled on; confirmed and dismissed rows survive.
    db.delete_requirements(tender_id, pending_only=True)

    inserted = skipped = ungrounded = 0
    rule_count = llm_count = 0

    for document in documents:
        if document.get("extraction_status") != "done":
            continue
        chunks = db.list_chunks(document["document_id"]) or []
        if not chunks:
            continue
        # list_chunks selects no document_id column, so stamp it on for grounding lookups.
        for chunk in chunks:
            chunk["document_id"] = document["document_id"]

        rule_rows = compute_rule_requirements(chunks)
        rule_count += len(rule_rows)

        llm_rows: list[dict] = []
        for batch in _batch(chunks):
            chunk_index = {str(c.get("chunk_id")): c for c in batch}
            payload = {
                "document_name": document.get("filename"),
                "document_type": document.get("document_type"),
                "excerpts": [
                    {
                        "chunk_id": c.get("chunk_id"),
                        "page": c.get("page"),
                        "text": _strip_html(c.get("text") or "")[:_MAX_CHUNK_CHARS],
                    }
                    for c in batch
                ],
            }
            answer = llm_reasoning.ask(REQUIREMENT_EXTRACTION, payload, tender_id=tender_id)
            if answer is None:
                continue  # LLM unavailable — rule rows still stand
            validated = validate_llm_requirements(answer, chunk_index)
            raw_count = len(answer.get("requirements") or []) if isinstance(answer, dict) else 0
            ungrounded += max(0, raw_count - len(validated))
            llm_rows.extend(validated)

        llm_count += len(llm_rows)

        for row in merge(rule_rows, llm_rows):
            # RequirementRecord enforces Rule 2 before anything reaches the database.
            try:
                RequirementRecord(**row)
            except Exception:
                ungrounded += 1
                continue
            created = db.insert_requirement({
                **row,
                "requirement_id": f"REQ-{uuid.uuid4().hex[:8].upper()}",
                "tender_id": tender_id,
                "org_id": tender.get("org_id"),
                "human_review_status": "pending",
                "completion_status": "not_started",
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
    # `ungrounded_dropped` is deliberately surfaced: a run where the model invented most of its
    # citations should be visible in the audit trail, not quietly successful.
    db.write_tender_audit(tender_id, "system", "requirements_extracted", result)
    return result
