"""Bid / no-bid recommendation.

This is the most advisory thing in the product and the easiest to misread as a verdict, so the
tests are mostly about what it is not allowed to do: outrank the readiness report, produce a
recommendation with no argument behind it, invent a second score, or touch the team's own
decision on the workspace.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.tendering import db, routes
from backend.apps.tendering.pipeline import bid_decision
from backend.core import llm_reasoning, ratelimit
from backend.core.auth import get_current_user

WS = "ws-1"


def _report(blocked=False, **overrides):
    report = {
        "score": 0.75, "submission_blocked": blocked,
        "satisfied": 6, "total": 8, "mandatory_satisfied": 3, "mandatory_total": 4,
        "blocking_reasons": ["No evidence attached for mandatory requirement: CIDB G7"] if blocked else [],
        "blockers": 1 if blocked else 0,
        "gaps": [{"gap_type": "mandatory_requirement_unmet", "severity": "blocker",
                  "message": "No evidence attached for mandatory requirement: CIDB G7"}],
    }
    report.update(overrides)
    return report


def _answer(**overrides):
    answer = {
        "recommendation": "bid",
        "rationale": "Six of eight requirements are satisfied and the deadline is six weeks out.",
        "strengths": ["CIDB G7 certificate on file", "Turnover above the stated threshold"],
        "risks": ["ISO 27001 expires before closing"],
    }
    answer.update(overrides)
    return answer


# ── validation ─────────────────────────────────────────────────────────────────

def test_a_usable_recommendation_is_kept():
    kept = bid_decision.validate_recommendation(_answer(), _report())

    assert kept["recommendation"] == "bid"
    assert len(kept["strengths"]) == 2


def test_a_recommendation_without_a_rationale_is_dropped():
    """Rule 2 applied to advice: the argument is the product, not the verdict."""
    assert bid_decision.validate_recommendation(_answer(rationale="  "), _report()) is None


@pytest.mark.parametrize("value", ["maybe", "", None, "BID!", 42])
def test_an_unrecognised_recommendation_is_dropped(value):
    assert bid_decision.validate_recommendation(_answer(recommendation=value), _report()) is None


@pytest.mark.parametrize("raw", [None, [], "bid", {}])
def test_malformed_output_is_dropped(raw):
    assert bid_decision.validate_recommendation(raw, _report()) is None


def test_bid_is_downgraded_when_the_report_says_submission_is_blocked():
    """The model does not get to wave a blocker through, but its reasoning is still shown."""
    kept = bid_decision.validate_recommendation(_answer(), _report(blocked=True))

    assert kept["recommendation"] == "pending"
    assert "blocking issues" in kept["rationale"]
    assert "Six of eight requirements" in kept["rationale"]


def test_no_bid_stands_even_when_nothing_is_blocked():
    kept = bid_decision.validate_recommendation(
        _answer(recommendation="no_bid", rationale="The contract value is below our floor."),
        _report(),
    )
    assert kept["recommendation"] == "no_bid"


def test_long_lists_are_trimmed():
    kept = bid_decision.validate_recommendation(
        _answer(strengths=[f"strength {i}" for i in range(20)]), _report())

    assert len(kept["strengths"]) == 6


# ── the fallback ───────────────────────────────────────────────────────────────

def test_without_the_model_it_never_recommends_bidding():
    fallback = bid_decision.deterministic_recommendation(_report())

    assert fallback["recommendation"] == "pending"
    assert "without the AI advisor" in fallback["rationale"]


def test_the_fallback_still_carries_the_blockers():
    fallback = bid_decision.deterministic_recommendation(_report(blocked=True))

    assert fallback["risks"] == ["No evidence attached for mandatory requirement: CIDB G7"]


# ── the run ────────────────────────────────────────────────────────────────────

@pytest.fixture
def generate(monkeypatch):
    saved: list[dict] = []
    audits: list[tuple] = []
    state = {"report": _report(), "answer": _answer()}

    monkeypatch.setattr(db, "get_tendering_workspace",
                        lambda ws: {"id": ws, "org_id": "org-1", "title": "Fibre rollout",
                                    "closing_date": "2026-11-01", "bid_decision": "pending"})
    monkeypatch.setattr(db, "list_workspace_requirements_raw", lambda ws: [])
    monkeypatch.setattr(db, "list_evidence_links", lambda ws: [])
    monkeypatch.setattr(db, "list_core_documents_for_workspace", lambda ws: [])
    monkeypatch.setattr(db, "list_library_documents", lambda org: [])
    monkeypatch.setattr(db, "update_workspace",
                        lambda ws, patch: pytest.fail(f"must not touch the workspace: {patch}"))
    monkeypatch.setattr(db, "save_workspace_bid_decision",
                        lambda ws, record: saved.append(record) or record)
    monkeypatch.setattr(db, "write_workspace_audit",
                        lambda ws, actor, action, detail=None: audits.append((action, detail)))
    monkeypatch.setattr(bid_decision, "_payload",
                        lambda workspace, report, **_: {"r": report})
    from backend.apps.tendering.pipeline import readiness_review
    monkeypatch.setattr(readiness_review, "build_report", lambda *a, **k: state["report"])
    monkeypatch.setattr(llm_reasoning, "ask", lambda *a, **k: state["answer"])
    return state, saved, audits


def test_the_recommendation_is_stored_with_the_reports_score(generate):
    state, saved, _audits = generate

    result = bid_decision.generate(WS)

    assert saved[0]["recommendation"] == "bid"
    assert saved[0]["score"] == 75          # the report's 0.75, not anything the model said
    assert result["rationale"].startswith("Six of eight")


def test_the_teams_own_decision_is_never_touched(generate):
    """Rule 3: the workspace's bid_decision belongs to the person who clicks it."""
    state, saved, _audits = generate

    bid_decision.generate(WS)   # the update_workspace stub fails the test if it is called

    assert "bid_decision" not in saved[0]


def test_an_unusable_answer_falls_back_rather_than_failing(generate):
    state, saved, audits = generate
    state["answer"] = {"recommendation": "bid"}      # no rationale

    bid_decision.generate(WS)

    assert saved[0]["recommendation"] == "pending"
    assert audits[0][1]["source"] == "deterministic"


def test_an_unavailable_model_falls_back(generate):
    state, saved, _audits = generate
    state["answer"] = None

    bid_decision.generate(WS)

    assert saved[0]["recommendation"] == "pending"


# ── the route ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    ratelimit.reset()
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u-1", "email": "u@x.com"}
    monkeypatch.setattr(routes, "_get_tendering_membership",
                        lambda user: {"org_id": "org-1", "role": "org_admin"})
    monkeypatch.setattr(routes.db, "get_tendering_workspace",
                        lambda ws: {"id": ws, "org_id": "org-1"} if ws == WS else None)
    yield TestClient(app)
    ratelimit.reset()


def test_the_endpoint_returns_the_stored_recommendation(client, monkeypatch):
    monkeypatch.setattr(bid_decision, "generate",
                        lambda ws: {"workspace_id": ws, "recommendation": "no_bid", "score": 20,
                                    "rationale": "The deadline has passed.", "strengths": [],
                                    "risks": ["Closing date passed"]})

    response = client.post(f"/tendering/workspaces/{WS}/generate-bid-decision")

    assert response.status_code == 201
    assert response.json()["recommendation"] == "no_bid"


def test_a_workspace_the_caller_cannot_reach_is_a_404(client):
    assert client.post("/tendering/workspaces/ws-other/generate-bid-decision").status_code == 404


def test_a_generation_failure_is_reported_rather_than_a_500(client, monkeypatch):
    audits: list[str] = []

    def boom(_ws):
        raise RuntimeError("openai down")

    monkeypatch.setattr(bid_decision, "generate", boom)
    monkeypatch.setattr(routes.db, "write_workspace_audit",
                        lambda ws, actor, action, detail=None: audits.append(action))

    response = client.post(f"/tendering/workspaces/{WS}/generate-bid-decision")

    assert response.status_code == 502
    assert "openai" not in response.json()["detail"]      # the provider's noise stays in the logs
    assert audits == ["bid_decision_generation_failed"]
