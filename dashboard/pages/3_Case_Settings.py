import streamlit as st

st.set_page_config(
    page_title="Settings · Investigation Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.styles import inject_styles  # noqa: E402

inject_styles("Settings")

st.markdown("""<style>
.settings-page { display:grid; grid-template-columns:220px 1fr; min-height:calc(100vh - 96px); }
.settings-nav { background:#fff; border-right:1px solid #D5DAE1; padding:24px 0; }
.nav-section-label { font-size:10px; font-weight:700; color:#878E99; text-transform:uppercase; letter-spacing:.8px; padding:0 20px; margin-bottom:8px; margin-top:20px; display:block; }
.nav-section-label:first-child { margin-top:0; }
.nav-item { display:flex; align-items:center; padding:8px 20px; font-size:13px; font-weight:500; color:#525862; cursor:pointer; border-left:2px solid transparent; }
.nav-item.active { color:#1E3A5F; border-left-color:#0E7C86; background:#F6F7F9; font-weight:600; }
.nav-item:hover { background:#F6F7F9; color:#1E3A5F; }
.nav-badge { display:inline-flex; align-items:center; justify-content:center; background:#B4232A; color:#fff; border-radius:20px; font-size:10px; font-weight:700; min-width:18px; height:16px; padding:0 5px; margin-left:auto; line-height:1; }
.settings-body { padding:32px 40px; background:#DEE1E6; }
.section-header { margin-bottom:24px; }
.section-title { font-size:16px; font-weight:600; color:#16293F; margin-bottom:4px; }
.section-desc { font-size:13px; color:#878E99; }
.settings-card { background:#fff; border:1px solid #D5DAE1; border-radius:10px; padding:28px 30px; box-shadow:0 1px 3px rgba(0,0,0,.04); margin-bottom:20px; }
.card-title { font-size:13px; font-weight:600; color:#16293F; margin-bottom:20px; padding-bottom:14px; border-bottom:1px solid #EEF0F3; }
.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.form-grid-full { grid-column:1/-1; }
.field-label { font-size:11px; font-weight:600; color:#525862; text-transform:uppercase; letter-spacing:.6px; display:block; margin-bottom:7px; }
.field-value { background:#F6F7F9; border:1px solid #D5DAE1; border-radius:7px; padding:9px 13px; font-size:13px; color:#2A2E35; font-family:'IBM Plex Sans',sans-serif; }
.field-value-edit { background:#fff; border:1px solid #C2C9D2; border-radius:7px; padding:9px 13px; font-size:13px; color:#2A2E35; font-family:'IBM Plex Sans',sans-serif; }
.field-value-row { background:#F6F7F9; border:1px solid #D5DAE1; border-radius:7px; padding:9px 13px; font-size:13px; color:#525862; font-family:'IBM Plex Sans',sans-serif; display:flex; align-items:center; justify-content:space-between; }
.field-value-row-edit { background:#fff; border:1px solid #C2C9D2; border-radius:7px; padding:9px 13px; font-size:13px; color:#525862; font-family:'IBM Plex Sans',sans-serif; display:flex; align-items:center; justify-content:space-between; }
.field-textarea-edit { background:#fff; border:1px solid #C2C9D2; border-radius:7px; padding:10px 13px; font-size:13px; color:#2A2E35; font-family:'IBM Plex Sans',sans-serif; min-height:80px; line-height:1.55; }
.field-meta { font-size:11px; color:#878E99; margin-top:5px; }
.field-readonly-note { font-size:11px; color:#878E99; margin-top:4px; }
.status-badge { display:inline-flex; align-items:center; gap:6px; background:#E9F3EE; color:#2E7D52; border-radius:20px; font-size:11px; font-weight:600; padding:4px 12px; }
.status-dot { width:6px; height:6px; border-radius:50%; background:#2E7D52; }
.risk-display { display:flex; align-items:center; gap:12px; }
.risk-score { font-size:28px; font-weight:700; color:#B4232A; font-family:'IBM Plex Mono',monospace; }
.risk-bar-wrap { flex:1; }
.risk-bar-bg { height:8px; background:#EEF0F3; border-radius:4px; overflow:hidden; }
.risk-bar-fill { height:100%; border-radius:4px; background:#B4232A; width:87%; }
.risk-label { font-size:11px; color:#878E99; margin-top:4px; }
.btn-row { display:flex; justify-content:flex-end; gap:10px; padding-top:8px; }
.btn-cancel { font-size:13px; font-weight:500; color:#525862; background:transparent; border:1px solid #D5DAE1; border-radius:7px; padding:8px 18px; cursor:not-allowed; font-family:'IBM Plex Sans',sans-serif; }
.btn-save { font-size:13px; font-weight:600; color:#fff; background:#0E7C86; border:none; border-radius:7px; padding:8px 22px; cursor:not-allowed; font-family:'IBM Plex Sans',sans-serif; opacity:.7; }
.info-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.info-item { }
.info-label { font-size:10px; font-weight:600; color:#878E99; text-transform:uppercase; letter-spacing:.6px; margin-bottom:5px; }
.info-value { font-size:13px; font-weight:500; color:#2A2E35; }
.info-value.mono { font-family:'IBM Plex Mono',monospace; font-size:12px; }
.info-note { font-size:10px; color:#878E99; margin-top:3px; }
</style>
<div class="settings-page">
<div class="settings-nav">
<span class="nav-section-label">Case</span>
<span class="nav-item active">Case Details</span>
<span class="nav-item">Team &amp; Access</span>
<span class="nav-item">Evidence Chain</span>
<span class="nav-section-label">System</span>
<span class="nav-item">Extraction Schema</span>
<span class="nav-item">Notification Rules</span>
<span class="nav-item">Audit Log<span class="nav-badge">3</span></span>
</div>
<div class="settings-body">
<div class="section-header">
<div class="section-title">Case Details</div>
<div class="section-desc">These fields will update the official case registry across all modules once synchronized.</div>
</div>
<div class="settings-card">
<div class="card-title">Identification &amp; Status</div>
<div class="info-grid">
<div class="info-item">
<div class="info-label">🔒 Case ID</div>
<div class="info-value mono">INV-2026-0047</div>
<div class="info-note">Managed by system</div>
</div>
<div class="info-item">
<div class="info-label">Status</div>
<div class="info-value"><span class="status-badge"><span class="status-dot"></span>Active</span></div>
</div>
<div class="info-item">
<div class="info-label">Risk Score</div>
<div class="risk-display"><div class="risk-score">87</div><div class="risk-bar-wrap"><div class="risk-bar-bg"><div class="risk-bar-fill"></div></div><div class="risk-label">High — auto-calculated</div></div></div>
</div>
</div>
</div>
<div class="settings-card">
<div class="card-title">Case Configuration</div>
<div class="form-grid">
<div>
<div class="field-label">Case Title</div>
<div class="field-value-edit">Ministry of Public Works — Infrastructure Procurement</div>
<div class="field-meta">Displayed in the Cases list and all reports</div>
</div>
<div>
<div class="field-label">Case Type</div>
<div class="field-value-row-edit"><span>Procurement Fraud</span><span style="color:#878E99;font-size:11px;">▾</span></div>
<div class="field-meta">Used to select extraction schema</div>
</div>
<div>
<div class="field-label">Lead Investigator</div>
<div class="field-value-edit">S. Kowalski</div>
</div>
<div>
<div class="field-label">🔒 Created</div>
<div class="field-value" style="color:#878E99;">12 Jan 2026</div>
<div class="field-readonly-note">Managed by system</div>
</div>
<div class="form-grid-full">
<div class="field-label">Allegation Summary</div>
<div class="field-textarea-edit">Suspected irregular award of infrastructure contracts to shell companies with ties to senior ministry officials. Pattern of split invoicing and inflated valuations identified across Q2–Q4 2024 procurement cycles.</div>
</div>
</div>
</div>
<div class="btn-row">
<span class="btn-cancel">Cancel</span>
<span class="btn-save">Save Changes</span>
</div>
</div>
</div>""", unsafe_allow_html=True)
