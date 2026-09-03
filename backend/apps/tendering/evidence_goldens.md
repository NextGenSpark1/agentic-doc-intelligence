# Evidence matching — what still needs measuring

Evidence matching is the highest-risk AI in this product. A wrong match means a company submits
the wrong certificate and is disqualified from a bid it could have won. The build plan is blunt
that this stage "needs an eval harness from day one," and **it does not have one yet.**

This file records what to measure, so the gap is explicit rather than discovered later.

## Current state

Built and unit-tested: retrieval shortlisting, the grounding guardrail, score clamping, expiry
handling, the match query. Those tests prove the *plumbing* is correct — that an invented
document id is dropped, that a rationale is mandatory, that a weak match never reaches the
database.

**Not measured: whether the matches are any good.** No golden set exists, so nobody can say
what fraction of proposals a bid manager would accept, or how many real matches are missed.

## What to measure

The harness in `backend/eval/` already scores retrieval; evidence matching needs a second set
because the unit is different — requirement → vault document, not question → chunk.

| Metric | Why it matters here |
|---|---|
| **Match precision** | Of the proposals shown to a bid manager, how many do they approve? This is the number that decides whether the feature helps or wastes their time. Precision matters more than recall: a missed match costs a search, a wrong one costs a bid. |
| **Match recall** | Of the requirements the vault *can* satisfy, how many got a proposal? Low recall means the gap list is wrong, which misleads the readiness score. |
| **Correct abstention** | When the vault genuinely cannot satisfy a requirement, does the model return `{"matches": []}`? A fabricated weak match here is the failure mode that loses bids. |
| **Rationale accuracy** | Does the stated reason actually hold — does the certificate really say G7? A plausible-sounding wrong rationale is worse than no rationale, because it survives review. |

## Building the golden set

1. Take a real tender with extracted requirements and a real (or realistic) org vault.
2. For each requirement, a bid manager records which vault documents genuinely satisfy it —
   including **none**, which is a valid and important answer.
3. Deliberately include near-miss pairs, because they are where the model actually fails:
   - CIDB **G4** certificate against a **G7** requirement
   - an **expired** certificate against a current requirement
   - audited accounts from the **wrong financial year**
   - a document on the right topic that proves the wrong thing (a safety *policy* against a
     requirement for a safety *certification*)
4. Verify by hand. As with the retrieval goldens, ground truth nobody checked measures nothing.

## Tuning knobs, once there is a set to tune against

All in `pipeline/evidence_matching.py`, currently set conservatively by judgement, not data:

| Constant | Now | What it trades |
|---|---|---|
| `_MIN_SIMILARITY` | 0.35 | Retrieval floor. Lower = better recall, more LLM calls. |
| `_MIN_MATCH_SCORE` | 0.4 | Persistence floor. Higher = fewer, better proposals. |
| `_CANDIDATE_POOL` | 12 | Retrieval breadth before shortlisting. |
| `_SHORTLIST` | 6 | How many candidates the adjudicator sees per requirement. |

Until the set exists, **leave these conservative.** Under-proposing is a visible gap a human
can fill; over-proposing is an invisible error that reaches a submission.

See `backend/eval/goldens/README.md` for the authoring conventions this should follow.
