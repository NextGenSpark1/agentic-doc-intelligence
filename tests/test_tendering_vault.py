"""Supplier vault lifecycle — deletion cascade.

The vault feeds evidence matching, so a row that outlives what created it does not just
linger: it gets proposed as evidence for a live bid. These tests pin the cascade using a
stubbed Supabase client, so they need no database.
"""
from unittest.mock import MagicMock

from backend.apps.tendering import db


class _FakeTable:
    """Records the delete/select calls made against one table name."""

    def __init__(self, name: str, registry: dict, rows: list[dict]):
        self.name = name
        self.registry = registry
        self.rows = rows
        self._filters: dict = {}

    def select(self, *_a, **_k):
        return self

    def delete(self):
        self.registry.setdefault("deletes", []).append(self)
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def execute(self):
        self.registry.setdefault("calls", []).append((self.name, dict(self._filters)))
        return MagicMock(data=self.rows)


class _FakeClient:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self.registry: dict = {}
        self.rows_by_table = rows_by_table
        self.deleted: list[tuple[str, dict]] = []

    def table(self, name):
        table = _FakeTable(name, self.registry, self.rows_by_table.get(name, []))
        original_delete = table.delete

        def delete():
            result = original_delete()

            def execute():
                self.deleted.append((name, dict(table._filters)))
                return MagicMock(data=[])

            result.execute = execute
            return result

        table.delete = delete
        return table


def _client_with_vault_rows(rows):
    return _FakeClient({"supplier_documents": rows})


def test_deleting_a_library_document_removes_its_vault_rows(monkeypatch):
    """A document removed from the library must stop being searchable evidence.

    supplier_documents.library_doc_id has no foreign key, so nothing cascades in the
    database. Without an explicit cascade the chunks stay in match_supplier_chunks and the
    deleted document can still be proposed for a live bid.
    """
    client = _client_with_vault_rows([{"supplier_document_id": "SUP-1"}])
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.delete_library_document("LIB-1")

    deleted = dict((name, filters) for name, filters in client.deleted)
    assert "supplier_document_chunks" in deleted, "vault chunks were left searchable"
    assert deleted["supplier_document_chunks"] == {"supplier_document_id": "SUP-1"}
    assert deleted["supplier_documents"] == {"supplier_document_id": "SUP-1"}
    assert deleted["library_documents"] == {"doc_id": "LIB-1"}


def test_vault_rows_are_deleted_before_the_library_row(monkeypatch):
    """Order matters: a part-way failure should leave a visible, retryable library entry
    rather than orphaned evidence with no owning document."""
    client = _client_with_vault_rows([{"supplier_document_id": "SUP-1"}])
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.delete_library_document("LIB-1")

    order = [name for name, _ in client.deleted]
    assert order.index("supplier_document_chunks") < order.index("library_documents")
    assert order.index("supplier_documents") < order.index("library_documents")


def test_chunks_are_deleted_before_their_parent_document(monkeypatch):
    client = _client_with_vault_rows([{"supplier_document_id": "SUP-1"}])
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.delete_library_document("LIB-1")

    order = [name for name, _ in client.deleted]
    assert order.index("supplier_document_chunks") < order.index("supplier_documents")


def test_every_vault_entry_for_the_document_is_removed(monkeypatch):
    """Re-uploading creates a second supplier_documents row for the same library doc, so the
    cascade must clear all of them, not just the newest."""
    client = _client_with_vault_rows([
        {"supplier_document_id": "SUP-1"},
        {"supplier_document_id": "SUP-2"},
    ])
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.delete_library_document("LIB-1")

    cleared = {
        filters["supplier_document_id"]
        for name, filters in client.deleted
        if name == "supplier_documents"
    }
    assert cleared == {"SUP-1", "SUP-2"}


def test_a_document_with_no_vault_entry_still_deletes(monkeypatch):
    """URL-only library entries never get a supplier_documents row — deletion must not fail."""
    client = _client_with_vault_rows([])
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.delete_library_document("LIB-1")

    assert [name for name, _ in client.deleted] == ["library_documents"]


# ------------------------------ re-indexing (#3) ------------------------------
# `_index_vault_chunks` is exercised with db and the embedder stubbed, so the ordering of the
# delete and insert can be observed directly.

from backend.apps.tendering.pipeline import vault


def _chunks(*ids):
    return [{"chunk_id": cid, "text": f"text {cid}", "grounding": [{"page": 1, "bbox": []}]}
            for cid in ids]


def _record_vault_calls(monkeypatch, embed=None):
    calls: list[tuple] = []
    monkeypatch.setattr(db, "delete_supplier_chunks",
                        lambda sid: calls.append(("delete", sid)))
    monkeypatch.setattr(db, "insert_supplier_chunks",
                        lambda rows: calls.append(("insert", [r["chunk_id"] for r in rows])))
    monkeypatch.setattr(vault, "_embed_in_batches",
                        embed or (lambda texts, *_a, **_k: [[0.0] * 3 for _ in texts]))
    return calls


def test_reindexing_replaces_the_previous_chunks(monkeypatch):
    """Clicking Extract twice must not double the document's rows in the vault."""
    calls = _record_vault_calls(monkeypatch)

    vault._index_vault_chunks("org-1", "SUP-1", _chunks("c1", "c2"))

    assert calls == [("delete", "SUP-1"), ("insert", ["c1", "c2"])]


def test_old_chunks_survive_an_embedding_failure(monkeypatch):
    """The delete waits until the new chunks are embedded, so a failure mid-extract leaves
    the previous working index searchable instead of wiping it."""
    def failing_embed(*_a, **_k):
        raise RuntimeError("embedding provider down")

    calls = _record_vault_calls(monkeypatch, embed=failing_embed)

    try:
        vault._index_vault_chunks("org-1", "SUP-1", _chunks("c1"))
    except RuntimeError:
        pass

    assert ("delete", "SUP-1") not in calls


def test_a_document_with_no_text_leaves_the_index_untouched(monkeypatch):
    """An empty parse (e.g. an image ADE could not read) is not a reason to delete a
    previously good index."""
    calls = _record_vault_calls(monkeypatch)

    vault._index_vault_chunks("org-1", "SUP-1", [{"chunk_id": "c1", "text": ""}])

    assert calls == []


# ------------------------- embedding-failure audit (#7) -------------------------
def test_vault_embedding_failure_is_not_logged_against_a_case(monkeypatch):
    """The vault is org-scoped, so an embedding failure must not land an org id in
    audit_log.case_id. The row should still link to the vault document via the detail.

    Uses the real core _embed_in_batches, stubbing only the embedder and the audit writer,
    so the case_id actually passed to write_audit is what gets checked.
    """
    from backend.core import extract as core_extract

    audits: list[tuple] = []
    monkeypatch.setattr(core_extract, "_embed_batch_with_retry",
                        lambda batch: (_ for _ in ()).throw(RuntimeError("provider down")))
    monkeypatch.setattr(core_extract.db, "write_audit",
                        lambda case_id, actor, action, detail=None, **kw: audits.append(
                            (case_id, action, detail)))
    monkeypatch.setattr(vault, "_embed_in_batches", core_extract._embed_in_batches)
    monkeypatch.setattr(db, "delete_supplier_chunks", lambda sid: None)
    monkeypatch.setattr(db, "insert_supplier_chunks", lambda rows: None)

    vault._index_vault_chunks("org-1", "SUP-1", _chunks("c1"))

    assert audits, "an embedding failure must still be audited"
    case_id, action, detail = audits[0]
    assert action == "chunk_embedding_failed"
    assert case_id is None, f"org id leaked into case_id: {case_id!r}"
    assert detail["document_id"] == "SUP-1"


def test_vault_chunks_degrade_to_text_only_when_embedding_fails(monkeypatch):
    """A failed embed stores the chunk text without a vector rather than dropping it."""
    from backend.core import extract as core_extract

    inserted: list[list[dict]] = []
    monkeypatch.setattr(core_extract, "_embed_batch_with_retry",
                        lambda batch: (_ for _ in ()).throw(RuntimeError("provider down")))
    monkeypatch.setattr(core_extract.db, "write_audit", lambda *a, **k: None)
    monkeypatch.setattr(vault, "_embed_in_batches", core_extract._embed_in_batches)
    monkeypatch.setattr(db, "delete_supplier_chunks", lambda sid: None)
    monkeypatch.setattr(db, "insert_supplier_chunks", lambda rows: inserted.append(rows))

    vault._index_vault_chunks("org-1", "SUP-1", _chunks("c1"))

    assert inserted[0][0]["text"] == "text c1"
    assert inserted[0][0]["embedding"] is None
    assert inserted[0][0]["org_id"] == "org-1"   # isolation key still set
