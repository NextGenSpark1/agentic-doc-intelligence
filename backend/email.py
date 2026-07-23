"""Transactional email via Resend — optional.

If RESEND_API_KEY is not set, all send functions return False and log nothing.
Switch RESEND_FROM_EMAIL from onboarding@resend.dev to your verified domain address
once a domain is connected in the Resend dashboard.
"""
from __future__ import annotations

from .config import get_settings

_ROLE_LABELS = {
    "org_admin": "Organisation Admin",
    "supervisor": "Supervisor",
    "member": "Member",
}


def send_invitation_email(
    to_email: str,
    org_name: str,
    role: str,
    invite_link: str,
    inviter_name: str = "Your team",
) -> bool:
    """Send a branded invite email. Returns True if sent, False if skipped (no API key)."""
    s = get_settings()
    if not s.resend_api_key:
        return False

    try:
        import resend  # lazy — only installed when email feature is in use
        resend.api_key = s.resend_api_key
    except ImportError:
        return False

    role_display = _ROLE_LABELS.get(role, role.replace("_", " ").title())

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #0F172A; margin: 0; padding: 40px 20px; }}
    .card {{ max-width: 520px; margin: 0 auto; background: #1E293B; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }}
    .header {{ background: #0E7C86; padding: 24px 32px; }}
    .brand {{ color: #fff; font-size: 11px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; }}
    .body {{ padding: 32px; }}
    .title {{ color: #F8FAFC; font-size: 20px; font-weight: 600; margin: 0 0 16px; line-height: 1.3; }}
    .text {{ color: #94A3B8; font-size: 14px; line-height: 1.7; margin: 0 0 24px; }}
    .pill {{ display: inline-block; background: rgba(14,124,134,0.18); color: #0E7C86; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 24px; border: 1px solid rgba(14,124,134,0.3); }}
    .btn {{ display: block; background: #1558D4; color: #fff !important; text-decoration: none; text-align: center; padding: 14px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; margin-bottom: 24px; }}
    .link-label {{ color: #475569; font-size: 11px; margin: 0 0 6px; }}
    .link-box {{ background: #0F172A; border: 1px solid #334155; border-radius: 6px; padding: 10px 14px; word-break: break-all; font-size: 11px; color: #64748B; font-family: monospace; margin-bottom: 28px; }}
    .footer {{ color: #334155; font-size: 11px; line-height: 1.6; border-top: 1px solid #334155; padding-top: 20px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="brand">NextGen Spark &mdash; Investigation Intelligence</div>
    </div>
    <div class="body">
      <p class="title">You&rsquo;ve been invited to join {org_name}</p>
      <span class="pill">{role_display}</span>
      <p class="text">
        <strong style="color:#F8FAFC">{inviter_name}</strong> has invited you to collaborate on
        <strong style="color:#F8FAFC">{org_name}</strong> as a
        <strong style="color:#F8FAFC">{role_display}</strong>
        on the NextGen Spark Investigation Intelligence platform.
      </p>
      <a href="{invite_link}" class="btn">Accept Invitation &rarr;</a>
      <p class="link-label">Or copy this link into your browser:</p>
      <div class="link-box">{invite_link}</div>
      <div class="footer">
        This invitation expires in 7 days. If you did not expect this email, you can safely ignore it.
        <br />NextGen Spark &mdash; For authorised personnel only.
      </div>
    </div>
  </div>
</body>
</html>"""

    try:
        resend.Emails.send({
            "from": s.resend_from_email,
            "to": [to_email],
            "subject": f"You're invited to join {org_name} on NextGen Spark",
            "html": html,
        })
        return True
    except Exception:
        return False
