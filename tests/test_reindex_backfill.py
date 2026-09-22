"""Backfilling embeddings for chunks that were stored text-only.

The loop's job is to terminate: it reads rows whose embedding is null and writes vectors back,
so anything that stops a row from being fixed (blank text, a write that does not take, a
provider still down) must end the pass rather than re-fetch the same rows for ever.
"""
from backend.apps.tendering import db as tendering_db
from backend.core import db_core, llm, reindex


def _table(rows):
    """A fake chunk table: fetch returns rows still missing a vector, write fills one in."""
    store = {row["id"]: dict(row) for row in rows}

    def fetch(limit):
        return [dict(row) for row in store.values() if row.get("embedding") is None][:limit]

    def write(row_id, embedding):
        store[row_id]["embedding"] = embedding

    return store, fetch, write


def _embed(texts):
    return [[0.1] * 4 for _ in texts]


def test_missing_vectors_are_filled():
    store, fetch, write = _table([
        {"id": 1, "text": "clause one", "embedding": None},
        {"id": 2, "text": "clause two", "embedding": None},
        {"id": 3, "text": "already indexed", "embedding": [0.5] * 4},
    ])

    filled, error = reindex._fill(fetch, write, "id", _embed, limit=100, batch_size=50)

    assert (filled, error) == (2, None)
    assert all(row["embedding"] is not None for row in store.values())


def test_chunks_with_no_text_end_the_pass_instead_of_looping():
    store, fetch, write = _table([{"id": 1, "text": "   ", "embedding": None}])

    filled, error = reindex._fill(fetch, write, "id", _embed, limit=100, batch_size=50)

    assert (filled, error) == (0, None)


def test_a_write_that_does_not_take_still_terminates():
    """Otherwise the same rows come back from every fetch, for ever."""
    _store, fetch, _write = _table([{"id": 1, "text": "clause", "embedding": None}])

    filled, error = reindex._fill(fetch, lambda row_id, vector: None, "id", _embed,
                                  limit=100, batch_size=50)

    assert (filled, error) == (1, None)


def test_a_provider_still_down_stops_and_reports():
    store, fetch, write = _table([{"id": 1, "text": "clause", "embedding": None}])

    def boom(_texts):
        raise RuntimeError("provider down")

    filled, error = reindex._fill(fetch, write, "id", boom, limit=100, batch_size=50)

    assert filled == 0
    assert "provider down" in error
    assert store[1]["embedding"] is None      # left for the next run, not lost


def test_the_limit_is_respected():
    store, fetch, write = _table([
        {"id": i, "text": f"clause {i}", "embedding": None} for i in range(10)
    ])

    filled, _error = reindex._fill(fetch, write, "id", _embed, limit=4, batch_size=3)

    assert filled == 4
    assert sum(1 for row in store.values() if row["embedding"] is None) == 6


def test_both_tables_are_covered(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(db_core, "list_chunks_missing_embeddings",
                        lambda limit: calls.append("chunks") or [])
    monkeypatch.setattr(tendering_db, "list_supplier_chunks_missing_embeddings",
                        lambda limit: calls.append("vault") or [])
    monkeypatch.setattr(llm, "embed", _embed)

    summary = reindex.backfill_missing_embeddings(limit=10)

    assert calls == ["chunks", "vault"]
    assert summary == {"chunks_filled": 0, "vault_chunks_filled": 0}
