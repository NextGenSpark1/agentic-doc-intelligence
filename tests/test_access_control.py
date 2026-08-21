"""Case access-control matrix — the org/role/owner isolation enforced by _assert_case_access.

This is security-critical: a hole here leaks one tenant's forensic evidence to another. The
function is pure (raises HTTPException or returns None), so it's tested directly without a DB.
"""
import pytest
from fastapi import HTTPException

from backend.core.access import assert_case_access as _assert_case_access


def _denied(case, user_id, membership=None):
    """True if access is refused (403 raised), False if allowed."""
    try:
        _assert_case_access(case, user_id, membership)
        return False
    except HTTPException as e:
        assert e.status_code == 403
        return True


# ── Legacy (no org membership) — owner_id isolation ─────────────────────────

def test_legacy_owner_can_access_own_case():
    case = {"owner_id": "u1"}
    assert not _denied(case, "u1", membership=None)


def test_legacy_non_owner_is_denied():
    case = {"owner_id": "u1"}
    assert _denied(case, "u2", membership=None)


def test_legacy_ownerless_case_is_open():
    # Pre-isolation cases (owner_id NULL) stay visible — documented safe-migration behaviour.
    assert not _denied({"owner_id": None}, "anyone", membership=None)


# ── Org isolation ───────────────────────────────────────────────────────────

def test_case_in_another_org_is_denied_even_for_admin():
    case = {"org_id": "orgA", "created_by": "u1"}
    membership = {"org_id": "orgB", "role": "org_admin"}
    assert _denied(case, "u9", membership)


def test_org_admin_sees_any_case_in_their_org():
    case = {"org_id": "orgA", "created_by": "someone_else"}
    membership = {"org_id": "orgA", "role": "org_admin"}
    assert not _denied(case, "admin", membership)


# ── Supervisor scope: only their own cases ──────────────────────────────────

def test_supervisor_can_access_case_they_created():
    case = {"org_id": "orgA", "created_by": "sup1"}
    membership = {"org_id": "orgA", "role": "supervisor"}
    assert not _denied(case, "sup1", membership)


def test_supervisor_denied_another_supervisors_case():
    case = {"org_id": "orgA", "created_by": "sup2"}
    membership = {"org_id": "orgA", "role": "supervisor"}
    assert _denied(case, "sup1", membership)


# ── Member scope: only their supervisor's cases ─────────────────────────────

def test_member_can_access_their_supervisors_case():
    case = {"org_id": "orgA", "created_by": "sup1"}
    membership = {"org_id": "orgA", "role": "member", "invited_by": "sup1"}
    assert not _denied(case, "m1", membership)


def test_member_denied_a_different_supervisors_case():
    case = {"org_id": "orgA", "created_by": "sup2"}
    membership = {"org_id": "orgA", "role": "member", "invited_by": "sup1"}
    assert _denied(case, "m1", membership)
