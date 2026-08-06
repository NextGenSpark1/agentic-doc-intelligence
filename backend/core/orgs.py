"""Multi-tenancy org management — platform admin and org-level endpoints."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db_core as db, email as mail
from .auth import get_current_user
from .config import get_settings

router = APIRouter()


def _is_platform_admin(user: dict) -> bool:
    return user.get("email", "").lower() in [e.lower() for e in get_settings().platform_admin_emails]


def _require_platform_admin(user: dict = Depends(get_current_user)) -> dict:
    if not _is_platform_admin(user):
        raise HTTPException(403, "Platform admin access required")
    return user


def _get_membership(user: dict) -> dict:
    m = db.get_user_membership(user["user_id"])
    if not m:
        raise HTTPException(403, "Not a member of any organisation")
    return m


# ── Pydantic models ────────────────────────────────────────────────────────

class CreateOrgBody(BaseModel):
    name: str
    plan: str = "trial"
    admin_email: str
    admin_name: str | None = None


class InviteBody(BaseModel):
    email: str
    role: str
    name: str | None = None


class AcceptInviteBody(BaseModel):
    token: str


# ── Platform admin endpoints ───────────────────────────────────────────────

@router.get("/platform/orgs")
async def platform_list_orgs(user: dict = Depends(_require_platform_admin)):
    """List all orgs with metadata — platform admin only, no case content."""
    orgs = await asyncio.to_thread(db.list_orgs)
    result = []
    for org in orgs:
        members = await asyncio.to_thread(db.list_org_members, org["org_id"])
        case_count = await asyncio.to_thread(db.list_org_cases_count, org["org_id"])
        result.append({
            "org_id": org["org_id"],
            "name": org["name"],
            "plan": org["plan"],
            "created_at": org["created_at"],
            "member_count": len(members),
            "case_count": case_count,
            "members": [
                {
                    "email": m["email"],
                    "role": m["role"],
                    "full_name": m.get("full_name"),
                    "joined_at": m["joined_at"],
                }
                for m in members
            ],
        })
    return {"orgs": result}


@router.post("/platform/orgs", status_code=201)
async def platform_create_org(body: CreateOrgBody, user: dict = Depends(_require_platform_admin)):
    """Create a new organisation and send first invite to org admin — platform admin only."""
    org_id = str(uuid.uuid4())[:8].upper()
    org = await asyncio.to_thread(db.create_org, org_id, body.name, body.plan, user["user_id"])
    invite = await asyncio.to_thread(db.create_invitation, org_id, body.admin_email, "org_admin", user["user_id"])
    invite_link = f"/invite/{invite['token']}"
    email_sent = await asyncio.to_thread(
        mail.send_invitation_email,
        body.admin_email, body.name, "org_admin", invite_link,
        body.admin_name or "NextGen Spark",
    )
    return {
        "org": org,
        "invite_token": invite["token"],
        "invite_link": invite_link,
        "email_sent": email_sent,
    }


@router.delete("/platform/orgs/{org_id}/members/{user_id}", status_code=204)
async def platform_remove_member(org_id: str, user_id: str, user: dict = Depends(_require_platform_admin)):
    await asyncio.to_thread(db.remove_org_member, org_id, user_id)


# ── Org member endpoints ───────────────────────────────────────────────────

@router.get("/orgs/me")
async def get_my_org(user: dict = Depends(get_current_user)):
    """Return current user's org membership and org details."""
    if _is_platform_admin(user):
        return {"role": "platform_admin", "org": None}
    m = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    if not m:
        return {"role": None, "org": None}
    org = m.get("organisations") or {}
    return {
        "role": m["role"],
        "org_id": m["org_id"],
        "org_name": org.get("name") if isinstance(org, dict) else None,
        "org_plan": org.get("plan") if isinstance(org, dict) else None,
    }


@router.get("/orgs/{org_id}/members")
async def list_members(org_id: str, user: dict = Depends(get_current_user)):
    m = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    if not m or m["org_id"] != org_id:
        raise HTTPException(403, "access denied")
    members = await asyncio.to_thread(db.list_org_members, org_id)
    return {"members": members}


@router.post("/orgs/{org_id}/invite", status_code=201)
async def invite_member(org_id: str, body: InviteBody, user: dict = Depends(get_current_user)):
    m = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    if not m or m["org_id"] != org_id:
        raise HTTPException(403, "access denied")

    # Role-based invite permission
    allowed_roles: list[str] = []
    if m["role"] == "org_admin":
        allowed_roles = ["org_admin", "supervisor", "member"]
    elif m["role"] == "supervisor":
        allowed_roles = ["member"]
    else:
        raise HTTPException(403, "Members cannot invite others")

    if body.role not in allowed_roles:
        raise HTTPException(403, f"You cannot invite someone with role '{body.role}'")

    try:
        invite = await asyncio.to_thread(db.create_invitation, org_id, body.email, body.role, user["user_id"])
    except Exception:
        raise HTTPException(409, "An invitation for this email already exists in this org")

    invite_link = f"/invite/{invite['token']}"
    org = await asyncio.to_thread(db.get_org, org_id)
    org_name = org["name"] if org else org_id
    inviter_name = user.get("full_name") or user.get("email", "Your team")
    email_sent = await asyncio.to_thread(
        mail.send_invitation_email,
        body.email, org_name, body.role, invite_link, inviter_name,
    )

    return {
        "invitation_id": str(invite["invitation_id"]),
        "invite_token": invite["token"],
        "invite_link": invite_link,
        "email": body.email,
        "role": body.role,
        "email_sent": email_sent,
    }


@router.delete("/orgs/{org_id}/members/{member_user_id}", status_code=204)
async def remove_member(org_id: str, member_user_id: str, user: dict = Depends(get_current_user)):
    m = await asyncio.to_thread(db.get_user_membership, user["user_id"])
    if not m or m["org_id"] != org_id or m["role"] != "org_admin":
        raise HTTPException(403, "Only org admin can remove members")
    if member_user_id == user["user_id"]:
        raise HTTPException(400, "Cannot remove yourself")
    await asyncio.to_thread(db.remove_org_member, org_id, member_user_id)


# ── Invitation endpoints ───────────────────────────────────────────────────

@router.get("/invitations/{token}")
async def get_invitation(token: str):
    """Public — returns invite details so the accept page can show org name + role."""
    invite = await asyncio.to_thread(db.get_invitation_by_token, token)
    if not invite:
        raise HTTPException(404, "Invitation not found")
    if invite.get("accepted_at"):
        raise HTTPException(410, "Invitation already accepted")
    expires = invite.get("expires_at", "")
    if expires and datetime.fromisoformat(expires.replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise HTTPException(410, "Invitation has expired")
    org = invite.get("organisations") or {}
    return {
        "org_id": invite["org_id"],
        "org_name": org.get("name") if isinstance(org, dict) else invite["org_id"],
        "email": invite["email"],
        "role": invite["role"],
        "expires_at": invite["expires_at"],
    }


@router.post("/invitations/{token}/accept", status_code=200)
async def accept_invitation(token: str, user: dict = Depends(get_current_user)):
    """Authenticated user accepts an invite — they are added to the org."""
    invite = await asyncio.to_thread(db.get_invitation_by_token, token)
    if not invite:
        raise HTTPException(404, "Invitation not found")
    if invite.get("accepted_at"):
        raise HTTPException(410, "Invitation already accepted")
    expires = invite.get("expires_at", "")
    if expires and datetime.fromisoformat(expires.replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise HTTPException(410, "Invitation has expired")

    # Bind the invite to its intended recipient. Invite links are emailed and can be forwarded
    # or leaked; without this, anyone holding a valid token could join the org with the invited
    # role. The accepting user's authenticated email must match the address the invite was sent to.
    invited_email = (invite.get("email") or "").strip().lower()
    user_email = (user.get("email") or "").strip().lower()
    if not user_email or user_email != invited_email:
        raise HTTPException(403, "This invitation was issued to a different email address.")

    # Check not already a member
    existing = await asyncio.to_thread(db.get_org_member, invite["org_id"], user["user_id"])
    if existing:
        raise HTTPException(409, "Already a member of this organisation")

    await asyncio.to_thread(
        db.add_org_member,
        invite["org_id"], user["user_id"], user["email"],
        invite["role"], invite["invited_by"],
        user.get("full_name"),
    )
    await asyncio.to_thread(db.accept_invitation, token)

    org = await asyncio.to_thread(db.get_org, invite["org_id"])
    return {
        "org_id": invite["org_id"],
        "org_name": org["name"] if org else invite["org_id"],
        "role": invite["role"],
    }
