"""Stage 4c — timeline reconstruction.

Collect every dated event across the case's extractions and order them chronologically.
Feeds the Timeline tab in the workspace.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from .. import db


def parse_date(value) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def compute_events(extractions: list[dict], case_id: str | None = None) -> list[dict]:
    events: list[dict] = []
    for ex in extractions:
        d = ex.get("extracted_json") or {}
        # payment_date is the main dated event in financial schemas
        iso = parse_date(d.get("payment_date"))
        if iso:
            vendor = d.get("vendor_name") or d.get("awarded_vendor") or "unknown vendor"
            amount = d.get("amount")
            label = f"Payment to {vendor}" + (f" ({amount})" if amount else "")
            events.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "case_id": case_id or ex.get("case_id"),
                    "event_date": iso,
                    "label": label,
                    "document_id": ex.get("document_id"),
                }
            )
        # communication dates
        for cdate in (d.get("dates") or []):
            ciso = parse_date(cdate)
            if ciso:
                events.append(
                    {
                        "event_id": str(uuid.uuid4()),
                        "case_id": case_id or ex.get("case_id"),
                        "event_date": ciso,
                        "label": "Communication event",
                        "document_id": ex.get("document_id"),
                    }
                )

    events.sort(key=lambda e: e["event_date"])
    return events


def build_timeline(case_id: str) -> list[dict]:
    extractions = db.list_extractions(case_id)
    events = compute_events(extractions, case_id)
    db.get_client().table("timeline_events").delete().eq("case_id", case_id).execute()
    if events:
        db.get_client().table("timeline_events").insert(events).execute()
    return events

