"""What a requirement's evidence adds up to. Pure — no DB, no LLM, no imports from either.

One place decides how links become a status, because two places need the answer and they used to
disagree: matching left every requirement `unchecked` no matter what it found, while confirming
or dismissing a link went straight to `met` or back to `unchecked`.

The statuses:

  * ``met``       — a person confirmed evidence, or marked the work complete. Only a human
                    produces this (Rule 3): matching proposes, it never decides.
  * ``partial``   — evidence has been proposed and is waiting for someone to approve it.
  * ``gap``       — nothing proposed, everything proposed was dismissed, or what was proposed is
                    too weak to count.
  * ``unchecked`` — the starting point, before matching has run.
"""
from __future__ import annotations

MET = "met"
PARTIAL = "partial"
GAP = "gap"
UNCHECKED = "unchecked"

# A proposal below this does not colour a requirement as partially covered. Matching persists
# anything from 0.4 up, but 0.4 is "worth a person's glance", not "we appear to have this" — and
# a compliance matrix that looks half-covered on weak guesses is worse than one that looks empty.
# Tuning this is part of the evidence eval work (see evidence_goldens.md).
MIN_PROPOSAL_SCORE = 0.6


def _score(link: dict) -> float:
    try:
        return float(link.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _has_confirmed(links: list[dict]) -> bool:
    return any(link.get("human_review_status") == "confirmed" for link in links)


def _has_usable_proposal(links: list[dict], min_score: float) -> bool:
    return any(
        link.get("human_review_status") == "pending" and _score(link) >= min_score
        for link in links
    )


def status_from_evidence(links: list[dict], completion_status: str = "",
                         min_score: float = MIN_PROPOSAL_SCORE) -> str:
    """The status the evidence implies, with no regard for what is stored today.

    Used after a person confirms or dismisses a link, where their action is the whole input:
    confirming makes a requirement met, and dismissing the last confirmed link makes it a gap —
    not `unchecked`, which claims nobody has looked at it and hides it from the blocker count as
    merely unreviewed.
    """
    if completion_status == "complete":
        return MET
    if _has_confirmed(links):
        return MET
    if _has_usable_proposal(links, min_score):
        return PARTIAL
    return GAP


def status_after_matching(links: list[dict], current_status: str,
                          completion_status: str = "",
                          min_score: float = MIN_PROPOSAL_SCORE) -> str | None:
    """What matching may set this requirement to, or None to leave it alone.

    Matching may fill in `partial` and `gap`, which is what turns a freshly analysed workspace
    into a compliance matrix someone can work through. It may never write `met` and never
    overwrite one: a requirement is only met because a person said so, and an analysis re-run
    must not quietly undo that.
    """
    if completion_status == "complete" or current_status == MET:
        return None
    if _has_confirmed(links):
        # A confirmed link means a person already settled this; leave it to the review path.
        return None
    implied = PARTIAL if _has_usable_proposal(links, min_score) else GAP
    return implied if implied != current_status else None
