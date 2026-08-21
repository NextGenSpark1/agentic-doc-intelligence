"""Case-access enforcement (core, shared by every product router).

Lives in its own module so both the core app and each product's router can import it without a
circular dependency on core.main. EVERY case-scoped route must go through `load_case_or_403`.
"""
from __future__ import annotations

import asyncio

from fastapi import HTTPException

from backend.core import db_core as db


def assert_case_access(case: dict, user_id: str, membership: dict | None = None) -> None:
    """Raise 403 if the requesting user should not access this case.

    With team isolation: org_admin sees all org cases; supervisor sees their own;
    member sees their supervisor's. Without membership (no org yet), falls back to owner_id.
    """
    if membership:
        if case.get("org_id") != membership.get("org_id"):
            raise HTTPException(403, "access denied")
        role = membership.get("role")
        if role == "org_admin":
            return
        case_creator = case.get("created_by")
        if role == "supervisor":
            if case_creator and case_creator != user_id:
                raise HTTPException(403, "access denied")
        elif role == "member":
            supervisor_id = membership.get("invited_by")
            if case_creator and case_creator != supervisor_id:
                raise HTTPException(403, "access denied")
        return
    # Legacy: no org membership yet — use owner_id isolation
    owner = case.get("owner_id")
    if owner and owner != user_id:
        raise HTTPException(403, "access denied")


async def load_case_or_403(case_id: str, user: dict) -> dict:
    """Fetch a case and enforce that `user` may access it. 404 if it doesn't exist, 403 if the
    user's org/role/owner scope excludes it. EVERY case-scoped route must go through this — a
    route that only checks `document.case_id == case_id` leaks other tenants' evidence to anyone
    who knows a case_id."""
    case = await asyncio.to_thread(db.get_case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    membership = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    assert_case_access(case, user["user_id"], membership)
    return case
