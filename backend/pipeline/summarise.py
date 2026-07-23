"""Stage 5 — case summary + risk score.

The LLM writes the narrative ONLY from facts we already derived (findings, entities,
counts). It does not invent findings. We also compute a transparent risk score from
finding severities and store both on the case.
"""
from __future__ import annotations

import json

from .. import db, llm

_SEVERITY_WEIGHT = {"high": 30, "medium": 15, "low": 5}


def active_findings(findings: list[dict]) -> list[dict]:
    """Findings that still count toward the risk score and case summary. A dismissed finding is
    an explicit investigator decision that it's NOT real, so it must not inflate risk or be
    narrated as an irregularity — drop it. Pending and confirmed both stand."""
    return [f for f in findings if f.get("human_review_status") != "dismissed"]


def _risk_score(findings: list[dict]) -> float:
    score = sum(_SEVERITY_WEIGHT.get(f.get("severity", "low"), 5) for f in findings)
    return round(min(score, 100) / 100, 4)


def summarise(case_id: str) -> dict:
    case = db.get_case(case_id) or {}
    findings = active_findings(db.list_findings(case_id))
    entities = db.list_entities(case_id)
    documents = db.list_documents(case_id)

    risk = _risk_score(findings)

    facts = {
        "case_title": case.get("title"),
        "documents_processed": len(documents),
        "entities_found": len(entities),
        "findings": [
            {"type": f["finding_type"], "severity": f["severity"], "statement": f["statement"]}
            for f in findings
        ],
    }

    try:
        summary_text = llm.complete(
            tier="reasoning",
            messages=[
                {"role": "system", "content":
                    "You are an investigation analyst. Write a concise, neutral case summary "
                    "STRICTLY from the JSON facts provided. Do not invent findings or numbers. "
                    "State key irregularities, then suggested next steps. Plain prose."},
                {"role": "user", "content": json.dumps(facts, default=str)},
            ],
        )
    except Exception:
        # Deterministic fallback if no LLM key
        lines = [f"{len(documents)} documents processed; {len(entities)} entities identified."]
        for f in findings:
            lines.append(f"- [{f['severity'].upper()}] {f['statement']}")
        summary_text = "\n".join(lines)

    db.update_case(case_id, {"ai_summary": summary_text, "risk_score": risk})
    return {"summary": summary_text, "risk_score": risk, "finding_count": len(findings)}
