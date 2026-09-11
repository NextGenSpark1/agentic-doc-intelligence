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
