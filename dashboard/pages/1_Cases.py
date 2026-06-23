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

if "_success_msg" in st.session_state:
    msg = st.session_state.pop("_success_msg")
    st.markdown(f'<div class="banner banner-success">{msg}</div>', unsafe_allow_html=True)


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
                st.markdown('<div class="banner banner-warning">Case Title and Lead Investigator are required.</div>', unsafe_allow_html=True)
            else:
                result, err = create_case({
                    "title": title.strip(),
                    "case_type": case_type,
                    "lead_investigator": lead.strip(),
                    "allegation_summary": allegation.strip(),
                })
                if err:
                    st.markdown(f'<div class="banner banner-error">Could not create case: {err}</div>', unsafe_allow_html=True)
                else:
                    st.session_state["_success_msg"] = f"Case {result['case_id']} created."
                    st.rerun()


# ── search + stat cards ───────────────────────────────────────────

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
</div>""", unsafe_allow_html=True)


# ── table ─────────────────────────────────────────────────────────

st.markdown("""<div class="tbl-grid-head">
<span>Case ID</span><span>Title</span><span>Type</span><span>Status</span>
<span>Docs</span><span>Risk</span><span>Last Activity</span><span></span>
</div>""", unsafe_allow_html=True)

if error:
    st.markdown(f'<div class="tbl-empty">Backend unavailable — {error}</div>', unsafe_allow_html=True)
elif not cases:
    st.markdown('<div class="tbl-empty">No cases yet. Use "+ New Case" above to create the first one.</div>', unsafe_allow_html=True)
else:
    for i, c in enumerate(cases):
        stale    = _is_stale(c)
        score    = int(c.get("risk_score") or 0)
        color    = _risk_color(score)
        activity = _relative_time(c.get("last_analysed_at") or c.get("created_at"))
        stale_badge = '<span class="badge-stale">Stale</span>' if stale else ""
        is_last  = (i == len(cases) - 1)

        # Marker classes drive CSS :has() targeting for border/hover/stale/last-row styling
        marker_cls = "case-row-marker"
        if stale:   marker_cls += " case-row-stale"
        if is_last: marker_cls += " case-row-last"
        marker = f'<span class="{marker_cls}" style="display:none;"></span>'

        cols = st.columns([1.0, 2.2, 1.3, 1.2, 0.5, 0.85, 1.15, 0.4], gap="small")
        with cols[0]:
            st.markdown(f'{marker}<span class="case-id">{c["case_id"]}</span>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(
                f'<div class="title-main">{c.get("title","")}</div>'
                f'<div class="title-sub">Lead: {c.get("lead_investigator","—")} · Created {_fmt_date(c.get("created_at"))}</div>',
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(f'<span class="type-badge">{_fmt_type(c.get("case_type",""))}</span>', unsafe_allow_html=True)
        with cols[3]:
            st.markdown(_status_badge(c.get("status", "")), unsafe_allow_html=True)
        with cols[4]:
            st.markdown('<span class="ts">—</span>', unsafe_allow_html=True)
        with cols[5]:
            st.markdown(
                f'<div class="risk-wrap">'
                f'<div class="risk-track"><div class="risk-fill" style="width:{score}%;background:{color};"></div></div>'
                f'<span class="risk-num" style="color:{color};">{score}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cols[6]:
            st.markdown(f'<span class="ts">{activity}</span>{stale_badge}', unsafe_allow_html=True)
        with cols[7]:
            if st.button("›", key=f"open_{c['case_id']}"):
                st.session_state["active_case_id"] = c["case_id"]
                st.switch_page("pages/2_Case_Workspace.py")
