"""Tendering access control: the org+role guard on every workspace route, and storage paths.

Two holes are covered here, both reachable by any authenticated user of the right org:

  1. Only the tender list, the tender page and Analyse applied the role rule. Every other route
     (delete, patch, requirements, evidence, documents, chat, bid decision) checked the org
     alone, so a member who was never assigned — or was removed from the team — could still
     drive them with nothing but the workspace id from the URL.
  2. `storage_path` arrives from the browser and is handed to a service-key download. Unchecked,
     it names any file in the bucket, including another org's tender.

The route tests go through the real router with a fake user and fake DB functions, because the
bug was never in the rule — `_can_access_workspace` was correct all along — but in which routes
remembered to call it. Only wiring proves that.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.tendering import routes
from backend.apps.tendering.routes import is_http_url, is_safe_storage_path, is_storage_path_within
from backend.core.auth import get_current_user
from backend.core.main import _safe_filename

ORG = "org-a"
OTHER_ORG = "org-b"
WS = "ws-1"


# ── Storage path validation ────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "ws-1/1726-tender.pdf",
    "ws-1/nested/folder/file.pdf",
    "general/1726-cidb certificate.pdf",
])
def test_ordinary_upload_paths_are_accepted(path):
    assert is_safe_storage_path(path)


@pytest.mark.parametrize("path", [
    "",                              # nothing at all
    " ws-1/f.pdf",                   # padded — would not match what we then store
    "/ws-1/f.pdf",                   # absolute
    "ws-1/../ws-2/f.pdf",            # traversal out of the workspace folder
    "../f.pdf",
    "ws-1//f.pdf",                   # empty segment
    "ws-1\\..\\ws-2\\f.pdf",         # backslash traversal
    "https://evil.example/f.pdf",    # not a bucket key at all
    "ws-1/f\npdf",                   # control character
])
def test_dangerous_paths_are_rejected(path):
    assert not is_safe_storage_path(path)


def test_long_paths_are_rejected():
    assert not is_safe_storage_path("ws-1/" + "a" * 600)


@pytest.mark.parametrize("url,ok", [
    ("https://project.supabase.co/storage/v1/object/public/tender-documents/ws-1/f.pdf", True),
    ("http://localhost:8000/f.pdf", True),
    ("javascript:alert(1)", False),
    ("data:text/html,<script>alert(1)</script>", False),
    ("  javascript:alert(1)", False),   # leading space must not sneak it past
    ("", False),
])
def test_only_http_links_count_as_document_urls(url, ok):
    assert is_http_url(url) is ok


@pytest.mark.parametrize("filename,expected", [
    ("report.pdf", "report.pdf"),
    ("../../other-case/secret.pdf", "secret.pdf"),   # cannot climb out of the case folder
    ("..\\..\\other-case\\secret.pdf", "secret.pdf"),
    ("", "upload"),
    ("..", "upload"),
    (None, "upload"),
])
def test_uploaded_filenames_stay_inside_their_case_folder(filename, expected):
    assert _safe_filename(filename) == expected


def test_path_must_sit_inside_the_named_folder():
    assert is_storage_path_within("ws-1/f.pdf", "ws-1")
    assert not is_storage_path_within("ws-2/f.pdf", "ws-1")
    # Prefix, not folder: `ws-10` must not pass as being inside `ws-1`.
    assert not is_storage_path_within("ws-10/f.pdf", "ws-1")
    # The folder itself is not a file in it.
    assert not is_storage_path_within("ws-1", "ws-1")
    assert not is_storage_path_within("ws-1/", "ws-1")
    assert not is_storage_path_within("ws-1/f.pdf", "")


# ── Route guards ───────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    """The real tendering router, with membership and DB reads faked.

    Returns a `(TestClient, calls)` pair; `calls` records the write/read helpers a route reaches
    only after its guard has passed, so a test can assert the guard stopped it.
    """
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u-member", "email": "m@x.com"}

    state = {
        "membership": {"org_id": ORG, "role": "member", "invited_by": "u-sup"},
        "workspace": {"id": WS, "org_id": ORG, "created_by": "u-other", "team_members": []},
        "team_ids": [],
    }
    calls: list[str] = []

    def record(name, result=None):
        def _fn(*_args, **_kwargs):
            calls.append(name)
            return result
        return _fn

    monkeypatch.setattr(routes, "_get_tendering_membership", lambda user: state["membership"])
    monkeypatch.setattr(routes, "list_team_member_ids", lambda org_id, user_id: state["team_ids"])
    monkeypatch.setattr(routes.db, "get_tendering_workspace",
                        lambda workspace_id: state["workspace"] if workspace_id == WS else None)

    monkeypatch.setattr(routes.db, "delete_workspace", record("delete_workspace"))
    monkeypatch.setattr(routes.db, "update_workspace", record("update_workspace", {"id": WS}))
    monkeypatch.setattr(routes.db, "list_workspace_requirements", record("list_requirements", []))
    monkeypatch.setattr(routes.db, "list_evidence_links", record("list_evidence_links", []))
    monkeypatch.setattr(routes.db, "list_workspace_documents", record("list_documents", []))
    monkeypatch.setattr(routes.db, "create_workspace_document",
                        record("create_workspace_document", {"id": "doc-1"}))
    monkeypatch.setattr(routes.db, "get_workspace_bid_decision",
                        record("get_bid_decision", {"decision": "bid"}))

    client = TestClient(app)
    client.state_for_test = state  # type: ignore[attr-defined]
    return client, calls


def _assign_member(client):
    client.state_for_test["workspace"]["team_members"] = ["u-member"]


def _call(api, method: str, path: str):
    """Send `method path`, with an empty body for the verbs that take one."""
    if method in ("patch", "post", "put"):
        return getattr(api, method)(path, json={})
    return getattr(api, method)(path)


@pytest.mark.parametrize("method,path,guarded_call", [
    ("delete", f"/tendering/workspaces/{WS}", "delete_workspace"),
    ("patch", f"/tendering/workspaces/{WS}", "update_workspace"),
    ("get", f"/tendering/workspaces/{WS}/requirements", "list_requirements"),
    ("get", f"/tendering/workspaces/{WS}/evidence-links", "list_evidence_links"),
    ("get", f"/tendering/workspaces/{WS}", "list_documents"),
    ("get", f"/tendering/workspaces/{WS}/bid-decision", "get_bid_decision"),
])
def test_unassigned_member_is_refused_on_every_workspace_route(client, method, path, guarded_call):
    api, calls = client
    response = _call(api, method, path)

    assert response.status_code == 404
    # The refusal must happen BEFORE the work: a 404 with the row already deleted is no guard.
    assert guarded_call not in calls


@pytest.mark.parametrize("method,path", [
    ("delete", f"/tendering/workspaces/{WS}"),
    ("get", f"/tendering/workspaces/{WS}/requirements"),
])
def test_assigned_member_is_allowed(client, method, path):
    api, _calls = client
    _assign_member(api)

    assert _call(api, method, path).status_code in (200, 204)


def test_creator_is_allowed_even_without_being_in_team_members(client):
    api, _calls = client
    api.state_for_test["workspace"]["created_by"] = "u-member"

    assert api.get(f"/tendering/workspaces/{WS}/requirements").status_code == 200


def test_org_admin_reaches_any_workspace_in_their_org(client):
    api, _calls = client
    api.state_for_test["membership"]["role"] = "org_admin"

    assert api.get(f"/tendering/workspaces/{WS}/requirements").status_code == 200


def test_supervisor_reaches_only_their_own_teams_workspaces(client):
    api, _calls = client
    api.state_for_test["membership"]["role"] = "supervisor"

    assert api.get(f"/tendering/workspaces/{WS}/requirements").status_code == 404

    api.state_for_test["team_ids"] = ["u-other"]  # the creator is now on their team
    assert api.get(f"/tendering/workspaces/{WS}/requirements").status_code == 200


def test_another_orgs_workspace_stays_invisible_to_an_admin(client):
    api, calls = client
    api.state_for_test["membership"]["role"] = "org_admin"
    api.state_for_test["workspace"]["org_id"] = OTHER_ORG

    assert api.delete(f"/tendering/workspaces/{WS}").status_code == 404
    assert "delete_workspace" not in calls


# ── storage_path on the routes that accept one ─────────────────────────────────

def test_document_registration_refuses_a_path_outside_the_workspace(client):
    api, calls = client
    _assign_member(api)

    response = api.post(f"/tendering/workspaces/{WS}/documents",
                        json={"name": "stolen.pdf", "storage_path": "ws-2/1726-their-tender.pdf"})

    assert response.status_code == 400
    assert "create_workspace_document" not in calls


def test_document_registration_accepts_the_workspaces_own_path(client, monkeypatch):
    api, calls = client
    _assign_member(api)
    monkeypatch.setattr(routes.db, "link_core_document_to_workspace_doc", lambda *a, **k: None)
    monkeypatch.setattr("backend.core.db_core.insert_document", lambda row: row)

    response = api.post(f"/tendering/workspaces/{WS}/documents",
                        json={"name": "rfp.pdf", "storage_path": f"{WS}/1726-rfp.pdf"})

    assert response.status_code == 201
    assert "create_workspace_document" in calls


def test_readiness_score_cannot_be_set_through_the_api(client, monkeypatch):
    """It is computed from requirements and evidence — a client-set 100% would be a lie.

    The readiness review still writes it through db.update_workspace, which this request body
    cannot reach.
    """
    api, _calls = client
    _assign_member(api)
    patches: list[dict] = []
    monkeypatch.setattr(routes.db, "update_workspace",
                        lambda workspace_id, patch: patches.append(patch) or {"id": workspace_id})

    api.patch(f"/tendering/workspaces/{WS}", json={"readiness_score": 100, "buyer": "Ministry"})

    assert patches and "readiness_score" not in patches[0]
    assert patches[0]["buyer"] == "Ministry"      # the rest of the edit still applies


def test_vault_upload_refuses_a_file_another_org_already_registered(client, monkeypatch):
    api, calls = client
    monkeypatch.setattr(routes.db, "get_supplier_document_by_storage_path",
                        lambda path: {"org_id": OTHER_ORG, "storage_path": path})
    monkeypatch.setattr(routes.db, "create_library_document",
                        lambda *a, **k: calls.append("create_library_document"))

    response = api.post("/tendering/library",
                        json={"title": "Their financials",
                              "storage_path": "general/1726-their-financials.pdf"})

    assert response.status_code == 409
    assert "create_library_document" not in calls


@pytest.mark.parametrize("url", [
    "javascript:fetch('/tendering/library').then(r=>r.text())",
    "JavaScript:alert(1)",     # case is not a defence
    "data:text/html,<script>alert(1)</script>",
])
def test_document_url_must_be_a_real_link(client, url):
    """The UI puts this value in `<iframe src>`; a script URL there runs for the next viewer."""
    api, calls = client
    _assign_member(api)

    response = api.post(f"/tendering/workspaces/{WS}/documents",
                        json={"name": "doc.pdf", "url": url})

    assert response.status_code == 400
    assert "create_workspace_document" not in calls


def test_vault_upload_allows_a_path_no_other_org_claims(client, monkeypatch):
    api, _calls = client
    monkeypatch.setattr(routes.db, "get_supplier_document_by_storage_path", lambda path: None)
    monkeypatch.setattr(routes.db, "create_library_document",
                        lambda org_id, data: {"doc_id": "lib-1", **data})
    monkeypatch.setattr(routes.db, "create_supplier_document", lambda org_id, data: {"ok": True})

    response = api.post("/tendering/library",
                        json={"title": "Our CIDB", "storage_path": "general/1726-our-cidb.pdf"})

    assert response.status_code == 201
