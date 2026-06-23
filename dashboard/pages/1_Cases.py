import streamlit as st
import requests
from datetime import datetime, timezone

st.set_page_config(
    page_title="Cases · Investigation Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.styles import inject_styles, get_cases_page_css  # noqa: E402

API_BASE = "http://localhost:8000"

inject_styles("Cases")


# ── data helpers ──────────────────────────────────────────────────

def fetch_cases():
    try:
        r = requests.get(f"{API_BASE}/cases", timeout=5)
        r.raise_for_status()
        return r.json(), None
    except Exception as exc:
        return None, str(exc)


def create_case(payload: dict):
    try:
        r = requests.post(f"{API_BASE}/cases", json=payload, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except Exception as exc:
        return None, str(exc)


def _relative_time(iso):
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        secs = (datetime.now(timezone.utc) - dt).total_seconds()
        if secs < 3600:
            return f"{int(secs / 60)}m ago"
        if secs < 86400:
            return f"{int(secs / 3600)}h ago"
        return f"{int(secs / 86400)}d ago"
    except Exception:
        return "—"


def _risk_color(score):
    if score >= 70:
        return "#B4232A"
    if score >= 40:
        return "#C77A12"
    if score > 0:
        return "#0E7C86"
    return "#878E99"


def _status_badge(status):
    mapping = {
        "pending review": ("badge-amber", "Pending Review"),
        "report ready":   ("badge-green", "Report Ready"),
        "extracting":     ("badge-teal",  "Extracting"),
        "active":         ("badge-teal",  "Active"),
        "intake":         ("badge-grey",  "Intake"),
        "archived":       ("badge-grey",  "Archived"),
    }
    key = (status or "intake").strip().lower()
    cls, label = mapping.get(key, ("badge-grey", status or "Intake"))
    return f'<span class="badge {cls}">{label}</span>'


def _is_stale(case):
    ref = case.get("last_analysed_at") or case.get("created_at")
    if not ref:
        return False
    try:
        dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days >= 3
    except Exception:
        return False


def _fmt_type(ct):
    return (ct or "").replace("_", " ").title()


def _fmt_date(iso):
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y")
    except Exception:
        return iso[:10]


# ── fetch ─────────────────────────────────────────────────────────

data, error = fetch_cases()
cases = (data or {}).get("cases", [])
stats = (data or {}).get("stats", {})

count_all     = len(cases)
count_active  = sum(1 for c in cases if (c.get("status") or "").lower() not in ("archived",))
count_pending = sum(1 for c in cases if (c.get("status") or "").lower() == "pending review")
count_archived = sum(1 for c in cases if (c.get("status") or "").lower() == "archived")

open_cases       = stats.get("open_cases", count_active)
findings_pending = stats.get("findings_pending_review", 0)


st.markdown(get_cases_page_css(), unsafe_allow_html=True)


# ── toolbar (dynamic pill counts) ────────────────────────────────

st.markdown(f"""<div class="page-wrap" style="padding-bottom:0;">
<div class="toolbar">
<h3 class="toolbar-title">Cases</h3>
<div class="spacer"></div>
<span class="filter-pill-active">All <span class="pill-count">{count_all}</span></span>
<span class="filter-pill">Active <span class="pill-count">{count_active}</span></span>
<span class="filter-pill">Pending Review <span class="pill-count">{count_pending}</span></span>
<span class="filter-pill">Archived <span class="pill-count">{count_archived}</span></span>
</div>
</div>""", unsafe_allow_html=True)


# ── new case form ─────────────────────────────────────────────────

with st.expander("+ New Case"):
    with st.form("new_case_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            title     = st.text_input("Case Title *")
            case_type = st.selectbox("Case Type", [
                "procurement_fraud",
                "payment_tracing",
                "conflict_of_interest",
                "audit",
            ])
        with col_b:
            lead       = st.text_input("Lead Investigator *")
            allegation = st.text_area("Allegation Summary", height=96)
        submitted = st.form_submit_button("Create Case")
        if submitted:
            if not title.strip() or not lead.strip():
                st.warning("Case Title and Lead Investigator are required.")
            else:
                result, err = create_case({
                    "title": title.strip(),
                    "case_type": case_type,
                    "lead_investigator": lead.strip(),
                    "allegation_summary": allegation.strip(),
                })
                if err:
                    st.error(f"Could not create case: {err}")
                else:
                    st.success(f"Case {result['case_id']} created.")
                    st.rerun()


# ── build table rows ──────────────────────────────────────────────

if error:
    rows_html = (
        f'<tr><td colspan="7" style="text-align:center;padding:40px 16px;color:#878E99;">'
        f'Backend unavailable — {error}</td></tr>'
    )
elif not cases:
    rows_html = (
        '<tr><td colspan="7" style="text-align:center;padding:40px 16px;color:#878E99;">'
        'No cases yet. Use &ldquo;+ New Case&rdquo; above to create the first one.</td></tr>'
    )
else:
    parts = []
    for c in cases:
        stale    = _is_stale(c)
        row_cls  = "stale-row" if stale else ""
        score    = int(c.get("risk_score") or 0)
        color    = _risk_color(score)
        stale_badge = '<span class="badge-stale">Stale</span>' if stale else ""
        activity = _relative_time(c.get("last_analysed_at") or c.get("created_at"))
        parts.append(
            f'<tr class="{row_cls}">'
            f'<td><span class="case-id">{c["case_id"]}</span></td>'
            f'<td>'
            f'<div class="title-main">{c.get("title", "")}</div>'
            f'<div class="title-sub">Lead: {c.get("lead_investigator", "—")} · Created {_fmt_date(c.get("created_at"))}</div>'
            f'</td>'
            f'<td><span class="type-badge">{_fmt_type(c.get("case_type", ""))}</span></td>'
            f'<td>{_status_badge(c.get("status", ""))}</td>'
            f'<td><span class="ts">—</span></td>'
            f'<td>'
            f'<div class="risk-wrap">'
            f'<div class="risk-track"><div class="risk-fill" style="width:{score}%;background:{color};"></div></div>'
            f'<span class="risk-num" style="color:{color};">{score}</span>'
            f'</div>'
            f'</td>'
            f'<td><span class="ts">{activity}</span>{stale_badge}</td>'
            f'</tr>'
        )
    rows_html = "\n".join(parts)


# ── search + stat cards + table (dynamic) ────────────────────────

st.markdown(f"""<div class="page-wrap" style="padding-top:8px;">
<div class="search-wrap">
<div class="search-input">Search cases, entities, leads…</div>
</div>
<div class="stat-grid">
<div class="stat-card teal">
<div class="stat-label">Open Cases</div>
<div class="stat-value">{open_cases}</div>
<div class="stat-note">active in system</div>
</div>
<div class="stat-card">
<div class="stat-label">Documents Processed</div>
<div class="stat-value">—</div>
<div class="stat-note">connects in Phase 1</div>
</div>
<div class="stat-card red">
<div class="stat-label">Findings Pending Review</div>
<div class="stat-value">{findings_pending}</div>
<div class="stat-note">across all cases</div>
</div>
<div class="stat-card">
<div class="stat-label">Reports Generated</div>
<div class="stat-value">—</div>
<div class="stat-note">connects in Phase 2</div>
</div>
</div>
<div class="table-card">
<table class="tbl">
<thead>
<tr>
<th>Case ID</th>
<th>Title</th>
<th>Type</th>
<th>Status</th>
<th>Docs</th>
<th>Risk</th>
<th>Last Activity</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
</div>""", unsafe_allow_html=True)
