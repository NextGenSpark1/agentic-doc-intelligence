"""Investigation chunk indexing — the two rules both other indexers already follow.

`_index_chunks` is the third place in this codebase that embeds and stores chunks, and it was
the one left behind: it sent an explicit null embedding (rejected by some pgvector/PostgREST
versions, so a whole document's chunks could fail to store after one bad embedding batch) and
appended instead of replacing, so re-extracting a document that had failed part-way through
left two copies of every chunk it had already indexed.
"""
from backend.core import extract as core_extract


def _chunks(*ids):
    return [{"chunk_id": cid, "text": f"text {cid}", "type": "text",
             "grounding": [{"page": 1, "bbox": [0, 0, 1, 1]}]} for cid in ids]


def _capture(monkeypatch, vectors):
    calls: list[tuple] = []
    monkeypatch.setattr(core_extract.db, "delete_chunks_for_document",
                        lambda document_id: calls.append(("delete", document_id)))
    monkeypatch.setattr(core_extract.db, "insert_chunks", lambda rows: calls.append(("insert", rows)))
    monkeypatch.setattr(core_extract, "_embed_in_batches", lambda texts, case_id, doc_id: vectors)
    return calls


def test_chunks_are_replaced_not_appended(monkeypatch):
    calls = _capture(monkeypatch, [[0.1] * 4, [0.2] * 4])

    core_extract._index_chunks("case-1", "doc-1", _chunks("c1", "c2"))

    assert [call[0] for call in calls] == ["delete", "insert"]
    assert calls[0][1] == "doc-1"
    rows = calls[1][1]
    assert [row["chunk_id"] for row in rows] == ["c1", "c2"]
    assert all(row["case_id"] == "case-1" for row in rows)


def test_a_failed_embedding_omits_the_key_rather_than_sending_null(monkeypatch):
    calls = _capture(monkeypatch, [None])

    core_extract._index_chunks("case-1", "doc-1", _chunks("c1"))

    row = calls[1][1][0]
    assert "embedding" not in row      # explicit null is what some vector columns reject
    assert row["text"] == "text c1"    # the text is still stored, so the chunk stays readable


def test_a_mix_of_embedded_and_failed_chunks_keeps_both(monkeypatch):
    calls = _capture(monkeypatch, [[0.1] * 4, None])

    core_extract._index_chunks("case-1", "doc-1", _chunks("c1", "c2"))

    rows = calls[1][1]
    assert "embedding" in rows[0]
    assert "embedding" not in rows[1]


def test_a_document_with_no_text_touches_nothing(monkeypatch):
    calls = _capture(monkeypatch, [])

    core_extract._index_chunks("case-1", "doc-1", [{"chunk_id": "c1", "text": ""}])

    assert calls == []
