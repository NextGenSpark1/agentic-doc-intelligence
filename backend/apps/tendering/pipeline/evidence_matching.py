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

from ..status_rules import (
    MIN_EVIDENCE_SCORE,
    PARTIALLY_PROVES,
    PROVES,
    RELATED_ONLY,
    VERDICT_SCORES,
)

# Retrieval breadth per requirement, counted in DOCUMENTS. Both search functions return one row
# per document — each document's best-matching chunk — so this is "consider up to twelve
# documents", not "take the twelve best passages in the vault". Those are very different
# questions, and asking the second one is what hid the audited financials and the project
# manager's CV behind a capability statement that mentions everything.
#
# Wider than the final shortlist because the adjudicator is what decides; retrieval only has to
# not miss.
_CANDIDATE_POOL = 12
_SHORTLIST = 6

# A vault excerpt below this cosine similarity is not worth an LLM call. Tuned conservatively:
# a missed match costs a human a search, a wrong match costs a disqualified bid.
_MIN_SIMILARITY = 0.35

# Below this a proposal is not saved at all. Defined with the other bands in status_rules.
_MIN_MATCH_SCORE = MIN_EVIDENCE_SCORE

# Validity caps, expressed as the best verdict a document may earn rather than as free-standing
# numbers, so they stay inside the right band whatever the thresholds are moved to.
#
# A document that lapses before the closing date can at most PARTIALLY prove a requirement, however
# strong its content: the certificate will be invalid at submission, so the match surfaces as
# `partial` with a renewal note rather than as `met`.
_EXPIRES_BEFORE_CLOSING_CAP = VERDICT_SCORES[PARTIALLY_PROVES]

# A document that has already lapsed is only RELATED: saved so the reviewer sees it and the reason,
# but it does not colour the requirement at all. A lapsed cert is context, not evidence.
_ALREADY_EXPIRED_CAP = VERDICT_SCORES[RELATED_ONLY]

# How the model may spell a verdict, mapped to the canonical one. Anything else is not a verdict.
_VERDICT_ALIASES = {
    "proves": PROVES, "proven": PROVES, "satisfies": PROVES, "fully_proves": PROVES,
    "partially_proves": PARTIALLY_PROVES, "partial": PARTIALLY_PROVES,
    "partially_satisfies": PARTIALLY_PROVES,
    "related_only": RELATED_ONLY, "related": RELATED_ONLY,
}
# Verdicts that say "this is not evidence" — dropped, but counted under their own reason.
_NON_EVIDENCE_VERDICTS = {"does_not_prove", "not_related", "none", "no_match", "unrelated"}

# How much of a candidate document the adjudicator is shown.
#
# It used to be a single chunk, and that was the bug behind "the AI cannot see obvious evidence".
# Retrieval returns the chunk closest to the REQUIREMENT, which is routinely the chunk that
# echoes the requirement's own wording rather than the one holding the answer. On the audited
# financial summary the winning chunk was "designed to test a tender requirement for minimum
# average annual turnover of RM 5,000,000" — a restatement of the requirement with no figures in
# it — while "Three-Year Average Annual Revenue: RM 7,166,667" two chunks away was never shown.
# The model was asked whether the wrong paragraph proved the requirement, said no, and the
# requirement came out as a gap against a document ranked first at 0.800.
#
# The excerpt is now the matched passage together with its neighbours in page order. Vault
# documents are certificates, CVs and summaries — a few pages at most — so in practice the model
# sees the whole document, which is what a human reviewer would read.
_MAX_EXCERPT_CHARS = 3_000


def shortlist_candidates(rows: list[dict], min_similarity: float = _MIN_SIMILARITY,
                         limit: int = _SHORTLIST) -> list[dict]:
    """Trim retrieval output to the excerpts worth adjudicating.

    Deduplicates to the best excerpt per vault document: five excerpts from one certificate is
    one piece of evidence, and spending the adjudicator's attention on all five crowds out a
    different document that might actually be the right answer. Retrieval now returns one row
    per document, so this is a safety net over the merge rather than the place the crowding is
    solved — it was never able to solve it here, because by this point the documents that lost
    the chunk-level race are already gone.

    Rows tagged with `_sources` containing "keyword" bypass the cosine similarity floor. The
    two retrieval passes score on different scales — cosine similarity for the vector pass,
    matched_keywords/total_keywords for the keyword pass — and comparing them directly is why
    a document containing the exact SSM registration number could score 2/8 = 0.25 in the
    keyword pass and get dropped before the LLM saw it. Vector-only rows still respect the
    floor because a low cosine there is genuine evidence of irrelevance.
    """
    best_by_document: dict[str, dict] = {}
    for row in rows:
        try:
            similarity = float(row.get("similarity") or 0.0)
        except (TypeError, ValueError):
            continue
        sources = row.get("_sources") or set()
        if "keyword" not in sources and similarity < min_similarity:
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
                     today: date | None = None,
                     drops: dict | None = None) -> list[dict]:
    """Keep only proposals grounded in a candidate we actually offered.

    Same discipline as requirement extraction, applied to matching: a `supplier_document_id`
    the model invented — or one from a document we never sent — is discarded. The vault
    document's identity comes from OUR candidate row, never from the model's output, so a
    hallucinated id cannot become a link to a real document.

    Each proposal carries a verdict — proves / partially_proves / related_only — and is scored
    from the bands in status_rules, not from a number the model chose. Validity then caps it: a
    document already expired is at most related, one expiring before the closing date at most
    partially proves (surfaces as partial with a renewal note).

    Pass `drops` to learn WHY proposals were discarded. A run reporting "28 dropped" cannot be
    acted on: a model citing documents that were never sent is a grounding problem, scores under
    the floor are a threshold problem, and missing rationales are a prompt problem, and they are
    fixed in completely different places.
    """
    def _drop(reason: str) -> None:
        if drops is not None:
            drops[reason] = drops.get(reason, 0) + 1

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
            _drop("malformed")
            continue
        doc_id = str(item.get("supplier_document_id") or "")
        candidate = candidate_index.get(doc_id)
        if candidate is None:
            # The model named a document we never sent it.
            _drop("ungrounded")
            continue
        if doc_id in seen:
            _drop("duplicate_document")
            continue  # one link per (requirement, document)
        seen.add(doc_id)

        # The verdict is the answer; its score comes from the bands in status_rules, so the model
        # cannot land a "partially proves" outside the partial band however it phrases things.
        # A bare decimal is still accepted for a model that ignores the verdict instruction, so
        # a provider change degrades the matching rather than emptying it.
        raw_verdict = str(item.get("verdict") or "").strip().lower().replace(" ", "_").replace("-", "_")
        verdict = _VERDICT_ALIASES.get(raw_verdict)
        if verdict is not None:
            score = VERDICT_SCORES[verdict]
        elif raw_verdict in _NON_EVIDENCE_VERDICTS:
            _drop("judged_not_evidence")
            continue
        elif "match_score" in item:
            try:
                score = max(0.0, min(1.0, float(item.get("match_score"))))
            except (TypeError, ValueError):
                _drop("unreadable_score")
                continue
        else:
            # Neither a verdict we know nor a number — there is nothing to judge it by.
            _drop("unknown_verdict" if raw_verdict else "no_verdict")
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
            _drop("score_below_floor")
            continue

        rationale = str(item.get("rationale") or "").strip()
        if not rationale:
            _drop("no_rationale")
            continue  # Rule 2 for matching: a proposal must say why, or it is not persisted

        kept.append({
            "supplier_document_id": doc_id,
            "doc_id": candidate.get("library_doc_id"),  # FK to library_documents
            "score": score,
            # None when the model answered with a bare decimal instead of a verdict — counted by
            # the run, so a model drifting off the contract shows up in the audit row.
            "verdict": verdict,
            "rationale": rationale,
            "matched_chunk_id": candidate.get("chunk_id"),
            "matched_text": _strip_html(candidate.get("text") or "")[:600],
            "source": "llm",
            "already_expired": already_expired,
            "expires_before_closing": expiring_early,
        })
    return kept


def build_excerpt(chunks: list[dict], matched_chunk_id: str,
                  budget: int = _MAX_EXCERPT_CHARS) -> str:
    """The matched passage plus as much of what surrounds it as the budget allows.

    Grows outwards from the match in page order, so the adjudicator reads the evidence in
    context rather than as one orphaned line. Falls back to the start of the document when the
    matched chunk cannot be found among the document's chunks.
    """
    keep = [(chunk, str(chunk.get("text") or "").strip()) for chunk in chunks]
    keep = [(chunk, text) for chunk, text in keep if text]
    if not keep:
        return ""

    ordered = [text for _chunk, text in keep]
    start = next((index for index, (chunk, _text) in enumerate(keep)
                  if str(chunk.get("chunk_id") or "") == str(matched_chunk_id or "")), 0)

    selected = [ordered[start]]
    used = len(ordered[start])
    before, after = start - 1, start + 1
    # Alternate outwards so the match keeps context on both sides, nearest first.
    while before >= 0 or after < len(ordered):
        for index in (after, before):
            if not 0 <= index < len(ordered):
                continue
            text = ordered[index]
            if used + len(text) + 1 > budget:
                continue
            if index > start:
                selected.append(text)
            else:
                selected.insert(0, text)
            used += len(text) + 1
        before -= 1
        after += 1
    return "\n".join(selected)[:budget]


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
                # `excerpt` is the matched passage in context, attached by the caller. The bare
                # chunk is the fallback for when the document's other chunks could not be read.
                "excerpt": _strip_html(
                    c.get("excerpt") or c.get("text") or ""
                )[:_MAX_EXCERPT_CHARS],
            }
            for c in candidates
        ],
    }


def _apply_status(requirement: dict, links: list[dict]) -> int:
    """Set the requirement's status from the evidence now attached to it. Returns 1 if written.

    Matching used to leave every requirement on `unchecked` however much it found, so a finished
    analysis produced a compliance matrix with nothing in the status column and a readiness score
    that read as if nobody had looked. What it may write is bounded by status_rules, which refuses
    to touch a `met`, a `rejected`, or anything a reviewer has already weighed in on.

    The write is tagged `status_source="ai"`, which is what lets the review path tell a status it
    derived from a status a person set by hand — and what lets the matrix show the difference.

    A failure here is swallowed on purpose: the evidence link is already saved, and losing the
    whole matching run over a status write would cost more than the status is worth.
    """
    from .. import db
    from ..status_rules import status_after_matching

    if (requirement.get("status_source") or "") == "manual":
        return 0  # a person set this status; matching does not revisit it

    new_status = status_after_matching(
        links,
        requirement.get("status") or "unchecked",
        requirement.get("completion_status") or "",
    )
    if new_status is None:
        return 0
    try:
        db.update_requirement(requirement["req_id"],
                              {"status": new_status, "status_source": "ai"})
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
    no_proposal_from_model = 0
    # Why validation discarded proposals, by reason — see validate_matches.
    drops: dict[str, int] = {}
    # What the model said about the proposals it kept. `numeric_score` counts answers that came
    # back as a bare decimal instead of a verdict: if that number climbs, the model has drifted
    # off the contract and the scoring is back to trusting its decimals.
    verdicts: dict[str, int] = {}
    # A vault document's chunks, read once per run rather than once per requirement: with fifty
    # requirements and a handful of candidates each, the same certificate would otherwise be
    # fetched hundreds of times.
    chunks_by_document: dict[str, list[dict]] = {}
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
        # Widen each candidate from its matched chunk to that passage in context. Without this
        # the model judges a document on one paragraph, and the paragraph retrieval picks is the
        # one that echoes the requirement rather than the one that answers it.
        for candidate in candidates:
            document_id = str(candidate.get("supplier_document_id") or "")
            if document_id and document_id not in chunks_by_document:
                try:
                    chunks_by_document[document_id] = db.list_supplier_chunks(document_id) or []
                except Exception as exc:  # noqa: BLE001
                    db.write_workspace_audit(tender_id, "system", "evidence_context_failed",
                                             {"supplier_document_id": document_id,
                                              "error": f"{type(exc).__name__}: {exc}"[:300]})
                    chunks_by_document[document_id] = []
            chunks = chunks_by_document.get(document_id) or []
            if chunks:
                candidate["excerpt"] = build_excerpt(chunks, candidate.get("chunk_id"))

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
                                   closing_date=closing_date, today=today, drops=drops)
        raw_count = len(answer.get("matches") or []) if isinstance(answer, dict) else 0
        ungrounded += max(0, raw_count - len(matches))
        # How many requirements the model answered with nothing at all — distinct from answering
        # with something that was then discarded, and pointing at a different fix.
        if raw_count == 0:
            no_proposal_from_model += 1

        if matches:
            matched_requirements += 1
        for m in matches:
            verdict_key = m.get("verdict") or "numeric_score"
            verdicts[verdict_key] = verdicts.get(verdict_key, 0) + 1
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
        "dropped_by_reason": drops,
        "verdicts": verdicts,
        "no_proposal_from_model": no_proposal_from_model,
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


def _row_similarity(row: dict) -> float:
    try:
        return float(row.get("similarity") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def merge_candidates(vector_rows: list[dict], keyword_rows: list[dict]) -> list[dict]:
    """Combine the two retrieval passes into one candidate pool, keeping the best chunk per doc.

    The bug this fixes: the old loop was `merged[doc_id] = dict(row)` on every iteration, so
    the LAST chunk of a document overwrote earlier chunks — and vector search returns chunks
    best-first, so we systematically kept the WORST excerpt from each document. The adjudicator
    then sometimes received the ISO cert's validity-dates chunk instead of its scope chunk and
    returned "cert found but the excerpt does not show the scope" — a self-inflicted false
    negative on a document we had already retrieved correctly.

    Now: dedupe by document, keeping the highest-similarity chunk. A document that appears in
    both passes gets a small boost so it survives the shortlist.
    """
    merged: dict[str, dict] = {}

    def _place(row: dict, source: str) -> None:
        doc_id = str(row.get("supplier_document_id") or "")
        if not doc_id:
            return
        existing = merged.get(doc_id)
        if existing is None:
            new_row = dict(row)
            new_row["_sources"] = {source}
            merged[doc_id] = new_row
            return
        # Preserve accumulated source tags across passes so shortlist_candidates can decide
        # whether to bypass the similarity floor for this document.
        existing_sources = set(existing.get("_sources") or set()) | {source}
        if _row_similarity(row) > _row_similarity(existing):
            new_row = dict(row)
            new_row["_sources"] = existing_sources
            merged[doc_id] = new_row
        else:
            existing["_sources"] = existing_sources

    for row in vector_rows:
        _place(row, "vector")
    for row in keyword_rows:
        _place(row, "keyword")

    # A document surfaced by both passes is stronger evidence than one seen by only one — the
    # vault knows about it and the requirement's exact terms hit it. Small boost so it survives.
    for row in merged.values():
        if {"vector", "keyword"}.issubset(row.get("_sources") or set()):
            row["similarity"] = min(1.0, _row_similarity(row) + 0.05)

    return list(merged.values())
