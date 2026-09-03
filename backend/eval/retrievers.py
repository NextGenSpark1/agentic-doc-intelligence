"""Pluggable retrievers — the A/B seam.

Every retrieval strategy implements the same `retrieve()` signature, so the runner can score
today's dense search and tomorrow's hybrid search against the identical golden set and print
the delta. Without this seam, "hybrid is better" stays an opinion.

`DenseRetriever` deliberately mirrors the production chat path (`llm.embed` →
`db.match_chunks`) rather than reimplementing it — if production changes, the eval follows,
which is the only way the numbers keep meaning anything.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieved chunk, normalised across retrievers."""

    chunk_id: str
    document_id: str = ""
    text: str = ""
    page: int = 0
    score: float = 0.0

    @classmethod
    def from_row(cls, row: dict) -> "RetrievedChunk":
        return cls(
            chunk_id=str(row.get("chunk_id") or ""),
            document_id=str(row.get("document_id") or ""),
            text=str(row.get("text") or ""),
            page=int(row.get("page") or 0),
            score=float(row.get("similarity") or row.get("score") or 0.0),
        )


@runtime_checkable
class Retriever(Protocol):
    """Anything that can turn a question into a ranked chunk list."""

    name: str

    def retrieve(self, question: str, case_id: str, k: int) -> list[RetrievedChunk]:
        ...


class DenseRetriever:
    """Production path: embed the question, ANN search over the case's chunks.

    This is the current baseline — pure dense, no reranking, no keyword signal, no
    similarity floor. Whatever it scores is the number every later change must beat.
    """

    name = "dense"

    def __init__(self, embed_fn=None, match_fn=None) -> None:
        # Imported lazily so the harness can be imported (and metrics unit-tested)
        # without Supabase or LLM credentials present.
        if embed_fn is None or match_fn is None:
            from backend.core import db_core, llm

            embed_fn = embed_fn or (lambda texts: llm.embed(texts))
            match_fn = match_fn or db_core.match_chunks
        self._embed = embed_fn
        self._match = match_fn

    def retrieve(self, question: str, case_id: str, k: int) -> list[RetrievedChunk]:
        query_vec = self._embed([question])[0]
        rows = self._match(case_id, query_vec, k) or []
        return [RetrievedChunk.from_row(r) for r in rows]


class HybridRetriever:
    """Dense + keyword arms, RRF-fused — the candidate for replacing `DenseRetriever`.

    Constructor args expose the fusion knobs so a sweep can be run without a migration or a
    config change:

        for kw in (0.5, 1.0, 2.0):
            run_eval(golden_set, HybridRetriever(keyword_weight=kw), k=8)
    """

    name = "hybrid"

    def __init__(
        self,
        pool: int = 50,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        keyword_weight: float = 1.0,
        embed_fn=None,
        candidates_fn=None,
    ) -> None:
        if embed_fn is None:
            from backend.core import llm

            embed_fn = lambda texts: llm.embed(texts)  # noqa: E731
        self._embed = embed_fn
        self._candidates_fn = candidates_fn
        self.pool = pool
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.keyword_weight = keyword_weight

    def retrieve(self, question: str, case_id: str, k: int) -> list[RetrievedChunk]:
        from backend.core import retrieval

        rows = retrieval.hybrid_search(
            case_id=case_id,
            query_text=question,
            query_embedding=self._embed([question])[0],
            top_k=k,
            pool=self.pool,
            rrf_k=self.rrf_k,
            dense_weight=self.dense_weight,
            keyword_weight=self.keyword_weight,
            candidates_fn=self._candidates_fn,
        )
        return [RetrievedChunk.from_row(r) for r in rows]


class KeywordRetriever:
    """Literal substring matching over a case's chunks.

    This is what production silently falls back to when embedding is unavailable, so it is
    worth measuring: it tells us how bad a degraded session actually is. It is also the
    baseline that a proper BM25 implementation has to beat.
    """

    name = "keyword"

    _STOPWORDS = frozenset(
        "the a an and or of to in on for is are was were what which who whom whose when "
        "where why how did does do this that these those with from by at as it its".split()
    )

    def __init__(self, fetch_fn=None) -> None:
        if fetch_fn is None:
            from backend.core import db_core

            def fetch_fn(case_id: str) -> list[dict]:
                return (
                    db_core.get_client()
                    .table("chunks")
                    .select("chunk_id,document_id,text,page")
                    .eq("case_id", case_id)
                    .execute()
                    .data
                    or []
                )

        self._fetch = fetch_fn

    def _terms(self, question: str) -> list[str]:
        words = "".join(c.lower() if c.isalnum() else " " for c in question).split()
        return [w for w in words if len(w) > 2 and w not in self._STOPWORDS]

    def retrieve(self, question: str, case_id: str, k: int) -> list[RetrievedChunk]:
        terms = self._terms(question)
        if not terms:
            return []
        scored: list[tuple[float, dict]] = []
        for row in self._fetch(case_id):
            text = (row.get("text") or "").lower()
            hits = sum(1 for t in terms if t in text)
            if hits:
                scored.append((hits / len(terms), row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [RetrievedChunk.from_row({**row, "score": s}) for s, row in scored[:k]]


class FixtureRetriever:
    """Replays recorded retrievals from a JSON file.

    Lets the harness run in CI with no database, no API keys, and no cost, and makes a
    regression reproducible: capture once with `--record`, then replay forever. Also the
    retriever used to test the harness itself.
    """

    name = "fixture"

    def __init__(self, path: str | Path, name: str | None = None) -> None:
        self.path = Path(path)
        if name:
            self.name = name
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._by_question: dict[str, list[RetrievedChunk]] = {
            qid: [RetrievedChunk.from_row(r) for r in rows] for qid, rows in raw.get("retrievals", {}).items()
        }
        # Fixtures are keyed by question id, which retrieve() does not receive, so the
        # runner sets this before each call.
        self.current_question_id: str = ""

    def retrieve(self, question: str, case_id: str, k: int) -> list[RetrievedChunk]:
        return self._by_question.get(self.current_question_id, [])[:k]


def build_retriever(name: str, **kwargs) -> Retriever:
    """Resolve a retriever by name for the CLI."""
    builders = {
        "dense": DenseRetriever,
        "hybrid": HybridRetriever,
        "keyword": KeywordRetriever,
        "fixture": FixtureRetriever,
    }
    if name not in builders:
        raise ValueError(f"unknown retriever {name!r} (expected one of {sorted(builders)})")
    return builders[name](**kwargs)
