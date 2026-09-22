"""Rate limits on the endpoints that spend money.

Each analysis is an OpenAI bill and each extraction a LandingAI credit, so the limit is a
spending cap first and a load control second: it has to hold against a retry loop as much as
against a person clicking twice.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.tendering import routes
from backend.core import ratelimit
from backend.core.auth import get_current_user
from backend.core.config import get_settings


@pytest.fixture(autouse=True)
def _clean_windows():
    ratelimit.reset()
    yield
    ratelimit.reset()


# ── the window itself ──────────────────────────────────────────────────────────

def test_calls_inside_the_limit_are_allowed():
    assert all(ratelimit._allow("k", max_calls=3, per_seconds=60, now=100.0) for _ in range(3))


def test_the_call_over_the_limit_is_refused():
    for _ in range(3):
        ratelimit._allow("k", 3, 60, now=100.0)

    assert ratelimit._allow("k", 3, 60, now=100.0) is False


def test_the_window_slides_rather_than_resetting_on_the_hour():
    for _ in range(3):
        ratelimit._allow("k", 3, 60, now=100.0)

    assert ratelimit._allow("k", 3, 60, now=159.0) is False   # still inside the minute
    assert ratelimit._allow("k", 3, 60, now=161.0) is True    # the first three have aged out


def test_one_users_spending_does_not_consume_anothers():
    for _ in range(3):
        ratelimit._allow("analysis:user-a", 3, 60, now=100.0)

    assert ratelimit._allow("analysis:user-b", 3, 60, now=100.0) is True


def test_limits_do_not_bleed_between_actions():
    for _ in range(3):
        ratelimit._allow("analysis:user-a", 3, 60, now=100.0)

    assert ratelimit._allow("chat:user-a", 3, 60, now=100.0) is True


# ── applied to a real route ────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u-1", "email": "u@x.com"}

    monkeypatch.setattr(routes, "_get_tendering_membership",
                        lambda user: {"org_id": "org-1", "role": "org_admin"})
    monkeypatch.setattr(routes.db, "get_tendering_workspace",
                        lambda ws: {"id": ws, "org_id": "org-1", "stage": "preparing"})
    # No documents extracted yet: chat answers immediately, with no model call.
    monkeypatch.setattr(routes.db, "match_workspace_chunks", lambda *a, **k: [])
    from backend.core import llm
    monkeypatch.setattr(llm, "embed", lambda texts: [[0.1] * 4 for _ in texts])
    return TestClient(app)


def test_chat_stops_after_the_minute_allowance(client):
    statuses = [client.post("/tendering/workspaces/ws-1/chat", json={"message": "hi"}).status_code
                for _ in range(31)]

    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


def test_the_refusal_says_what_the_limit_is(client):
    for _ in range(30):
        client.post("/tendering/workspaces/ws-1/chat", json={"message": "hi"})

    detail = client.post("/tendering/workspaces/ws-1/chat", json={"message": "hi"}).json()["detail"]

    assert "30" in detail and "chat" in detail


def test_limiting_can_be_switched_off_for_local_work(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", False, raising=False)
    monkeypatch.setattr(ratelimit, "get_settings", lambda: settings)

    statuses = [client.post("/tendering/workspaces/ws-1/chat", json={"message": "hi"}).status_code
                for _ in range(35)]

    assert set(statuses) == {200}
