"""Requirement extraction — RFP documents become structured workspace requirements.

The rule pass runs first and deterministically, but it no longer lands as-is: its rows are sent
to the LLM as `draft_requirements` and the model returns one unified, deduplicated set. That is
what removes section-header noise and near-duplicates, and it means a rule draft the model does
not carry forward is not inserted. Drafts for excerpts the model returned nothing for at all are
counted as `rule_drafts_dropped` in the result and the audit row, with samples — so an obligation
disappearing between the rule pass and the database is visible rather than silent.

Grounding guardrail: every LLM requirement must cite the chunk_id of an excerpt we actually sent
— ungrounded rows are dropped before hitting the database. Page and source_doc come from OUR
chunk row, never from the model output.

If the LLM is unavailable the rule rows still land (per batch, and for the whole document if no
batch succeeded), so a workspace never comes back empty because a provider was having a bad
afternoon.
"""
from __future__ import annotations

import re
import traceback
import uuid
from datetime import datetime, timezone

from backend.core.text_utils import strip_html as _strip_html

from ..schemas import REQUIREMENT_CATEGORIES

# 12k produced 15+ fragmented batches for a typical 30-page tender, meaning cross-section
# references ("as per section 2") were extracted without their context. 80k fits most tenders
# in 1–2 batches and stays inside Groq's 128k context window.
_BATCH_CHAR_BUDGET = 80_000
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
    # Experience and personnel come before technical: "similar projects" and "key personnel" are
    # their own disqualifying categories, and lumping them under technical is what made the
    # compliance matrix show one big technical pile.
    ("experience",    ("experience", "track record", "similar project", "completed project",
                       "previous contract", "past performance", "years in operation")),
    ("personnel",     ("personnel", "key staff", "manpower", "curriculum vitae", " cv ",
                       "site supervisor", "project manager", "qualified engineer", "technician")),
    ("technical",     ("specification", "technical", "standard", "capacity",
                       "equipment", "methodology")),
)

# Older prompt versions offered submission_instruction / evaluation_criterion, which the database
# CHECK constraint does not allow. Kept as a translation so a model still answering with them (or
# a cached response) degrades to `other` instead of failing the insert.
_CATEGORY_NORMALISE = {
    "submission_instruction": "other",
    "evaluation_criterion": "other",
}
# Read from the shared constant rather than repeated here — these two lists drifting apart is
# the bug this file used to carry.
_VALID_CATEGORIES = set(REQUIREMENT_CATEGORIES)


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
                "chunk_id": str(chunk.get("chunk_id") or ""),
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


def drop_already_present(rows: list[dict], present: set[str]) -> tuple[list[dict], int]:
    """Return the rows the workspace does not already have, and how many were dropped.

    Re-running analysis keeps every requirement a person has worked on, then extracts all the
    documents again. Without this, each kept requirement was inserted a second time as a fresh
    'unchecked' copy on every run. `present` holds `requirement_hash` values (description +
    source document + page); descriptions cannot be edited after insert, so a stored row's hash
    stays stable. Rows kept here are added to `present`, so a requirement that turns up twice
    in one run is also inserted once.
    """
    from .. import db

    fresh: list[dict] = []
    dropped = 0
    for row in rows:
        digest = db.requirement_hash(row)
        if digest in present:
            dropped += 1
            continue
        present.add(digest)
        fresh.append(row)
    return fresh, dropped


def extract(workspace_id: str) -> dict:
    """Extract requirements from all processed documents in a workspace."""
    from backend.core import llm_reasoning
    from .. import db
    from ..prompts import REQUIREMENT_EXTRACTION

    workspace = db.get_tendering_workspace(workspace_id) or {}
    # Re-extract only what nobody has worked on yet. Whatever survives this delete is still in
    # the workspace, so it is excluded from the inserts below rather than duplicated.
    db.delete_workspace_requirements(workspace_id, pending_only=True)
    present = {db.requirement_hash(row) for row in db.list_workspace_requirements_raw(workspace_id)}

    # Documents in the pipeline come from the core documents table linked to this workspace.
    core_documents = db.list_core_documents_for_workspace(workspace_id)

    inserted = skipped = ungrounded = already_present = 0
    drafts_dropped = 0
    dropped_samples: list[str] = []
    insert_errors = 0
    first_insert_error: str | None = None
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

        unified_rows: list[dict] = []
        any_llm_succeeded = False
        for batch in _batch(chunks):
            batch_chunk_ids = {str(chunk.get("chunk_id")) for chunk in batch}
            # Only send the LLM drafts it can reference — those grounded in this batch's chunks.
            batch_drafts = [
                {
                    "chunk_id": row["chunk_id"],
                    "description": row["description"],
                    "category": row["category"],
                    "is_mandatory": row["mandatory"],
                }
                for row in rule_rows
                if str(row.get("chunk_id", "")) in batch_chunk_ids
            ]
            chunk_index = {str(chunk.get("chunk_id")): chunk for chunk in batch}
            payload = {
                "document_name": document.get("filename") or document.get("name"),
                "document_type": document.get("document_type"),
                "draft_requirements": batch_drafts,
                "excerpts": [
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "page": chunk.get("page"),
                        "text": _strip_html(chunk.get("text") or "")[:_MAX_CHUNK_CHARS],
                    }
                    for chunk in batch
                ],
            }
            answer = llm_reasoning.ask(REQUIREMENT_EXTRACTION, payload, workspace_id=workspace_id)
            if answer is None:
                # LLM failed for this batch — fall back to the rule rows for this batch only.
                for row in rule_rows:
                    if str(row.get("chunk_id", "")) in batch_chunk_ids:
                        unified_rows.append(row)
                continue
            any_llm_succeeded = True
            # Which excerpts did the model actually answer for? A draft whose excerpt produced no
            # requirement at all was not merged into a better-worded one — it was left behind, and
            # if it was a real obligation nobody finds out unless we say so.
            referenced_chunk_ids = {
                str(item.get("chunk_id") or "")
                for item in (answer.get("requirements") or [])
                if isinstance(item, dict)
            } if isinstance(answer, dict) else set()
            for draft in batch_drafts:
                if str(draft.get("chunk_id") or "") not in referenced_chunk_ids:
                    drafts_dropped += 1
                    if len(dropped_samples) < 3:
                        dropped_samples.append(str(draft.get("description") or "")[:160])
            validated = validate_llm_requirements(answer, chunk_index)
            raw_count = len(answer.get("requirements") or []) if isinstance(answer, dict) else 0
            ungrounded += max(0, raw_count - len(validated))
            unified_rows.extend(validated)

        # If LLM never responded at all, fall back to the full rule list.
        if not any_llm_succeeded:
            unified_rows = list(rule_rows)

        llm_count += len(unified_rows)

        new_rows, dropped = drop_already_present(unified_rows, present)
        already_present += dropped
        for row in new_rows:
            try:
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
            except Exception as exc:  # noqa: BLE001
                # Reported, not swallowed: a requirement that failed to save must never be
                # counted as a duplicate, or a half-written workspace looks complete.
                traceback.print_exc()
                insert_errors += 1
                first_insert_error = first_insert_error or f"{type(exc).__name__}: {exc}"[:300]
                continue
            if created is None:
                skipped += 1
            else:
                inserted += 1

    result = {
        "requirements_inserted": inserted,
        "already_present": already_present,
        "duplicates_skipped": skipped,
        "insert_errors": insert_errors,
        "ungrounded_dropped": ungrounded,
        "from_rules_draft": rule_count,
        "from_unified": llm_count,
        "rule_drafts_dropped": drafts_dropped,
    }
    if dropped_samples:
        result["rule_drafts_dropped_samples"] = dropped_samples
    if first_insert_error:
        result["first_insert_error"] = first_insert_error
    db.write_workspace_audit(workspace_id, "system", "requirements_extracted", result)
    return result
