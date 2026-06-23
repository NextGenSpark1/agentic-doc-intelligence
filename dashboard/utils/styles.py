import streamlit as st

from utils.theme import THEME


def get_global_css() -> str:
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root {
        --canvas: #E9EBEE;
        --canvas-deep: #DEE1E6;
        --panel: #FFFFFF;
        --panel-2: #F6F7F9;
        --panel-3: #EEF0F3;
        --border: #D5DAE1;
        --border-strong: #C2C9D2;
        --navy: #1E3A5F;
        --navy-deep: #16293F;
        --navy-soft: #2C4F78;
        --teal: #0E7C86;
        --teal-soft: #13929E;
        --red: #B4232A;
        --red-bg: #FBEDED;
        --amber: #C77A12;
        --amber-bg: #FBF1E2;
        --green: #2E7D52;
        --green-bg: #E9F3EE;
        --text: #2A2E35;
        --text-mid: #525862;
        --text-mute: #878E99;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body, .main, .stApp {
        background-color: var(--canvas-deep) !important;
        font-family: 'IBM Plex Sans', sans-serif !important;
        color: var(--text) !important;
    }

    [data-testid="stSidebar"]    { display: none !important; }
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stMainMenu"]   { display: none !important; }
    [data-testid="stHeader"]     { display: none !important; }
    footer                       { display: none !important; }
    #MainMenu                    { display: none !important; }

    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
        margin: 0 !important;
    }

    .mono { font-family: 'IBM Plex Mono', monospace !important; }

    /* ── invisible st.page_link overlays ── */
    /* The columns block containing page_links is lifted to sit over the visual tab bar.
       The links are opacity:0 so clicks pass through to Streamlit's router correctly. */
    [data-testid="stHorizontalBlock"]:has([data-testid="stPageLink"]) {
        position: fixed !important;
        top: 52px !important;
        left: 24px !important;
        height: 44px !important;
        z-index: 2000 !important;
        background: transparent !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 4px !important;
        padding: 0 !important;
        margin: 0 !important;
        width: auto !important;
    }
    [data-testid="stHorizontalBlock"]:has([data-testid="stPageLink"])
        > div[data-testid="stColumn"] {
        flex: none !important;
        width: auto !important;
        min-width: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stPageLink"] {
        display: inline-flex !important;
        align-items: center !important;
        padding: 0 !important;
        margin: 0 !important;
        background: transparent !important;
    }
    [data-testid="stPageLink"] a {
        display: inline-flex !important;
        align-items: center !important;
        height: 34px !important;
        padding: 0 16px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        white-space: nowrap !important;
        cursor: pointer !important;
        opacity: 0 !important;
        border-radius: 20px !important;
        text-decoration: none !important;
        border: none !important;
        box-shadow: none !important;
    }
    [data-testid="stPageLink"] svg { display: none !important; }
    </style>
    """


def get_navbar_html(active_page: str) -> str:
    nav_items = [
        ("Cases",    "/Cases"),
        ("Settings", "/Case_Settings"),
    ]

    tabs_html = ""
    for label, path in nav_items:
        is_active = label == active_page
        if is_active:
            style = (
                "background:#fff; color:#1E3A5F; font-weight:600;"
                " border-radius:20px; padding:5px 16px;"
                " font-size:13px; white-space:nowrap; display:inline-block;"
            )
        else:
            style = (
                "background:transparent; color:rgba(255,255,255,0.55); font-weight:500;"
                " border-radius:20px; padding:5px 16px;"
                " font-size:13px; white-space:nowrap; display:inline-block;"
            )
        tabs_html += f'<span style="{style}">{label}</span>\n'

    return f"""<div style="position:fixed;top:0;left:0;right:0;z-index:1000;">
<div style="height:52px;background:#16293F;display:flex;align-items:center;padding:0 24px;gap:20px;">
<div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0;">
<div style="width:26px;height:26px;background:#0E7C86;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff;font-family:'IBM Plex Mono',monospace;flex-shrink:0;">II</div>
<span style="color:#fff;font-size:14px;font-weight:600;white-space:nowrap;">Investigation Intelligence</span>
<span style="color:#4A6B8A;font-size:14px;margin:0 4px;">›</span>
<span style="color:#9FB0C4;font-size:13px;font-weight:400;">{active_page}</span>
</div>
<div style="background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.12);border-radius:6px;color:rgba(255,255,255,0.35);font-size:13px;padding:0 12px;height:32px;width:240px;display:flex;align-items:center;flex-shrink:0;">Search cases, entities…</div>
<div style="width:32px;height:32px;background:#0E7C86;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;flex-shrink:0;">SK</div>
</div>
<div style="height:44px;background:#1E3A5F;display:flex;align-items:center;padding:0 24px;gap:4px;border-bottom:1px solid rgba(255,255,255,0.08);">
{tabs_html}
</div>
</div>
<div style="height:96px;"></div>"""


def get_cases_page_css() -> str:
    return """<style>
.page-wrap { padding: 24px 32px; }
.toolbar { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
.toolbar-title { font-size:18px; font-weight:600; color:#16293F; margin:0; }
.spacer { flex:1; }
.filter-pill { font-size:12px; font-weight:500; color:#525862; background:#fff; border:1px solid #D5DAE1; border-radius:20px; padding:4px 13px; display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }
.filter-pill-active { font-size:12px; font-weight:500; color:#fff; background:#1E3A5F; border:1px solid #1E3A5F; border-radius:20px; padding:4px 13px; display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }
.pill-count { font-size:10px; font-weight:700; padding:1px 6px; border-radius:20px; }
.filter-pill .pill-count { background:#EEF0F3; color:#525862; }
.filter-pill-active .pill-count { background:rgba(255,255,255,0.22); color:#fff; }
.search-wrap { margin-bottom:16px; }
.search-input { width:100%; background:#F6F7F9; border:1px solid #D5DAE1; border-radius:7px; height:34px; padding:0 14px; font-size:13px; color:#878E99; display:flex; align-items:center; }
.stat-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }
.stat-card { background:#fff; border:1px solid #D5DAE1; border-left:3px solid #D5DAE1; border-radius:8px; padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,.04); }
.stat-card.teal { border-left-color:#0E7C86; }
.stat-card.red  { border-left-color:#B4232A; }
.stat-label { font-size:10px; font-weight:600; color:#878E99; text-transform:uppercase; letter-spacing:.7px; margin-bottom:8px; }
.stat-value { font-size:26px; font-weight:700; color:#2A2E35; line-height:1; margin-bottom:4px; }
.stat-note  { font-size:11px; color:#878E99; }
.table-card { background:#fff; border:1px solid #D5DAE1; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.04); }
.tbl { width:100%; border-collapse:collapse; font-size:13px; }
.tbl th { background:#F6F7F9; color:#878E99; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.6px; padding:10px 16px; text-align:left; border-bottom:1px solid #D5DAE1; }
.tbl td { padding:13px 16px; border-bottom:1px solid #EEF0F3; vertical-align:middle; color:#2A2E35; }
.tbl tr:last-child td { border-bottom:none; }
.tbl tr:hover td { background:#F6F7F9; }
.tbl tr.stale-row td:first-child { border-left:3px solid #C77A12; }
.tbl tr.clickable-row { cursor:pointer; }
.case-id { font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; color:#1E3A5F; }
.title-main { font-weight:500; color:#2A2E35; }
.title-sub  { font-size:11px; color:#878E99; margin-top:2px; }
.type-badge { display:inline-block; font-size:11px; font-weight:500; color:#2C4F78; background:#EEF0F3; border:1px solid #C2C9D2; border-radius:4px; padding:2px 9px; white-space:nowrap; }
.badge { display:inline-block; border-radius:20px; font-size:11px; font-weight:600; padding:3px 11px; white-space:nowrap; }
.badge-amber { background:#FBF1E2; color:#C77A12; border:1px solid #EAD3AC; }
.badge-green { background:#E9F3EE; color:#2E7D52; }
.badge-teal  { background:#E0F2F4; color:#0E7C86; }
.badge-grey  { background:#EEF0F3; color:#878E99; }
.badge-stale { display:inline-block; background:#EEF0F3; color:#878E99; border-radius:20px; font-size:10px; font-weight:600; padding:2px 8px; margin-left:6px; white-space:nowrap; }
.risk-wrap  { display:flex; align-items:center; gap:8px; }
.risk-track { width:68px; height:5px; background:#EEF0F3; border-radius:3px; overflow:hidden; }
.risk-fill  { height:100%; border-radius:3px; }
.risk-num   { font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; }
.ts { font-family:'IBM Plex Mono',monospace; font-size:12px; color:#878E99; }
/* ── New Case form ── */
.form-card { background:#fff; border:1px solid #D5DAE1; border-radius:8px; padding:20px 24px; margin-bottom:16px; }
.form-label { font-size:11px; font-weight:600; color:#878E99; text-transform:uppercase; letter-spacing:.6px; margin-bottom:6px; }
/* Style native Streamlit form inputs */
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label { font-size:11px !important; font-weight:600 !important; color:#878E99 !important; text-transform:uppercase !important; letter-spacing:.6px !important; }
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea { background:#fff !important; border:1px solid #C2C9D2 !important; border-radius:6px !important; font-family:'IBM Plex Sans',sans-serif !important; font-size:13px !important; color:#2A2E35 !important; }
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus { border-color:#1E3A5F !important; box-shadow:0 0 0 2px rgba(30,58,95,0.10) !important; outline:none !important; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child { background:#fff !important; border:1px solid #C2C9D2 !important; border-radius:6px !important; font-family:'IBM Plex Sans',sans-serif !important; font-size:13px !important; }
[data-testid="stFormSubmitButton"] button { background:#1E3A5F !important; color:#fff !important; border:none !important; border-radius:6px !important; font-family:'IBM Plex Sans',sans-serif !important; font-size:13px !important; font-weight:600 !important; padding:8px 20px !important; cursor:pointer !important; }
[data-testid="stFormSubmitButton"] button:hover { background:#16293F !important; }
/* ── inline banners ── */
.banner { border-radius:7px; padding:11px 16px; font-size:13px; font-weight:500; margin-bottom:12px; }
.banner-success { background:#E9F3EE; color:#2E7D52; border:1px solid #B6D9C6; }
.banner-warning { background:#FBF1E2; color:#C77A12; border:1px solid #EAD3AC; }
.banner-error   { background:#FBEDED; color:#B4232A; border:1px solid #EAC2C2; }
/* ── Clickable table rows via st.columns ── */
.tbl-grid-head { display:grid; grid-template-columns:100px 1fr 130px 120px 50px 80px 110px 44px; background:#F6F7F9; padding:10px 16px; gap:0; border:1px solid #D5DAE1; border-radius:8px 8px 0 0; border-bottom:1px solid #D5DAE1; box-shadow:0 1px 3px rgba(0,0,0,.04); margin:0 32px; }
.tbl-grid-head > span { font-size:10px; font-weight:600; color:#878E99; text-transform:uppercase; letter-spacing:.6px; }
/* Each case row is a stHorizontalBlock identified by a hidden .case-row-marker span */
div[data-testid="stHorizontalBlock"]:has(.case-row-marker) { width:calc(100% - 64px) !important; margin:0 32px !important; border-left:1px solid #D5DAE1 !important; border-right:1px solid #D5DAE1 !important; border-bottom:1px solid #EEF0F3 !important; background:#fff !important; gap:0 !important; padding:0 !important; }
div[data-testid="stHorizontalBlock"]:has(.case-row-marker):hover { background:#F6F7F9 !important; }
div[data-testid="stHorizontalBlock"]:has(.case-row-marker) > div[data-testid="stColumn"] { padding:12px 16px !important; }
div[data-testid="stHorizontalBlock"]:has(.case-row-stale) { border-left:3px solid #C77A12 !important; }
div[data-testid="stHorizontalBlock"]:has(.case-row-last) { border-bottom:1px solid #D5DAE1 !important; border-radius:0 0 8px 8px !important; box-shadow:0 1px 3px rgba(0,0,0,.04) !important; }
/* Open arrow button */
div[data-testid="stHorizontalBlock"]:has(.case-row-marker) [data-testid="stButton"] button { background:transparent !important; border:none !important; box-shadow:none !important; color:#C2C9D2 !important; font-size:18px !important; padding:0 !important; line-height:1 !important; cursor:pointer !important; width:100% !important; }
div[data-testid="stHorizontalBlock"]:has(.case-row-marker) [data-testid="stButton"] button:hover { color:#1E3A5F !important; background:transparent !important; }
/* Empty/error state */
.tbl-empty { border:1px solid #D5DAE1; border-top:none; border-radius:0 0 8px 8px; background:#fff; text-align:center; padding:40px 16px; color:#878E99; font-size:13px; box-shadow:0 1px 3px rgba(0,0,0,.04); margin:0 32px; }
</style>"""


def inject_styles(active_page: str = "Cases") -> None:
    st.markdown(get_global_css(), unsafe_allow_html=True)
    st.markdown(get_navbar_html(active_page), unsafe_allow_html=True)

    # Invisible st.page_link() anchors overlaid exactly on the visual nav tabs.
    # The CSS above positions this block fixed at top:52px left:24px (tab row start).
    # Each column auto-shrinks to content width, matching the visual tab widths.
    # opacity:0 keeps them invisible; Streamlit's router handles same-tab navigation.
    col1, col2 = st.columns([1, 1])
    with col1:
        st.page_link("pages/1_Cases.py", label="Cases")
    with col2:
        st.page_link("pages/3_Case_Settings.py", label="Settings")
