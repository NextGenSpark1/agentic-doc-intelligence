"""What a requirement's evidence adds up to. Pure — no DB, no LLM, no imports from either.

One place decides how links become a status, because two places need the answer and they used to
disagree: matching left every requirement `unchecked` no matter what it found, while confirming
or dismissing a link went straight to `met` or back to `unchecked`.

The statuses:

  * ``met``       — evidence conclusively proves the requirement. Set by a human marking the
                    work complete, by a manual status override, OR by any (pending or confirmed)
                    evidence link whose score meets the MET threshold with an underlying document
                    that is valid through the tender closing date. Confirming a partial link is
                    the reviewer's agreement, not an upgrade — the status stays partial (but it
                    never drops below partial either: see status_from_evidence).
  * ``partial``   — evidence is proposed and worth reviewing but does not conclusively prove the
                    requirement (medium score, or the document expires before the closing date).
  * ``gap``       — nothing has been proposed and no evidence exists.
  * ``rejected``  — evidence WAS proposed and a reviewer dismissed every candidate. Distinct
                    from `gap`: the human has looked and rejected, not that nothing was found.
  * ``unchecked`` — the starting point, before matching has run.
"""
from __future__ import annotations

MET = "met"
PARTIAL = "partial"
GAP = "gap"
REJECTED = "rejected"
UNCHECKED = "unchecked"

# ── The score bands. Every evidence threshold in the product lives here. ────────────────────────
#
#   0.0 ──────── 0.4 ──────────── 0.6 ──────────── 0.75 ──────────── 1.0
#      not saved  │  saved, but gap  │    partial     │       met
#
# Below MIN_EVIDENCE_SCORE a proposal is not saved at all. Between that and MIN_PROPOSAL_SCORE it
# is saved for a reviewer to see but does not colour the requirement — "worth a glance" is not
# "we appear to have this", and a matrix that looks half-covered on weak guesses is worse than one
# that looks empty. MET_SCORE_THRESHOLD is kept high because a wrong `met` costs a bid: the team
# stops looking, submits, and is disqualified.
MIN_EVIDENCE_SCORE = 0.4
MIN_PROPOSAL_SCORE = 0.6
MET_SCORE_THRESHOLD = 0.75

# ── What the adjudicator answers, and what that answer is worth. ─────────────────────────────────
#
# The model used to be asked for a decimal match_score, and its instructions said to score partial
# evidence "below 0.5" — while partial status started at 0.6 and anything under 0.4 was thrown
# away. Following its own instructions, it could never produce a partial requirement: partial
# evidence was either discarded or shown as a gap. The prompt and these thresholds were written
# separately and had drifted apart, and nothing connected them.
#
# So the model now answers with a verdict, and the score is derived here from the bands above —
# the middle of the band each verdict belongs to. Moving a threshold moves the verdict's score
# with it; there is no second copy of the scale for a prompt edit to contradict. (A model that
# answers with only a decimal still works: validate_matches falls back to it.)
PROVES = "proves"
PARTIALLY_PROVES = "partially_proves"
RELATED_ONLY = "related_only"

VERDICT_SCORES = {
    PROVES: round((MET_SCORE_THRESHOLD + 1.0) / 2, 3),                          # 0.875 -> met
    PARTIALLY_PROVES: round((MIN_PROPOSAL_SCORE + MET_SCORE_THRESHOLD) / 2, 3),  # 0.675 -> partial
    RELATED_ONLY: round((MIN_EVIDENCE_SCORE + MIN_PROPOSAL_SCORE) / 2, 3),       # 0.5   -> gap
}


def _score(link: dict) -> float:
    try:
        return float(link.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _valid_links(links: list[dict]) -> list[dict]:
    """Links a reviewer hasn't dismissed. Pending and confirmed both count as valid — a
    confirmed link records the reviewer's agreement with the AI assessment, not an upgrade."""
    return [link for link in links if link.get("human_review_status") != "dismissed"]


def _confirmed_links(links: list[dict]) -> list[dict]:
    return [link for link in links if link.get("human_review_status") == "confirmed"]


def _best_valid_score(links: list[dict]) -> float:
    return max((_score(link) for link in _valid_links(links)), default=0.0)


def _all_dismissed(links: list[dict]) -> bool:
    if not links:
        return False
    return all(link.get("human_review_status") == "dismissed" for link in links)


def status_from_evidence(links: list[dict], completion_status: str = "",
                         min_score: float = MIN_PROPOSAL_SCORE,
                         met_threshold: float = MET_SCORE_THRESHOLD) -> str:
    """The status the evidence implies, with no regard for what is stored today.

    Confirming a link is the reviewer saying "I agree with the AI assessment" — it does NOT
    upgrade the status. A confirmed partial link keeps the requirement partial; only a link
    whose score meets the MET threshold (or a manual override, or completion_status=complete)
    makes the requirement met. Dismissed links are excluded from the calculation entirely.

    The old behaviour returned MET as soon as any link was confirmed, which meant AI-proposed
    partial evidence silently upgraded to met the instant a reviewer clicked confirm. That
    contradicted the agreed model (confirm = agree, override = change).
    """
    if completion_status == "complete":
        return MET

    # A confirmed link is a person saying "this document is evidence for this requirement". That
    # is worth at least `partial`, whatever the model scored it. Scoring confirmed and pending
    # links identically meant confirming a 0.55 proposal produced `gap` — the reviewer's positive
    # action left the matrix reading as if no evidence existed, and clicking Confirm appeared to
    # do nothing at all. Confirmation still does not reach `met` on its own: that needs the score,
    # a manual override, or completed work.
    confirmed = _confirmed_links(links)
    if confirmed:
        return MET if max(_score(link) for link in confirmed) >= met_threshold else PARTIAL

    valid = _valid_links(links)
    if valid:
        best = max(_score(link) for link in valid)
        if best >= met_threshold:
            return MET
        if best >= min_score:
            return PARTIAL

    # All existing links dismissed → reviewer looked and rejected everything. Distinct from
    # gap (nothing was ever proposed) because the human review is real work worth preserving.
    if _all_dismissed(links):
        return REJECTED
    return GAP


def status_after_matching(links: list[dict], current_status: str,
                          completion_status: str = "",
                          min_score: float = MIN_PROPOSAL_SCORE,
                          met_threshold: float = MET_SCORE_THRESHOLD) -> str | None:
    """What matching may set this requirement to, or None to leave it alone.

    Matching may write `met` when a proposal scores at or above the MET threshold. It may not
    overwrite a status a person has already settled: a confirmed link (the reviewer weighed
    in), a manual `met`, or `rejected` (all evidence reviewed and dismissed) is left alone.
    """
    if completion_status == "complete" or current_status in (MET, REJECTED):
        return None
    if any(link.get("human_review_status") == "confirmed" for link in links):
        # A confirmed link means a person already settled this; leave it to the review path.
        return None

    valid = _valid_links(links)
    if valid:
        best = _best_valid_score(valid)
        if best >= met_threshold:
            implied = MET
        elif best >= min_score:
            implied = PARTIAL
        else:
            implied = GAP
    elif _all_dismissed(links):
        implied = REJECTED
    else:
        implied = GAP

    return implied if implied != current_status else None
