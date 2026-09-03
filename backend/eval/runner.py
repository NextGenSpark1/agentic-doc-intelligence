"""Runs a golden set through a retriever and scores it.

Two rules shape the output:

1. **Validated and unvalidated questions are scored separately.** Ground truth nobody has
   checked measures nothing, so only the validated number is quotable.
2. **Retrieval is scored without generating an answer by default.** Retrieval is where the
   ceiling lives — a chunk that never comes back can never be cited — and scoring it needs
   no LLM call, so the loop stays fast and free.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from backend.eval.goldens import GoldenQuestion, GoldenSet
from backend.eval.metrics import (
    AggregateMetrics,
    AnswerMetrics,
    RetrievalMetrics,
    aggregate,
    score_answer,
    score_question,
)
from backend.eval.retrievers import FixtureRetriever, RetrievedChunk, Retriever


@dataclass
class RunResult:
    """One question's outcome."""

    question: GoldenQuestion
    retrieved: list[RetrievedChunk]
    retrieval: RetrievalMetrics
    answer: str | None = None
    answer_metrics: AnswerMetrics | None = None
    latency_ms: float = 0.0
    error: str | None = None

    @property
    def retrieved_chunk_ids(self) -> list[str]:
        return [c.chunk_id for c in self.retrieved]


@dataclass
class EvalReport:
    """Scored results for a whole golden set."""

    retriever_name: str
    workspace_type: str
    k: int
    level: str = "chunk"
    results: list[RunResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @property
    def validated_results(self) -> list[RunResult]:
        return [r for r in self.results if r.question.is_validated]

    @property
    def unvalidated_results(self) -> list[RunResult]:
        return [r for r in self.results if not r.question.is_validated]

    @property
    def errors(self) -> list[RunResult]:
        return [r for r in self.results if r.error]

    def _agg(self, results: Sequence[RunResult]) -> AggregateMetrics:
        return aggregate([(r.question, r.retrieval, r.answer_metrics) for r in results])

    @property
    def headline(self) -> AggregateMetrics:
        """The quotable number: validated questions only."""
        return self._agg(self.validated_results)

    @property
    def provisional(self) -> AggregateMetrics:
        """Unvalidated questions — directional signal while a golden set is being built."""
        return self._agg(self.unvalidated_results)

    @property
    def overall(self) -> AggregateMetrics:
        return self._agg(self.results)

    @property
    def median_latency_ms(self) -> float:
        lats = sorted(r.latency_ms for r in self.results if r.latency_ms)
        if not lats:
            return 0.0
        mid = len(lats) // 2
        return lats[mid] if len(lats) % 2 else (lats[mid - 1] + lats[mid]) / 2

    def to_dict(self) -> dict:
        def agg_dict(a: AggregateMetrics) -> dict:
            return {
                "n_questions": a.n_questions,
                "n_scored": a.n_scored,
                "recall_at_k": round(a.recall_at_k, 4),
                "precision_at_k": round(a.precision_at_k, 4),
                "hit_at_k": round(a.hit_at_k, 4),
                "mrr": round(a.mrr, 4),
                "ndcg_at_k": round(a.ndcg_at_k, 4),
                "n_negative": a.n_negative,
                "n_negative_answered": a.n_negative_answered,
                "correct_abstentions": a.correct_abstentions,
                "abstention_rate": round(a.abstention_rate, 4),
                "abstention_measured": a.abstention_measured,
                "per_kind": {k: agg_dict(v) for k, v in a.per_kind.items()},
            }

        return {
            "retriever": self.retriever_name,
            "workspace_type": self.workspace_type,
            "k": self.k,
            "level": self.level,
            "n_total": len(self.results),
            "n_validated": len(self.validated_results),
            "n_unvalidated": len(self.unvalidated_results),
            "n_errors": len(self.errors),
            "median_latency_ms": round(self.median_latency_ms, 1),
            "headline_validated": agg_dict(self.headline),
            "provisional_unvalidated": agg_dict(self.provisional),
            "per_question": [
                {
                    "id": r.question.id,
                    "kind": r.question.kind,
                    "validated": r.question.is_validated,
                    "recall_at_k": round(r.retrieval.recall_at_k, 4),
                    "mrr": round(r.retrieval.mrr, 4),
                    "first_relevant_rank": r.retrieval.first_relevant_rank,
                    "retrieved": r.retrieved_chunk_ids,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def run_eval(
    golden_set: GoldenSet,
    retriever: Retriever,
    k: int = 8,
    level: str = "chunk",
    answer_fn: Callable[[GoldenQuestion, list[RetrievedChunk]], str] | None = None,
) -> EvalReport:
    """Score every question in `golden_set` through `retriever`.

    Pass `answer_fn` to also generate and check answers; leave it None to measure retrieval
    only (fast, free, and where the ceiling actually lives).
    """
    report = EvalReport(
        retriever_name=getattr(retriever, "name", type(retriever).__name__),
        workspace_type=golden_set.workspace_type,
        k=k,
        level=level,
    )

    for question in golden_set.questions:
        # Fixture replay is keyed by question id, which retrieve() has no way to receive.
        if isinstance(retriever, FixtureRetriever):
            retriever.current_question_id = question.id

        started = time.perf_counter()
        try:
            retrieved = retriever.retrieve(question.question, question.case_id, k)
            error = None
        except Exception as exc:  # a broken retriever should not abort the whole run
            retrieved, error = [], f"{type(exc).__name__}: {exc}"
        latency_ms = (time.perf_counter() - started) * 1000

        ids = [c.chunk_id if level == "chunk" else c.document_id for c in retrieved]
        retrieval = score_question(question, ids, k, level=level)

        answer, answer_metrics = None, None
        if answer_fn is not None and error is None:
            try:
                answer = answer_fn(question, retrieved)
                answer_metrics = score_answer(question, answer, n_citations=len(retrieved))
            except Exception as exc:
                error = f"answer_fn failed: {type(exc).__name__}: {exc}"

        report.results.append(
            RunResult(
                question=question,
                retrieved=retrieved,
                retrieval=retrieval,
                answer=answer,
                answer_metrics=answer_metrics,
                latency_ms=latency_ms,
                error=error,
            )
        )
    return report


@dataclass
class Comparison:
    """Delta between two runs over the same golden set."""

    baseline: EvalReport
    candidate: EvalReport

    @property
    def deltas(self) -> dict[str, float]:
        b, c = self.baseline.headline, self.candidate.headline
        return {
            "recall_at_k": c.recall_at_k - b.recall_at_k,
            "precision_at_k": c.precision_at_k - b.precision_at_k,
            "hit_at_k": c.hit_at_k - b.hit_at_k,
            "mrr": c.mrr - b.mrr,
            "ndcg_at_k": c.ndcg_at_k - b.ndcg_at_k,
        }

    @property
    def regressions(self) -> list[str]:
        """Question ids that got worse — the list to read before shipping a change."""
        base = {r.question.id: r.retrieval.recall_at_k for r in self.baseline.results}
        return sorted(
            r.question.id
            for r in self.candidate.results
            if r.question.id in base and r.retrieval.recall_at_k < base[r.question.id]
        )

    @property
    def improvements(self) -> list[str]:
        base = {r.question.id: r.retrieval.recall_at_k for r in self.baseline.results}
        return sorted(
            r.question.id
            for r in self.candidate.results
            if r.question.id in base and r.retrieval.recall_at_k > base[r.question.id]
        )


def compare(baseline: EvalReport, candidate: EvalReport) -> Comparison:
    return Comparison(baseline=baseline, candidate=candidate)


def record_fixture(report: EvalReport, path: str | Path) -> Path:
    """Save a run's raw retrievals so it can be replayed offline.

    Turns a live run into a reproducible CI check, and freezes the retrievals behind a
    reported number so the result stays auditable after the data moves on.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "retriever": report.retriever_name,
        "workspace_type": report.workspace_type,
        "k": report.k,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "retrievals": {
            r.question.id: [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "text": c.text,
                    "page": c.page,
                    "score": c.score,
                }
                for c in r.retrieved
            ]
            for r in report.results
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
