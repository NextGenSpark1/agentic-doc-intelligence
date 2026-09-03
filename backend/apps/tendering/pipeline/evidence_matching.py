"""Evidence matching — which vault document proves which requirement.

The genuinely new retrieval work in this product. Investigation's RAG matches chunks *within
one case*; this matches a requirement against a separate, **org-scoped** supplier corpus that
outlives any single tender.

Two-stage by design:

  1. **Retrieve** candidate vault excerpts by embedding the requirement (`match_supplier_docs`,
     org-filtered in SQL). Cheap, recall-oriented, no LLM.
  2. **Adjudicate** the shortlist with one LLM call per requirement, which must pick from the
     supplied candidates and say *why*. A match with no rationale is worse than no match — a
     bidder would submit on it.

**This is the piece most exposed by the missing eval set.** A wrong match on a live bid has a
real cost: the company submits the wrong certificate and is disqualified. So the defaults here
are deliberately conservative — a similarity floor, a confidence floor, and every proposal born
`pending` — and `apps/tendering/evidence_goldens.md` records what still needs measuring.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from backend.core.text_utils import strip_html as _strip_html

# Retrieval breadth per requirement. Wider than the final shortlist because the adjudicator is
# what decides; retrieval only has to not miss.
_CANDIDATE_POOL = 12
_SHORTLIST = 6

# A vault excerpt below this cosine similarity is not worth an LLM call. Tuned conservatively:
# a missed match costs a human a search, a wrong match costs a disqualified bid.
_MIN_SIMILARITY = 0.35

# The adjudicator's own confidence floor for persisting a proposal.
_MIN_MATCH_SCORE = 0.4

_MAX_EXCERPT_CHARS = 1_200


def shortlist_candidates(rows: list[dict], min_similarity: float = _MIN_SIMILARITY,
                         limit: int = _SHORTLIST) -> list[dict]:
    """Trim retrieval output to the excerpts worth adjudicating.

    Deduplicates to the best excerpt per vault document: five excerpts from one certificate is
    one piece of evidence, and spending the adjudicator's attention on all five crowds out a
    different document that might actually be the right answer.
    """
    best_by_document: dict[str, dict] = {}
    for row in rows:
        try:
            similarity = float(row.get("similarity") or 0.0)
        except (TypeError, ValueError):
            continue
        if similarity < min_similarity:
            continue
        doc_id = str(row.get("supplier_document_id") or "")
        if not doc_id:
            continue
        current = best_by_document.get(doc_id)
        if current is None or similarity > float(current.get("similarity") or 0.0):
            best_by_document[doc_id] = row

    ranked = sorted(best_by_document.values(),
                    key=lambda r: float(r.get("similarity") or 0.0), reverse=True)
    return ranked[:limit]


def is_expired(document: dict, today: date | None = None) -> bool:
    """Has this vault document's expiry passed?

    `match_supplier_docs` already excludes expired documents in SQL. This is the second check,
    for links created before an expiry lapsed — a certificate that was valid when matched and
    has since expired must stop counting toward readiness.
    """
    expiry = document.get("expiry_date")
    if not expiry:
        return False
    try:
        parsed = date.fromisoformat(str(expiry)[:10])
    except ValueError:
        return False
    return parsed < (today or datetime.now(timezone.utc).date())


def validate_matches(raw: object, candidate_index: dict[str, dict],
                     min_score: float = _MIN_MATCH_SCORE) -> list[dict]:
    """Keep only proposals grounded in a candidate we actually offered.

    Same discipline as requirement extraction, applied to matching: a `supplier_document_id`
    the model invented — or one from a document we never sent — is discarded. The vault
    document's identity comes from OUR candidate row, never from the model's output, so a
    hallucinated id cannot become a link to a real document.
    """
    if not isinstance(raw, dict):
        return []
    items = raw.get("matches")
    if not isinstance(items, list):
        return []

    kept: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        doc_id = str(item.get("supplier_document_id") or "")
        candidate = candidate_index.get(doc_id)
        if candidate is None:
            continue  # ungrounded — not one of the candidates we supplied
        if doc_id in seen:
            continue  # one link per (requirement, document)
        seen.add(doc_id)

        try:
            score = max(0.0, min(1.0, float(item.get("match_score", 0.0))))
        except (TypeError, ValueError):
            continue
        if score < min_score:
            continue

        rationale = str(item.get("rationale") or "").strip()
        if not rationale:
            continue  # Rule 2 for matching: a proposal must say why, or it is not persisted

        kept.append({
            "supplier_document_id": doc_id,
            "match_score": score,
            "rationale": rationale,
            "matched_chunk_id": candidate.get("chunk_id"),
            "source": "llm",
        })
    return kept


def _payload(requirement: dict, candidates: list[dict]) -> dict:
    return {
        "requirement": {
            "description": requirement.get("description"),
            "category": requirement.get("category"),
            "is_mandatory": requirement.get("is_mandatory"),
            "required_evidence": requirement.get("required_evidence"),
        },
        "candidate_documents": [
            {
                "supplier_document_id": c.get("supplier_document_id"),
                "title": c.get("title"),
                "doc_type": c.get("doc_type"),
                "expiry_date": str(c.get("expiry_date")) if c.get("expiry_date") else None,
                "excerpt": _strip_html(c.get("text") or "")[:_MAX_EXCERPT_CHARS],
            }
            for c in candidates
        ],
    }


def match(tender_id: str, requirement_ids: list[str] | None = None) -> dict:
    """Propose vault evidence for a tender's requirements.

    Only requirements a human has not dismissed are matched, and every proposal is born
    `pending` (Rule 3) — matching suggests, a human approves before it counts toward a
    submission. Pass `requirement_ids` to re-match a subset, e.g. after a vault upload.
    """
    from backend.core import llm, llm_reasoning

    from .. import db
    from ..prompts import EVIDENCE_MATCHING

    tender = db.get_tender(tender_id) or {}
    org_id = tender.get("org_id")
    if not org_id:
        # Without an org there is no vault to match against, and no isolation boundary either.
        db.write_tender_audit(tender_id, "system", "evidence_matching_skipped",
                              {"reason": "tender has no org_id"})
        return {"proposed": 0, "skipped": 0, "ungrounded_dropped": 0, "requirements_matched": 0}

    requirements = [
        r for r in db.list_requirements(tender_id)
        if r.get("human_review_status") != "dismissed"
        and (requirement_ids is None or r["requirement_id"] in requirement_ids)
    ]

    proposed = skipped = ungrounded = matched_requirements = no_candidates = 0

    for requirement in requirements:
        description = requirement.get("description") or ""
        if not description.strip():
            continue

        # 1. Retrieve — org-scoped in SQL, expired documents excluded at the source.
        try:
            query_vec = llm.embed([_match_query(requirement)])[0]
            rows = db.match_supplier_docs(org_id, query_vec, _CANDIDATE_POOL)
        except Exception as exc:
            db.write_tender_audit(tender_id, "system", "evidence_retrieval_failed",
                                  {"requirement_id": requirement["requirement_id"],
                                   "error": f"{type(exc).__name__}: {exc}"[:300]})
            continue

        candidates = shortlist_candidates(rows)
        if not candidates:
            no_candidates += 1
            continue

        # 2. Adjudicate — the model picks from what we offered and justifies each pick.
        answer = llm_reasoning.ask(EVIDENCE_MATCHING, _payload(requirement, candidates),
                                   tender_id=tender_id)
        if answer is None:
            continue  # LLM unavailable — leave the requirement unmatched rather than guess

        candidate_index = {str(c.get("supplier_document_id")): c for c in candidates}
        matches = validate_matches(answer, candidate_index)
        raw_count = len(answer.get("matches") or []) if isinstance(answer, dict) else 0
        ungrounded += max(0, raw_count - len(matches))

        if matches:
            matched_requirements += 1
        for m in matches:
            created = db.upsert_evidence_link({
                **m,
                "evidence_link_id": f"EVL-{uuid.uuid4().hex[:8].upper()}",
                "requirement_id": requirement["requirement_id"],
                "org_id": org_id,
                "human_review_status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            if created is None:
                skipped += 1
            else:
                proposed += 1

    result = {
        "proposed": proposed,
        "skipped": skipped,
        "ungrounded_dropped": ungrounded,
        "requirements_matched": matched_requirements,
        "requirements_considered": len(requirements),
        "requirements_without_candidates": no_candidates,
    }
    # `requirements_without_candidates` is the number that matters operationally: it is the
    # gap between what the tender demands and what the vault holds.
    db.write_tender_audit(tender_id, "system", "evidence_matching_completed", result)
    return result


def _match_query(requirement: dict) -> str:
    """The text embedded to search the vault.

    `required_evidence` ("a valid CIDB G7 certificate") describes the *document sought*, while
    `description` describes the *obligation*. When the tender states the former, it is the far
    better query — so both are used, with the evidence phrasing first.
    """
    parts = [requirement.get("required_evidence") or "", requirement.get("description") or ""]
    return " ".join(p.strip() for p in parts if p.strip())
