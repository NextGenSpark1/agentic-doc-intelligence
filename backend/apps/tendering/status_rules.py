"""What a requirement's evidence adds up to. Pure — no DB, no LLM, no imports from either.

One place decides how links become a status, because two places need the answer and they used to
disagree: matching left every requirement `unchecked` no matter what it found, while confirming
or dismissing a link went straight to `met` or back to `unchecked`.

The statuses:

  * ``met``       — evidence conclusively proves the requirement. Set either by a human
                    confirming a proposal, marking the work complete, OR by AI matching when a
                    proposal scores above the MET threshold and the underlying document is valid
                    through the tender closing date.
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

# A proposal below this does not colour a requirement as partially covered. Matching persists
# anything from 0.4 up, but 0.4 is "worth a person's glance", not "we appear to have this" — and
# a compliance matrix that looks half-covered on weak guesses is worse than one that looks empty.
MIN_PROPOSAL_SCORE = 0.6

# At or above this pending score, matching may propose `met` directly rather than `partial`.
# Kept high because a wrong `met` costs a bid: the team stops looking, submits, and is
# disqualified. The evidence-matching stage caps scores for documents expiring before the closing
# date at MET_SCORE_THRESHOLD - 0.05, so an expiring cert cannot slip through as met.
MET_SCORE_THRESHOLD = 0.75


def _score(link: dict) -> float:
    try:
        return float(link.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _has_confirmed(links: list[dict]) -> bool:
    return any(link.get("human_review_status") == "confirmed" for link in links)


def _best_pending_score(links: list[dict]) -> float:
    return max(
        (_score(link) for link in links if link.get("human_review_status") == "pending"),
        default=0.0,
    )


def _has_usable_proposal(links: list[dict], min_score: float) -> bool:
    return any(
        link.get("human_review_status") == "pending" and _score(link) >= min_score
        for link in links
    )


def _all_dismissed(links: list[dict]) -> bool:
    if not links:
        return False
    return all(link.get("human_review_status") == "dismissed" for link in links)


def status_from_evidence(links: list[dict], completion_status: str = "",
                         min_score: float = MIN_PROPOSAL_SCORE,
                         met_threshold: float = MET_SCORE_THRESHOLD) -> str:
    """The status the evidence implies, with no regard for what is stored today.

    Used after a person confirms or dismisses a link, where their action is the whole input.
    Also used to derive AI-set status during matching.
    """
    if completion_status == "complete":
        return MET
    if _has_confirmed(links):
        return MET
    if _best_pending_score(links) >= met_threshold:
        return MET
    if _has_usable_proposal(links, min_score):
        return PARTIAL
    if _all_dismissed(links):
        return REJECTED
    return GAP


def status_after_matching(links: list[dict], current_status: str,
                          completion_status: str = "",
                          min_score: float = MIN_PROPOSAL_SCORE,
                          met_threshold: float = MET_SCORE_THRESHOLD) -> str | None:
    """What matching may set this requirement to, or None to leave it alone.

    Matching may now write `met` when a proposal scores at or above the MET threshold — the
    same signal a strong pending proposal would give a human reviewer. It may not overwrite a
    status a person has already settled: a confirmed link, a manual `met`, or a `rejected`
    (all evidence reviewed and dismissed) is left alone.
    """
    if completion_status == "complete" or current_status in (MET, REJECTED):
        return None
    if _has_confirmed(links):
        # A confirmed link means a person already settled this; leave it to the review path.
        return None

    if _best_pending_score(links) >= met_threshold:
        implied = MET
    elif _has_usable_proposal(links, min_score):
        implied = PARTIAL
    elif _all_dismissed(links):
        implied = REJECTED
    else:
        implied = GAP

    return implied if implied != current_status else None
