"""Hybrid retrieval — dense + keyword, fused with Reciprocal Rank Fusion.

Pure dense search fails on the queries investigators actually type. An embedding of
"INV-2024-0031" is not meaningfully close to the chunk containing it, so a literal
invoice, account, or tender reference can rank below loosely-related prose. A lexical
arm catches those; the dense arm keeps the paraphrase recall that keyword search lacks.

**Why fusion lives here and not in SQL.** The candidate pool comes from one SQL round trip
(`match_chunks_candidates`, both arms case_id-filtered in SQL so tenant isolation is never
left to application code), but the *combination* happens in Python. The fusion constants are
exactly what the eval harness tunes, and tuning must not require a database migration each
time — that is the difference between a knob that gets turned and one that does not.

RRF is used rather than score normalisation because the two arms' scores are not comparable:
cosine similarity and ts_rank_cd live on different scales with different distributions.
Ranks are comparable; raw scores are not.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Standard RRF damping constant (Cormack et al. 2009). Larger values flatten the
# contribution curve, so deep results matter more relative to the top few.
DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class FusedHit:
    """One chunk after fusion, carrying where each arm ranked it."""

    chunk_id: str
    score: float
    dense_rank: int | None = None
    keyword_rank: int | None = None

    @property
    def found_by(self) -> str:
        """Which arm(s) surfaced this chunk — the diagnostic that explains a ranking."""
        if self.dense_rank is not None and self.keyword_rank is not None:
            return "both"
        if self.keyword_rank is not None:
            return "keyword"
        return "dense"


def reciprocal_rank_fusion(
    arms: Mapping[str, Sequence[str]],
    weights: Mapping[str, float] | None = None,
    k: int = DEFAULT_RRF_K,
) -> list[FusedHit]:
    """Fuse several ranked id lists into one ranking.

    Each arm contributes `weight / (k + rank)` for every id it ranked, where rank is
    1-based. An id both arms rank highly therefore beats one that only a single arm loves,
    which is the whole point: agreement between independent signals is evidence.

    Ties break on chunk id so the ordering is deterministic — a report that reshuffles
    between identical runs is not evidence of anything.
    """
    if k < 1:
        raise ValueError(f"RRF k must be >= 1, got {k}")

    weights = weights or {}
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}

    for arm_name, ranked_ids in arms.items():
        weight = float(weights.get(arm_name, 1.0))
        if weight == 0.0:
            continue
        seen: set[str] = set()
        rank = 0
        for chunk_id in ranked_ids:
            # A duplicate id inside one arm must not be scored twice, and must not
            # consume a rank position from the ids behind it.
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            rank += 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + rank)
            ranks.setdefault(chunk_id, {})[arm_name] = rank

    fused = [
        FusedHit(
            chunk_id=cid,
            score=score,
            dense_rank=ranks.get(cid, {}).get("dense"),
            keyword_rank=ranks.get(cid, {}).get("keyword"),
        )
        for cid, score in scores.items()
    ]
    fused.sort(key=lambda h: (-h.score, h.chunk_id))
    return fused


def _ranked_ids(rows: Sequence[dict], rank_field: str) -> list[str]:
    """Pull one arm's ranked chunk ids out of the candidate rows."""
    ranked = [r for r in rows if r.get(rank_field) is not None]
    ranked.sort(key=lambda r: r[rank_field])
    return [str(r.get("chunk_id") or "") for r in ranked]


def fuse_candidates(
    rows: Sequence[dict],
    top_k: int,
    rrf_k: int = DEFAULT_RRF_K,
    dense_weight: float = 1.0,
    keyword_weight: float = 1.0,
) -> list[dict]:
    """Fuse `match_chunks_candidates` rows into a final top-k chunk list.

    Returns rows in the same shape the rest of the pipeline expects from `match_chunks`,
    with `found_by` / `fusion_score` added for diagnostics — so a surprising citation can
    be traced to the arm that produced it.
    """
    by_id = {str(r.get("chunk_id") or ""): r for r in rows}
    fused = reciprocal_rank_fusion(
        {"dense": _ranked_ids(rows, "dense_rank"), "keyword": _ranked_ids(rows, "keyword_rank")},
        weights={"dense": dense_weight, "keyword": keyword_weight},
        k=rrf_k,
    )

    out: list[dict] = []
    for hit in fused[:top_k]:
        row = by_id.get(hit.chunk_id)
        if row is None:
            continue
        out.append({**row, "fusion_score": hit.score, "found_by": hit.found_by})
    return out


def hybrid_search(
    case_id: str,
    query_text: str,
    query_embedding: list[float],
    top_k: int,
    pool: int = 50,
    rrf_k: int = DEFAULT_RRF_K,
    dense_weight: float = 1.0,
    keyword_weight: float = 1.0,
    candidates_fn=None,
) -> list[dict]:
    """Retrieve `top_k` chunks for a case using both arms.

    `pool` is how deep each arm contributes before fusion. It should comfortably exceed
    top_k — the gain comes from a chunk that one arm ranks 30th and the other ranks 2nd,
    and a shallow pool never sees it.
    """
    if candidates_fn is None:
        from backend.core import db_core

        candidates_fn = db_core.match_chunks_candidates

    rows = candidates_fn(case_id, query_embedding, query_text, pool) or []
    return fuse_candidates(
        rows,
        top_k=top_k,
        rrf_k=rrf_k,
        dense_weight=dense_weight,
        keyword_weight=keyword_weight,
    )
