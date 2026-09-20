"""Replacing a vault document — the file the pipeline reads must follow the replacement.

The library row and the vault row hold different halves of one document: `library_documents`
carries the metadata and display url, `supplier_documents` carries the `storage_path` the
pipeline actually downloads. Replace only updated the first, so the preview showed the new file
while Extract re-read the old one and evidence matching kept proposing the old text — wrong
evidence on a live bid, with nothing in the UI to suggest it.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.tendering import routes
from backend.core.auth import get_current_user

ORG = "org-a"
OTHER_ORG = "org-b"
DOC = "lib-1"
NEW_PATH = "general/1726-renewed-cidb.pdf"


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u-1", "email": "u@x.com"}

    calls: list[tuple] = []
    monkeypatch.setattr(routes, "_get_tendering_membership",
                        lambda user: {"org_id": ORG, "role": "org_admin"})
    monkeypatch.setattr(routes.db, "list_library_documents",
                        lambda org_id: [{"doc_id": DOC, "title": "CIDB", "url": "https://x/old.pdf"}])
    monkeypatch.setattr(routes.db, "get_supplier_document_by_storage_path", lambda path: None)
    monkeypatch.setattr(routes.db, "update_library_document",
                        lambda doc_id, patch: calls.append(("update_library", doc_id, patch)) or {"doc_id": doc_id})
    monkeypatch.setattr(routes.db, "repoint_supplier_document",
                        lambda doc_id, path, filename=None: calls.append(("repoint", doc_id, path, filename)))
    return TestClient(app), calls


def test_replacing_the_file_repoints_the_vault_row(client):
    api, calls = client

    response = api.patch(f"/tendering/library/{DOC}",
                         json={"url": "https://x/new.pdf", "filename": "renewed.pdf",
                               "storage_path": NEW_PATH})

    assert response.status_code == 200
    assert ("repoint", DOC, NEW_PATH, "renewed.pdf") in calls


def test_metadata_only_edits_leave_the_vault_alone(client):
    """Renaming a document must not invalidate its extraction."""
    api, calls = client

    api.patch(f"/tendering/library/{DOC}", json={"title": "CIDB G7 (renewed)"})

    assert [call[0] for call in calls] == ["update_library"]


def test_a_replace_carrying_only_the_new_path_is_accepted(client):
    """There is nothing to write to the library row in that case — it is not an error."""
    api, calls = client

    response = api.patch(f"/tendering/library/{DOC}", json={"storage_path": NEW_PATH})

    assert response.status_code == 200
    assert [call[0] for call in calls] == ["repoint"]


def test_a_path_registered_to_another_org_is_refused(client, monkeypatch):
    api, calls = client
    monkeypatch.setattr(routes.db, "get_supplier_document_by_storage_path",
                        lambda path: {"org_id": OTHER_ORG, "storage_path": path})

    response = api.patch(f"/tendering/library/{DOC}", json={"storage_path": NEW_PATH})

    assert response.status_code == 409
    assert calls == []


@pytest.mark.parametrize("path", ["../other/f.pdf", "/absolute/f.pdf", "https://evil/f.pdf"])
def test_an_unsafe_replacement_path_is_refused(client, path):
    api, calls = client

    assert api.patch(f"/tendering/library/{DOC}", json={"storage_path": path}).status_code == 400
    assert calls == []


def test_repoint_clears_the_old_index_and_requires_re_extraction(monkeypatch):
    """The unit behind the route: old chunks go, status returns to uploaded."""
    from backend.apps.tendering import db

    actions: list[tuple] = []
    monkeypatch.setattr(db, "get_supplier_document_by_library_doc",
                        lambda library_doc_id: {"supplier_document_id": "sup-1"})
    monkeypatch.setattr(db, "delete_supplier_chunks",
                        lambda sid: actions.append(("delete_chunks", sid)))
    monkeypatch.setattr(db, "update_supplier_document",
                        lambda sid, patch: actions.append(("update", sid, patch)) or patch)

    db.repoint_supplier_document(DOC, NEW_PATH, "renewed.pdf")

    assert actions[0] == ("delete_chunks", "sup-1")
    _, _, patch = actions[1]
    assert patch["storage_path"] == NEW_PATH
    assert patch["extraction_status"] == "uploaded"   # must be re-extracted before it counts
    assert patch["filename"] == "renewed.pdf"


def test_repoint_is_a_no_op_when_there_is_no_vault_entry(monkeypatch):
    from backend.apps.tendering import db

    monkeypatch.setattr(db, "get_supplier_document_by_library_doc", lambda library_doc_id: None)

    assert db.repoint_supplier_document(DOC, NEW_PATH) is None
