"""Evidence matching — which vault document proves which requirement.

The genuinely new retrieval work in this product. Investigation's RAG matches chunks *within
one case*; this matches a requirement against a separate, **org-scoped** supplier corpus that
outlives any single tender.

Two-stage by design:

  1. **Retrieve** candidate vault excerpts by embedding the requirement (`db.match_supplier_docs`,
     which calls the `match_supplier_chunks` RPC — org-filtered in SQL). Cheap, recall-oriented,
     no LLM.
  2. **Adjudicate** the shortlist with one LLM call per requirement, which must pick from the
     supplied candidates and say *why*. A match with no rationale is worse than no match — a
     bidder would submit on it.

**This is the piece most exposed by the missing eval set.** A wrong match on a live bid has a
real cost: the company submits the wrong certificate and is disqualified. So the defaults here
are deliberately conservative — a similarity floor, a confidence floor, and every proposal born
`pending` — and `apps/tendering/evidence_goldens.md` records what still needs measuring.
"""
from __future__ import annotations

import re
import traceback
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

# A candidate whose expiry falls before the tender closing date cannot make a requirement `met`
# even if the document content is a strong match — the certificate will have lapsed by
# submission. Capping the score here keeps it below MET_SCORE_THRESHOLD (0.75) but above
# MIN_PROPOSAL_SCORE (0.6), so the match still surfaces as `partial` with a renewal note.
_EXPIRES_BEFORE_CLOSING_CAP = 0.70

# A candidate that has already expired today gets an even harsher cap — below the partial
# threshold, so the link is saved (visible to the reviewer) but does not colour the requirement
# as partially covered. A lapsed cert is context, not evidence.
_ALREADY_EXPIRED_CAP = 0.55

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

    The `match_supplier_chunks` RPC no longer filters expired documents — they are retrieved and
    surfaced to the reviewer with an `is_expired` flag so a lapsed certificate becomes a visible
    note rather than an invisible gap. This helper is still the single check for whether a
    confirmed evidence link should count toward readiness (readiness_review) and for the score
    cap in adjudication.
    """
    expiry = document.get("expiry_date")
    if not expiry:
        return False
    try:
        parsed = date.fromisoformat(str(expiry)[:10])
    except ValueError:
        return False
    return parsed < (today or datetime.now(timezone.utc).date())


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def expires_before(document: dict, cutoff: date | None) -> bool:
    """Would the document have lapsed by the tender's closing date?

    Called with `cutoff = workspace.closing_date`. A True answer disqualifies a document from
    satisfying a requirement even when the content matches: the certificate will not be valid at
    evaluation. Distinct from `is_expired`, which asks about today.
    """
    if cutoff is None:
        return False
    expiry = _parse_date(document.get("expiry_date"))
    if expiry is None:
        return False
    return expiry < cutoff


def validate_matches(raw: object, candidate_index: dict[str, dict],
                     min_score: float = _MIN_MATCH_SCORE,
                     closing_date: date | None = None,
                     today: date | None = None) -> list[dict]:
    """Keep only proposals grounded in a candidate we actually offered.

    Same discipline as requirement extraction, applied to matching: a `supplier_document_id`
    the model invented — or one from a document we never sent — is discarded. The vault
    document's identity comes from OUR candidate row, never from the model's output, so a
    hallucinated id cannot become a link to a real document.

    Scores are capped for candidates whose validity is a problem: already expired documents
    cap below the partial threshold (visible but non-covering), documents expiring before the
    tender closing date cap below the MET threshold (surfaces as partial with a renewal note).
    """
    if not isinstance(raw, dict):
        return []
    items = raw.get("matches")
    if not isinstance(items, list):
        return []

    today = today or datetime.now(timezone.utc).date()
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

        # Cap score by validity of the underlying document. Both flags are also reported in
        # the LLM payload so the rationale can explain the reason.
        already_expired = is_expired(candidate, today)
        expiring_early = (not already_expired) and expires_before(candidate, closing_date)
        if already_expired:
            score = min(score, _ALREADY_EXPIRED_CAP)
        elif expiring_early:
            score = min(score, _EXPIRES_BEFORE_CLOSING_CAP)

        if score < min_score:
            continue

        rationale = str(item.get("rationale") or "").strip()
        if not rationale:
            continue  # Rule 2 for matching: a proposal must say why, or it is not persisted

        kept.append({
            "supplier_document_id": doc_id,
            "doc_id": candidate.get("library_doc_id"),  # FK to library_documents
            "score": score,
            "rationale": rationale,
            "matched_chunk_id": candidate.get("chunk_id"),
            "matched_text": _strip_html(candidate.get("text") or "")[:600],
            "source": "llm",
            "already_expired": already_expired,
            "expires_before_closing": expiring_early,
        })
    return kept


def _payload(requirement: dict, candidates: list[dict],
             closing_date: date | None = None, today: date | None = None) -> dict:
    # `mandatory` is the column name on workspace_requirements. Reading `is_mandatory` here (the
    # name the extraction prompt uses in its own output) meant the adjudicator was told None for
    # every requirement, so it could not tell a must-have from a nice-to-have.
    today = today or datetime.now(timezone.utc).date()
    return {
        "requirement": {
            "description": requirement.get("description"),
            "category": requirement.get("category"),
            "is_mandatory": requirement.get("mandatory"),
            "required_evidence": requirement.get("required_evidence"),
        },
        "tender_closing_date": closing_date.isoformat() if closing_date else None,
        "candidate_documents": [
            {
                "supplier_document_id": c.get("supplier_document_id"),
                "title": c.get("title"),
                "doc_type": c.get("doc_type"),
                "expiry_date": str(c.get("expiry_date")) if c.get("expiry_date") else None,
                "is_expired": is_expired(c, today),
                "expires_before_closing": (
                    (not is_expired(c, today)) and expires_before(c, closing_date)
                ),
                "excerpt": _strip_html(c.get("text") or "")[:_MAX_EXCERPT_CHARS],
            }
            for c in candidates
        ],
    }


def _apply_status(requirement: dict, links: list[dict]) -> int:
    """Set the requirement's status from the evidence now attached to it. Returns 1 if written.

    Matching used to leave every requirement on `unchecked` however much it found, so a finished
    analysis produced a compliance matrix with nothing in the status column and a readiness score
    that read as if nobody had looked. What it may write is bounded by status_rules: `partial`
    when a proposal is worth reviewing, `gap` when there is nothing to show — never `met`, which
    stays a human's word (Rule 3).

    A failure here is swallowed on purpose: the evidence link is already saved, and losing the
    whole matching run over a status write would cost more than the status is worth.
    """
    from .. import db
    from ..status_rules import status_after_matching

    new_status = status_after_matching(
        links,
        requirement.get("status") or "unchecked",
        requirement.get("completion_status") or "",
    )
    if new_status is None:
        return 0
    try:
        db.update_requirement(requirement["req_id"], {"status": new_status})
        return 1
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 0


def match(tender_id: str, requirement_ids: list[str] | None = None) -> dict:
    """Propose vault evidence for a tender's requirements.

    Every requirement in the workspace is matched (requirements have no dismissed state) except
    those a person has already confirmed evidence for, and every proposal is born `pending`
    (Rule 3) — matching suggests, a human approves before it counts toward a submission. Pass
    `requirement_ids` to re-match a subset, e.g. after a vault upload.
    """
    from backend.core import llm, llm_reasoning

    from .. import db
    from ..prompts import EVIDENCE_MATCHING

    tender = db.get_tendering_workspace(tender_id) or {}
    org_id = tender.get("org_id")
    if not org_id:
        # Without an org there is no vault to match against, and no isolation boundary either.
        db.write_workspace_audit(tender_id, "system", "evidence_matching_skipped",
                                 {"reason": "tender has no org_id"})
        return {"proposed": 0, "skipped": 0, "ungrounded_dropped": 0, "requirements_matched": 0}

    # Closing date is the cutoff for "expires before closing" — a certificate valid today but
    # lapsed at evaluation cannot satisfy a requirement, and the adjudicator needs to know.
    closing_date = _parse_date(tender.get("closing_date"))
    today = datetime.now(timezone.utc).date()

    requirements = [
        r for r in db.list_workspace_requirements_raw(tender_id)
        if (requirement_ids is None or r["req_id"] in requirement_ids)
    ]

    # Existing links serve two purposes: a requirement a person has already confirmed evidence
    # for needs no second opinion (every re-analysis used to re-adjudicate the whole set — one
    # embedding and one LLM call each, for an answer that could not change anything), and the
    # status each requirement ends on depends on what it holds already, not only on what this
    # run proposes.
    links_by_req: dict[str, list[dict]] = {}
    for link in db.list_evidence_links(tender_id):
        if link.get("req_id"):
            links_by_req.setdefault(link["req_id"], []).append(link)
    confirmed_req_ids = {
        req_id for req_id, links in links_by_req.items()
        if any(link.get("human_review_status") == "confirmed" for link in links)
    }

    proposed = skipped = ungrounded = matched_requirements = no_candidates = 0
    left_unchanged = save_errors = already_confirmed = statuses_set = 0
    first_save_error: str | None = None

    for requirement in requirements:
        description = requirement.get("description") or ""
        if not description.strip():
            continue
        if requirement["req_id"] in confirmed_req_ids:
            already_confirmed += 1
            continue

        # 1. Retrieve — org-scoped in SQL. Two passes: vector similarity for meaning, keyword
        # ILIKE for exact identifiers the embeddings routinely miss. Merged before shortlist.
        try:
            query_vec = llm.embed([_match_query(requirement)])[0]
            vector_rows = db.match_supplier_docs(org_id, query_vec, _CANDIDATE_POOL)
        except Exception as exc:
            db.write_workspace_audit(tender_id, "system", "evidence_retrieval_failed",
                                     {"req_id": requirement["req_id"],
                                      "error": f"{type(exc).__name__}: {exc}"[:300]})
            continue

        keyword_rows: list[dict] = []
        keywords = extract_keywords(requirement)
        if keywords:
            try:
                keyword_rows = db.match_supplier_docs_by_keyword(org_id, keywords, _SHORTLIST)
            except Exception as exc:
                db.write_workspace_audit(tender_id, "system", "evidence_keyword_retrieval_failed",
                                         {"req_id": requirement["req_id"],
                                          "error": f"{type(exc).__name__}: {exc}"[:300]})

        merged_rows = merge_candidates(vector_rows, keyword_rows)
        candidates = shortlist_candidates(merged_rows)
        if not candidates:
            # Nothing in the vault comes close. That is a finding, not a blank: the requirement
            # becomes a gap so the matrix shows what the company cannot yet prove.
            no_candidates += 1
            statuses_set += _apply_status(requirement, links_by_req.get(requirement["req_id"], []))
            continue

        # 2. Adjudicate — the model picks from what we offered and justifies each pick.
        answer = llm_reasoning.ask(
            EVIDENCE_MATCHING,
            _payload(requirement, candidates, closing_date=closing_date, today=today),
            workspace_id=tender_id,
        )
        if answer is None:
            continue  # LLM unavailable — leave the requirement unmatched rather than guess

        candidate_index = {str(c.get("supplier_document_id")): c for c in candidates}
        matches = validate_matches(answer, candidate_index,
                                   closing_date=closing_date, today=today)
        raw_count = len(answer.get("matches") or []) if isinstance(answer, dict) else 0
        ungrounded += max(0, raw_count - len(matches))

        if matches:
            matched_requirements += 1
        for m in matches:
            if not m.get("doc_id"):
                # No library document linked to this vault doc — can't create an evidence link.
                skipped += 1
                continue
            try:
                created = db.upsert_evidence_link({
                    "req_id": requirement["req_id"],
                    "doc_id": m["doc_id"],
                    "workspace_id": tender_id,
                    "org_id": org_id,
                    "score": m["score"],
                    "rationale": m["rationale"],
                    "matched_chunk_id": m.get("matched_chunk_id") or "",
                    "source": m.get("source", "llm"),
                    "human_review_status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as exc:
                # Reported, not swallowed: a failing save must not look like "no matches".
                save_errors += 1
                first_save_error = first_save_error or f"{type(exc).__name__}: {exc}"[:300]
                continue
            if created is None:
                left_unchanged += 1  # a person already confirmed or dismissed this link
            else:
                proposed += 1
                links_by_req.setdefault(requirement["req_id"], []).append({
                    "human_review_status": "pending", "score": m["score"],
                })

        statuses_set += _apply_status(requirement, links_by_req.get(requirement["req_id"], []))

    result = {
        "proposed": proposed,
        "skipped": skipped,
        "already_confirmed": already_confirmed,
        "left_unchanged": left_unchanged,
        "save_errors": save_errors,
        "ungrounded_dropped": ungrounded,
        "statuses_set": statuses_set,
        "requirements_matched": matched_requirements,
        "requirements_considered": len(requirements),
        "requirements_without_candidates": no_candidates,
    }
    if first_save_error:
        result["first_save_error"] = first_save_error
    # `requirements_without_candidates` is the number that matters operationally: it is the
    # gap between what the tender demands and what the vault holds.
    db.write_workspace_audit(tender_id, "system", "evidence_matching_completed", result)
    return result


def _match_query(requirement: dict) -> str:
    """The text embedded to search the vault.

    `required_evidence` ("a valid CIDB G7 certificate") describes the *document sought*, while
    `description` describes the *obligation*. When the tender states the former, it is the far
    better query — so both are used, with the evidence phrasing first.
    """
    parts = [requirement.get("required_evidence") or "", requirement.get("description") or ""]
    return " ".join(p.strip() for p in parts if p.strip())


# Common English words we never want as keyword-search seeds: they match too much of the vault
# and add noise to the merge. Only used for the keyword pass; the vector pass is unaffected.
_KEYWORD_STOPWORDS = {
    "the", "and", "for", "with", "shall", "must", "any", "all", "from", "into", "onto", "upon",
    "will", "have", "been", "such", "each", "this", "that", "those", "these", "their", "them",
    "which", "within", "certificate", "certification", "certified", "required", "registration",
    "registered", "provide", "submit", "including", "include", "includes", "bidder", "tenderer",
    "company", "document", "documents", "least", "valid", "minimum", "years",
}

# Match acronyms (SSM, CIDB, ISO), model/grade codes (G7, ISO/IEC 27001), and quoted phrases.
_ACRONYM_RE = re.compile(r"[A-Z][A-Z0-9/\-]{1,15}")
_QUOTED_RE = re.compile(r'"([^"]{2,60})"')


def extract_keywords(requirement: dict, limit: int = 8) -> list[str]:
    """Pick short exact-match seeds from a requirement.

    Vector similarity is bad at short specific strings — an acronym, a grade code, a
    registration number. The keyword pass exists to catch those, so this is deliberately
    biased toward CAPS-heavy tokens rather than natural language. Long, common English
    words are dropped: they add noise without covering the failure mode we care about.
    """
    haystack = " ".join([
        str(requirement.get("required_evidence") or ""),
        str(requirement.get("description") or ""),
    ])
    if not haystack.strip():
        return []

    seeds: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        term = term.strip()
        if not term:
            return
        key = term.lower()
        if key in seen or key in _KEYWORD_STOPWORDS:
            return
        seen.add(key)
        seeds.append(term)

    # Quoted phrases first — the tender author's own emphasis.
    for match in _QUOTED_RE.findall(haystack):
        _add(match)
    # Then acronyms and grade/model codes.
    for match in _ACRONYM_RE.findall(haystack):
        _add(match)
    # Finally longer standalone words (>= 5 chars, not stopwords). Useful for things like
    # "audited", "insurance", "turnover" that carry meaning even without acronyms nearby.
    for word in re.findall(r"[A-Za-z][A-Za-z\-]{4,}", haystack):
        _add(word)

    return seeds[:limit]


def merge_candidates(vector_rows: list[dict], keyword_rows: list[dict]) -> list[dict]:
    """Combine the two retrieval passes into one candidate pool.

    A document that appears in both passes is stronger evidence than one that appears in only
    one — the vault knows about it and the requirement's keywords hit it. The merged score
    reflects that: a document in both passes takes the higher of its two scores, plus a small
    boost. Documents unique to either pass keep their own score.
    """
    merged: dict[str, dict] = {}
    for row in vector_rows:
        doc_id = str(row.get("supplier_document_id") or "")
        if not doc_id:
            continue
        merged[doc_id] = dict(row)

    for row in keyword_rows:
        doc_id = str(row.get("supplier_document_id") or "")
        if not doc_id:
            continue
        existing = merged.get(doc_id)
        try:
            keyword_score = float(row.get("similarity") or 0.0)
        except (TypeError, ValueError):
            keyword_score = 0.0
        if existing is None:
            merged[doc_id] = dict(row)
            continue
        try:
            vector_score = float(existing.get("similarity") or 0.0)
        except (TypeError, ValueError):
            vector_score = 0.0
        # Both passes hit — take the higher, boost slightly, cap at 1.0.
        existing["similarity"] = min(1.0, max(vector_score, keyword_score) + 0.05)

    return list(merged.values())
