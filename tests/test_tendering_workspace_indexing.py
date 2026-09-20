"""Workspace chunk indexing — re-extraction must replace a document's index, not add to it.

Extract can be clicked again on a document that is already `done`. Appending a second set of
chunks skews retrieval toward re-extracted documents and, after an embedding-model change, leaves
vectors from two different models in the same table — which is how search quietly starts
returning nonsense.
"""
from backend.apps.tendering import pipeline
from backend.core import db_core


def _chunks(*ids):
    return [{"chunk_id": cid, "text": f"text {cid}", "grounding": [{"page": 1, "bbox": [0, 0, 1, 1]}]}
            for cid in ids]


def _capture(monkeypatch, *, embed=lambda texts: [[0.1] * 4 for _ in texts]):
    """Record the delete/insert calls the indexer makes, in order."""
    calls: list[tuple] = []
    monkeypatch.setattr(db_core, "delete_chunks_for_document",
                        lambda document_id: calls.append(("delete", document_id)))
    monkeypatch.setattr(db_core, "insert_chunks", lambda rows: calls.append(("insert", rows)))
    from backend.core import llm
    monkeypatch.setattr(llm, "embed", embed)
    return calls


def test_old_chunks_are_deleted_before_the_new_ones_land(monkeypatch):
    calls = _capture(monkeypatch)

    pipeline._index_workspace_chunks("ws-1", "doc-1", _chunks("c1", "c2"))

    assert [call[0] for call in calls] == ["delete", "insert"]
    assert calls[0][1] == "doc-1"
    assert [row["chunk_id"] for row in calls[1][1]] == ["c1", "c2"]
    assert all(row["workspace_id"] == "ws-1" for row in calls[1][1])


def test_an_embedding_failure_leaves_the_previous_index_alone(monkeypatch):
    """Nothing is deleted until the replacement text is ready to be written."""
    def boom(_texts):
        raise RuntimeError("provider down")

    calls = _capture(monkeypatch, embed=boom)

    pipeline._index_workspace_chunks("ws-1", "doc-1", _chunks("c1"))

    # The embed failure degrades to text-only rows (no vector), but the delete+insert pair still
    # has to happen in that order and only once.
    assert [call[0] for call in calls] == ["delete", "insert"]
    assert "embedding" not in calls[1][1][0]
    assert calls[1][1][0]["text"] == "text c1"


def test_a_document_with_no_text_touches_nothing(monkeypatch):
    calls = _capture(monkeypatch)

    pipeline._index_workspace_chunks("ws-1", "doc-1", [{"chunk_id": "c1", "text": ""}])

    assert calls == []
