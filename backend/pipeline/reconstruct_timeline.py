"""Stage 4c — timeline reconstruction.

Collect every dated event across the case's extractions and order them chronologically.
Feeds the Timeline tab in the workspace.

After the deterministic events are built, a Gemini pass looks for sequencing anomalies a
date-sort can't catch (payment before the approval it claims to satisfy, backdating,
suspiciously even spacing). Flags may only reference an (event_date, document_id) pair that
is actually on the timeline we sent — anything else is dropped.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from .. import db
from . import llm_reasoning

_TIMELINE_ANOMALY_PROMPT = (
    "You are reviewing a chronologically-sorted timeline of events extracted from a forensic "
    "investigation case's documents. Look for sequencing anomalies a simple date-sort can't "
    "catch: a payment recorded before the approval or contract that should precede it, a "
    "document seemingly backdated relative to related events, or suspiciously clustered/evenly "
    "spaced dates that suggest fabrication. Only flag events already present in the list below — "
    "do not invent a new date or document_id.\n\n"
    'Reply with strict JSON: {"flags": [{"event_date": str, "document_id": str, '
    '"reasoning": str}]}. `event_date` and `document_id` must exactly match one entry from the '
    "timeline below. Return an empty list if nothing looks anomalous."
)

_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
    "%d %b %Y", "%d %B %Y", "%m/%d/%Y",
    "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
]

# Matches ISO dates, numeric dates, and month-name dates in free text
_DATE_TOKEN_RE = re.compile(
    r'\b\d{4}-\d{2}-\d{2}\b'
    r'|\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b'
    r'|\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
    r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b'
    r'|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
    r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\s+\d{1,2}[,]?\s+\d{4}\b',
    re.IGNORECASE,
)


def parse_date(value) -> str | None:
    if not value:
        return None
    text = str(value).strip().rstrip(',')
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def extract_dates_from_text(text: str) -> list[str]:
    """Extract all parseable ISO dates from a free-text string."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _DATE_TOKEN_RE.finditer(text or ""):
        iso = parse_date(m.group().strip().rstrip(','))
        if iso and iso not in seen:
            seen.add(iso)
            found.append(iso)
    return found


def extract_labeled_dates_from_text(text: str) -> list[tuple[str, str]]:
    """Return (label, iso_date) pairs by inferring a label from context before each date."""
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _DATE_TOKEN_RE.finditer(text or ""):
        iso = parse_date(m.group().strip().rstrip(","))
        if not iso or iso in seen:
            continue
        seen.add(iso)
        # look back up to 80 chars, stopping at |, ;, newline
        start = max(0, m.start() - 80)
        before = text[start:m.start()]
        segment = re.split(r"[|;,\n]", before)[-1].strip()
        # remove trailing colon / dash
        label = re.sub(r"[\s:—\-–]+$", "", segment).strip()
        if not label or len(label) > 50:
            label = "Procurement event"
        results.append((label.title(), iso))
    return results


def compute_events(extractions: list[dict], case_id: str | None = None) -> list[dict]:
    events: list[dict] = []
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        eid = case_id or ex.get("case_id")
        doc_id = ex.get("document_id")

        def evt(date_iso: str, label: str) -> dict:
            return {"event_id": str(uuid.uuid4()), "case_id": eid,
                    "event_date": date_iso, "label": label, "document_id": doc_id}

        # financial / audit / payment_tracing — payment_date
        iso = parse_date(d.get("payment_date"))
        if iso:
            vendor = d.get("vendor_name") or d.get("awarded_vendor") or "unknown vendor"
            amount = d.get("amount")
            events.append(evt(iso, f"Payment to {vendor}" + (f" ({amount})" if amount else "")))

        # communication — dates list
        for cdate in (d.get("dates") or []):
            ciso = parse_date(cdate)
            if ciso:
                events.append(evt(ciso, "Communication event"))

        # procurement_fraud — extract dates from approval_timeline text with context labels
        timeline_text = d.get("approval_timeline") or ""
        if timeline_text:
            for label, tiso in extract_labeled_dates_from_text(str(timeline_text)):
                events.append(evt(tiso, label))

        # general — key_dates list
        for kdate in (d.get("key_dates") or []):
            kiso = parse_date(kdate)
            if kiso:
                events.append(evt(kiso, "Document date"))

        # any custom date fields users might add (submission_date, award_date, etc.)
        for field in ("submission_date", "award_date", "report_date", "contract_date"):
            iso = parse_date(d.get(field))
            if iso:
                label = field.replace("_", " ").title()
                events.append(evt(iso, label))

    # deduplicate by (date, label, doc_id) then sort
    seen_keys: set[tuple] = set()
    deduped: list[dict] = []
    for e in events:
        key = (e["event_date"], e["label"], e["document_id"])
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(e)
    deduped.sort(key=lambda e: e["event_date"])
    return deduped


def _llm_timeline_flags(events: list[dict], case_id: str) -> list[dict]:
    if len(events) < 2:
        return []

    valid = {(e["event_date"], e["document_id"]) for e in events}
    payload = {"timeline": [
        {"event_date": e["event_date"], "label": e["label"], "document_id": e["document_id"]}
        for e in events
    ]}
    result = llm_reasoning.ask(_TIMELINE_ANOMALY_PROMPT, payload)
    flags = result.get("flags") if isinstance(result, dict) else None
    if not flags or not isinstance(flags, list):
        return []

    out = []
    for f in flags:
        if not isinstance(f, dict):
            continue
        date = str(f.get("event_date") or "")
        doc_id = str(f.get("document_id") or "")
        reasoning = str(f.get("reasoning") or "").strip()
        if (date, doc_id) not in valid or not reasoning:
            continue  # ungrounded — not one of the events we actually sent
        out.append({
            "event_id": str(uuid.uuid4()), "case_id": case_id,
            "event_date": date, "label": f"⚠ {reasoning}", "document_id": doc_id,
            "source": "llm", "reasoning": reasoning,
        })
    return out


def build_timeline(case_id: str) -> list[dict]:
    extractions = db.list_extractions(case_id)
    events = compute_events(extractions, case_id)
    for e in events:
        e.setdefault("source", "rule")
        e.setdefault("reasoning", None)
    events += _llm_timeline_flags(events, case_id)

    db.get_client().table("timeline_events").delete().eq("case_id", case_id).execute()
    if events:
        db.get_client().table("timeline_events").insert(events).execute()
    return events

