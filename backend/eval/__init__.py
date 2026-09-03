"""Retrieval evaluation harness.

Measures whether the RAG layer finds the right chunks before an answer is ever generated.
Every retrieval change (hybrid search, reranking, similarity floors) is judged against a
golden set here rather than by eyeballing a few chat answers.

Entry point: `python -m backend.eval --help`
"""
from backend.eval.goldens import GoldenQuestion, GoldenSet, load_golden_set
from backend.eval.metrics import RetrievalMetrics, score_question
from backend.eval.runner import EvalReport, RunResult, compare, run_eval

__all__ = [
    "GoldenQuestion",
    "GoldenSet",
    "load_golden_set",
    "RetrievalMetrics",
    "score_question",
    "EvalReport",
    "RunResult",
    "run_eval",
    "compare",
]
