"""Retrieval and answer metrics.

Pure functions over ranked id lists — no DB, no network, no LLM. Everything here is
deterministic and unit-testable, which matters because these numbers are the evidence
behind any claim about how well the system retrieves.

Retrieval metrics answer "did the right chunks come back, and how high up?":

  recall@k     fraction of the relevant chunks that appeared in the top k.
               The headline metric — a chunk never retrieved can never be cited.
  precision@k  fraction of retrieved chunks that were relevant. Low precision means
               the model's context is padded with noise it may still quote from.
  hit@k        did *any* relevant chunk appear. Coarse, but it's the floor: hit@k = 0
               means the answer cannot possibly be grounded.
  mrr          1/rank of the first relevant chunk. Sensitive to ordering, which matters
               because context position affects what the model actually uses.
  ndcg@k       rank-weighted overlap; the metric to watch when tuning a reranker.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from statistics import mean
from typing import Iterable, Sequence

from backend.eval.goldens import GoldenQuestion


@dataclass(frozen=True)
class RetrievalMetrics:
    """Scores for a single question's ranked retrieval."""

    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    hit_at_k: float = 0.0
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    k: int = 0
    n_relevant: int = 0
    n_retrieved: int = 0
    first_relevant_rank: int | None = None


def _dedupe(ids: Iterable[str]) -> list[str]:
    """Preserve rank order while dropping repeats — a chunk retrieved twice is one hit."""
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def score_retrieval(retrieved_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> RetrievalMetrics:
    """Score one ranked retrieval against its ground truth."""
    relevant = frozenset(i for i in relevant_ids if i)
    ranked = _dedupe(retrieved_ids)[:k]

    if not relevant:
        return RetrievalMetrics(k=k, n_relevant=0, n_retrieved=len(ranked))

    hits = [i for i in ranked if i in relevant]
    first_rank = next((pos for pos, i in enumerate(ranked, start=1) if i in relevant), None)

    # DCG with binary gains: each hit contributes 1/log2(rank+1).
    dcg = sum(1.0 / math.log2(pos + 1) for pos, i in enumerate(ranked, start=1) if i in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(pos + 1) for pos in range(1, ideal_hits + 1))

    return RetrievalMetrics(
        recall_at_k=len(hits) / len(relevant),
        precision_at_k=len(hits) / len(ranked) if ranked else 0.0,
        hit_at_k=1.0 if hits else 0.0,
        mrr=1.0 / first_rank if first_rank else 0.0,
        ndcg_at_k=dcg / idcg if idcg else 0.0,
        k=k,
        n_relevant=len(relevant),
        n_retrieved=len(ranked),
        first_relevant_rank=first_rank,
    )


# --------------------------- answer-level checks ---------------------------
# Deterministic string checks, deliberately no LLM judge. An LLM grading an LLM is
# a defensible extra signal but a poor foundation: these checks are reproducible and
# explainable, which is what a forensic buyer will ask for.

_ABSTENTION_PATTERNS = (
    r"\bcouldn'?t find\b",
    r"\bcould not find\b",
    r"\bnot (?:found|present|mentioned|stated|supported|available)\b",
    r"\bno (?:information|mention|record|evidence|reference)\b",
    r"\bdo(?:es)? not (?:appear|contain|mention|state|say|include|specify)\b",
    r"\bis not supported\b",
    r"\bi (?:don'?t|do not) (?:know|have)\b",
    r"\bnothing relevant\b",
    r"\bunable to (?:answer|determine|find)\b",
)
_ABSTENTION_RE = re.compile("|".join(_ABSTENTION_PATTERNS), re.IGNORECASE)


def is_abstention(answer: str) -> bool:
    """Did the system decline to answer rather than guess?

    For a negative question this is the *correct* behaviour, and the single most important
    property of a forensic assistant: confident invention is worse than silence.
    """
    return bool(_ABSTENTION_RE.search(answer or ""))


@dataclass(frozen=True)
class AnswerMetrics:
    """Deterministic checks on a generated answer."""

    missing_required: tuple[str, ...] = ()
    present_forbidden: tuple[str, ...] = ()
    abstained: bool = False
    cited_unretrieved: tuple[str, ...] = ()
    answered: bool = False

    @property
    def passed(self) -> bool:
        return not self.missing_required and not self.present_forbidden and not self.cited_unretrieved


_CITATION_RE = re.compile(r"\[(\d{1,3})\]")


def score_answer(question: GoldenQuestion, answer: str, n_citations: int) -> AnswerMetrics:
    """Check a generated answer against the golden question's expectations.

    `n_citations` is how many chunks were actually supplied to the model; any inline `[n]`
    beyond that range is a fabricated citation. That mirrors the pipeline's grounding
    guardrail, applied to chat — which the guardrail itself does not currently cover.
    """
    answer = answer or ""
    haystack = answer.lower()

    missing = tuple(s for s in question.must_include if s.lower() not in haystack)
    forbidden = tuple(s for s in question.must_not_include if s.lower() in haystack)

    cited = {int(m) for m in _CITATION_RE.findall(answer)}
    bad_citations = tuple(str(c) for c in sorted(cited) if c < 1 or c > n_citations)

    return AnswerMetrics(
        missing_required=missing,
        present_forbidden=forbidden,
        abstained=is_abstention(answer),
        cited_unretrieved=bad_citations,
        answered=bool(answer.strip()),
    )


@dataclass
class AggregateMetrics:
    """Mean retrieval metrics over a set of questions, plus abstention accuracy."""

    n_questions: int = 0
    # How many questions actually contribute to the retrieval averages below. Differs from
    # n_questions whenever negatives are present, since those carry no relevant chunks.
    n_scored: int = 0
    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    hit_at_k: float = 0.0
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    # Negative questions are scored on whether the system correctly declined.
    n_negative: int = 0
    # How many negatives actually had an answer generated. Retrieval-only runs leave this
    # at 0: abstention is then *unmeasured*, which must not be reported as *failed*.
    n_negative_answered: int = 0
    correct_abstentions: int = 0
    per_kind: dict[str, "AggregateMetrics"] = field(default_factory=dict)

    @property
    def abstention_rate(self) -> float:
        return self.correct_abstentions / self.n_negative_answered if self.n_negative_answered else 0.0

    @property
    def abstention_measured(self) -> bool:
        return self.n_negative_answered > 0


def aggregate(scored: Sequence[tuple[GoldenQuestion, RetrievalMetrics, AnswerMetrics | None]]) -> AggregateMetrics:
    """Average per-question scores, with a breakdown by question kind.

    Negative questions are excluded from retrieval averages — they have no relevant chunks,
    so a zero recall would drag the mean down while measuring nothing.
    """
    scorable = [(q, m) for q, m, _ in scored if q.kind != "negative"]
    negatives = [(q, a) for q, _, a in scored if q.kind == "negative"]

    agg = AggregateMetrics(
        n_questions=len(scored),
        n_scored=len(scorable),
        n_negative=len(negatives),
        n_negative_answered=sum(1 for _, a in negatives if a is not None),
        correct_abstentions=sum(1 for _, a in negatives if a is not None and a.abstained),
    )
    if scorable:
        agg.recall_at_k = mean(m.recall_at_k for _, m in scorable)
        agg.precision_at_k = mean(m.precision_at_k for _, m in scorable)
        agg.hit_at_k = mean(m.hit_at_k for _, m in scorable)
        agg.mrr = mean(m.mrr for _, m in scorable)
        agg.ndcg_at_k = mean(m.ndcg_at_k for _, m in scorable)

    kinds = {q.kind for q, _, _ in scored}
    if len(kinds) > 1:
        for kind in sorted(kinds):
            subset = [t for t in scored if t[0].kind == kind]
            agg.per_kind[kind] = aggregate(subset)
    return agg


def score_question(
    question: GoldenQuestion,
    retrieved_ids: Sequence[str],
    k: int,
    level: str = "chunk",
) -> RetrievalMetrics:
    """Score one question, using chunk-level ground truth when present."""
    relevant = question.relevant_ids("chunk" if level == "chunk" else "document")
    return score_retrieval(retrieved_ids, relevant, k)
