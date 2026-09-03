"""Reciprocal Rank Fusion — the logic that combines the dense and keyword arms.

Fusion is the part of hybrid retrieval that is worth testing directly: the SQL arms are
ordinary ranked queries, but the combination decides what the model actually sees. These
tests are pure — no DB, no embeddings.
"""
import pytest

from backend.core.retrieval import (
    DEFAULT_RRF_K,
    FusedHit,
    fuse_candidates,
    hybrid_search,
    reciprocal_rank_fusion,
)


def _row(chunk_id, dense_rank=None, keyword_rank=None, **kw):
    return {
        "chunk_id": chunk_id,
        "document_id": kw.get("document_id", "d1"),
        "text": kw.get("text", f"text of {chunk_id}"),
        "page": kw.get("page", 1),
        "bbox": kw.get("bbox", [0, 0, 1, 1]),
        "similarity": kw.get("similarity", 0.0),
        "keyword_score": kw.get("keyword_score", 0.0),
        "dense_rank": dense_rank,
        "keyword_rank": keyword_rank,
    }


# ---------------------------------- fusion ----------------------------------
def test_agreement_between_arms_beats_a_single_arm_favourite():
    """The core property: two independent signals agreeing is stronger evidence."""
    fused = reciprocal_rank_fusion({
        "dense": ["b", "agreed"],       # agreed is 2nd here
        "keyword": ["c", "agreed"],     # and 2nd here
    })
    assert fused[0].chunk_id == "agreed"
    assert fused[0].found_by == "both"


def test_exact_token_hit_can_outrank_a_dense_result():
    """The whole reason hybrid exists: a literal reference the embedding misses.

    "INV-2024-0031" is rank 1 in the keyword arm and absent from the dense arm; a chunk
    of loosely-related prose leads the dense arm. The exact hit must still surface.
    """
    fused = reciprocal_rank_fusion({
        "dense": ["prose-1", "prose-2", "prose-3"],
        "keyword": ["exact-invoice-chunk"],
    })
    ids = [h.chunk_id for h in fused]
    assert ids[0] in ("prose-1", "exact-invoice-chunk")
    # It must at minimum outrank everything below the other arm's top hit.
    assert ids.index("exact-invoice-chunk") <= 1
    assert next(h for h in fused if h.chunk_id == "exact-invoice-chunk").found_by == "keyword"


def test_rank_one_scores_higher_than_rank_two():
    fused = reciprocal_rank_fusion({"dense": ["first", "second"]})
    assert fused[0].chunk_id == "first"
    assert fused[0].score > fused[1].score
    assert fused[0].score == pytest.approx(1.0 / (DEFAULT_RRF_K + 1))


def test_weights_shift_the_balance():
    arms = {"dense": ["d-top"], "keyword": ["k-top"]}
    dense_heavy = reciprocal_rank_fusion(arms, weights={"dense": 3.0, "keyword": 1.0})
    kw_heavy = reciprocal_rank_fusion(arms, weights={"dense": 1.0, "keyword": 3.0})
    assert dense_heavy[0].chunk_id == "d-top"
    assert kw_heavy[0].chunk_id == "k-top"


def test_zero_weight_disables_an_arm():
    fused = reciprocal_rank_fusion(
        {"dense": ["d1"], "keyword": ["k1"]}, weights={"keyword": 0.0}
    )
    assert [h.chunk_id for h in fused] == ["d1"]


def test_larger_rrf_k_flattens_the_curve():
    """Higher k narrows the gap between ranks, letting deep results matter more."""
    tight = reciprocal_rank_fusion({"dense": ["a", "b"]}, k=1)
    flat = reciprocal_rank_fusion({"dense": ["a", "b"]}, k=1000)
    assert (tight[0].score - tight[1].score) > (flat[0].score - flat[1].score)


def test_duplicate_id_within_an_arm_is_scored_once():
    fused = reciprocal_rank_fusion({"dense": ["a", "a", "b"]})
    assert [h.chunk_id for h in fused] == ["a", "b"]
    # The repeat must not consume b's rank position either.
    assert fused[1].dense_rank == 2


def test_empty_arms_produce_no_hits():
    assert reciprocal_rank_fusion({"dense": [], "keyword": []}) == []


def test_ordering_is_deterministic_on_ties():
    """Identical scores must not reshuffle between runs — a report has to be reproducible."""
    arms = {"dense": ["zzz"], "keyword": ["aaa"]}
    first = [h.chunk_id for h in reciprocal_rank_fusion(arms)]
    for _ in range(5):
        assert [h.chunk_id for h in reciprocal_rank_fusion(arms)] == first
    assert first == ["aaa", "zzz"]  # tie broken on id


def test_invalid_rrf_k_is_rejected():
    with pytest.raises(ValueError, match="RRF k must be"):
        reciprocal_rank_fusion({"dense": ["a"]}, k=0)


# ------------------------------ candidate rows ------------------------------
def test_fuse_candidates_preserves_row_shape_and_adds_diagnostics():
    rows = [
        _row("c1", dense_rank=1, keyword_rank=3),
        _row("c2", keyword_rank=1),
        _row("c3", dense_rank=2),
    ]
    out = fuse_candidates(rows, top_k=3)

    assert len(out) == 3
    # Every field the chat route reads must survive fusion.
    for r in out:
        assert {"chunk_id", "document_id", "text", "page", "bbox"} <= set(r)
        assert "fusion_score" in r and "found_by" in r
    assert {r["chunk_id"]: r["found_by"] for r in out}["c1"] == "both"
    assert {r["chunk_id"]: r["found_by"] for r in out}["c2"] == "keyword"


def test_fuse_candidates_respects_top_k():
    rows = [_row(f"c{i}", dense_rank=i) for i in range(1, 21)]
    assert len(fuse_candidates(rows, top_k=8)) == 8


def test_chunk_ranked_by_both_arms_leads_the_fused_list():
    rows = [
        _row("dense-only", dense_rank=1),
        _row("keyword-only", keyword_rank=1),
        _row("both", dense_rank=2, keyword_rank=2),
    ]
    assert fuse_candidates(rows, top_k=3)[0]["chunk_id"] == "both"


def test_no_candidates_yields_no_results():
    assert fuse_candidates([], top_k=8) == []


# -------------------------------- integration --------------------------------
def test_hybrid_search_passes_through_to_the_rpc_and_fuses():
    captured = {}

    def fake_candidates(case_id, embedding, query_text, pool):
        captured.update(case_id=case_id, query_text=query_text, pool=pool)
        return [_row("c1", dense_rank=2, keyword_rank=1), _row("c2", dense_rank=1)]

    out = hybrid_search(
        case_id="case-9", query_text="who approved INV-2024-0031?",
        query_embedding=[0.1] * 4, top_k=2, pool=50, candidates_fn=fake_candidates,
    )

    # The question text must reach the keyword arm — without it there is no lexical signal.
    assert captured == {"case_id": "case-9", "query_text": "who approved INV-2024-0031?", "pool": 50}
    assert out[0]["chunk_id"] == "c1"  # ranked by both arms


def test_hybrid_search_handles_an_empty_pool():
    assert hybrid_search("c", "q", [0.1], top_k=8, candidates_fn=lambda *a: []) == []


def test_hybrid_search_tolerates_null_returning_rpc():
    """Supabase returns None rather than [] when a query matches nothing."""
    assert hybrid_search("c", "q", [0.1], top_k=8, candidates_fn=lambda *a: None) == []
