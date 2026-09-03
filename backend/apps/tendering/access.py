"""Tender-access enforcement.

Mirrors core's `load_case_or_403`, against the `tenders` table. The isolation *rules* are not
duplicated — `assert_case_access` from core is reused, because the org/role/owner logic is
workspace-generic and having two copies would mean two places for a tenancy bug to hide.

EVERY tender-scoped route must go through `load_tender_or_403`. A route that only checks
`document.tender_id == tender_id` leaks another org's bid documents to anyone who knows an id.
"""
from __future__ import annotations

import asyncio

from fastapi import HTTPException

from backend.core import db_core as core_db
from backend.core.access import assert_case_access


async def load_tender_or_403(tender_id: str, user: dict) -> dict:
    """Fetch a tender and enforce that `user` may access it.

    404 if it does not exist, 403 if the user's org/role/owner scope excludes it.
    """
    from . import db

    workspace = await asyncio.to_thread(db.get_tendering_workspace, tender_id)
    if not workspace:
        raise HTTPException(404, "workspace not found")
    membership = await asyncio.to_thread(core_db.get_user_membership, user["user_id"])
    assert_case_access(workspace, user["user_id"], membership)
    return workspace


async def assert_org_access(org_id: str | None, user: dict) -> str:
    """Enforce that `user` belongs to `org_id`, and return the org they may act in.

    The supplier vault is org-scoped rather than tender-scoped, so vault routes cannot lean on
    `load_tender_or_403`. This is the vault's isolation boundary: without it, a vault id would
    be enough to read another company's certificates and financials.
    """
    membership = await asyncio.to_thread(core_db.get_user_membership, user["user_id"])
    if not membership or not membership.get("org_id"):
        raise HTTPException(403, "an organisation membership is required to use the supplier vault")
    if org_id is not None and org_id != membership["org_id"]:
        raise HTTPException(403, "access denied")
    return membership["org_id"]
