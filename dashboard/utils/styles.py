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
        ("Cases",          "/Cases"),
        ("Case Workspace", "/Case_Workspace"),
        ("Settings",       "/Case_Settings"),
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


def inject_styles(active_page: str = "Cases") -> None:
    st.markdown(get_global_css(), unsafe_allow_html=True)
    st.markdown(get_navbar_html(active_page), unsafe_allow_html=True)

    # Invisible st.page_link() anchors overlaid exactly on the visual nav tabs.
    # The CSS above positions this block fixed at top:52px left:24px (tab row start).
    # Each column auto-shrinks to content width, matching the visual tab widths.
    # opacity:0 keeps them invisible; Streamlit's router handles same-tab navigation.
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.page_link("pages/1_Cases.py", label="Cases")
    with col2:
        st.page_link("pages/2_Case_Workspace.py", label="Case Workspace")
    with col3:
        st.page_link("pages/3_Case_Settings.py", label="Settings")
