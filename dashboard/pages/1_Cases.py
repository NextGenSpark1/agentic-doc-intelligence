import streamlit as st

st.set_page_config(
    page_title="Cases · Investigation Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.styles import inject_styles  # noqa: E402

inject_styles("Cases")

st.markdown("""<style>
.page-wrap { padding: 24px 32px; }
.toolbar { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
.toolbar-title { font-size:18px; font-weight:600; color:#16293F; margin:0; }
.spacer { flex:1; }
.filter-pill { font-size:12px; font-weight:500; color:#525862; background:#fff; border:1px solid #D5DAE1; border-radius:20px; padding:4px 13px; cursor:pointer; display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }
.filter-pill-active { font-size:12px; font-weight:500; color:#fff; background:#1E3A5F; border:1px solid #1E3A5F; border-radius:20px; padding:4px 13px; display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }
.pill-count { font-size:10px; font-weight:700; padding:1px 6px; border-radius:20px; }
.filter-pill .pill-count { background:#EEF0F3; color:#525862; }
.filter-pill-active .pill-count { background:rgba(255,255,255,0.22); color:#fff; }
.btn-new { font-size:13px; font-weight:600; color:#fff; background:#1E3A5F; border:none; border-radius:7px; padding:8px 18px; cursor:pointer; font-family:'IBM Plex Sans',sans-serif; white-space:nowrap; }
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
</style>
<div class="page-wrap">
<div class="toolbar">
<h3 class="toolbar-title">Cases</h3>
<div class="spacer"></div>
<span class="filter-pill-active">All <span class="pill-count">17</span></span>
<span class="filter-pill">Active <span class="pill-count">14</span></span>
<span class="filter-pill">Pending Review <span class="pill-count">5</span></span>
<span class="filter-pill">Archived <span class="pill-count">3</span></span>
<span class="btn-new">+ New Case</span>
</div>
<div class="search-wrap">
<div class="search-input">Search cases, entities, leads…</div>
</div>
<div class="stat-grid">
<div class="stat-card teal">
<div class="stat-label">Open Cases</div>
<div class="stat-value">14</div>
<div class="stat-note">↑ 2 this week</div>
</div>
<div class="stat-card">
<div class="stat-label">Documents Processed</div>
<div class="stat-value">3,204</div>
<div class="stat-note">across all cases</div>
</div>
<div class="stat-card red">
<div class="stat-label">Findings Pending Review</div>
<div class="stat-value">38</div>
<div class="stat-note">↑ 6 since yesterday</div>
</div>
<div class="stat-card">
<div class="stat-label">Reports Generated</div>
<div class="stat-value">9</div>
<div class="stat-note">last: 2 days ago</div>
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
<tr>
<td><span class="case-id">INV-2026-0047</span></td>
<td><div class="title-main">Ministry of Public Works — Procurement Irregularity</div><div class="title-sub">Lead: S. Kowalski · Created 12 Jan 2026</div></td>
<td><span class="type-badge">Procurement</span></td>
<td><span class="badge badge-amber">Pending Review</span></td>
<td><span class="ts">847</span></td>
<td><div class="risk-wrap"><div class="risk-track"><div class="risk-fill" style="width:87%;background:#B4232A;"></div></div><span class="risk-num" style="color:#B4232A;">87</span></div></td>
<td><span class="ts">2h ago</span></td>
</tr>
<tr>
<td><span class="case-id">INV-2026-0042</span></td>
<td><div class="title-main">Vendor Payment Tracing — Coastal Logistics</div><div class="title-sub">Lead: A. Mensah · Created 8 Jan 2026</div></td>
<td><span class="type-badge">Payment Tracing</span></td>
<td><span class="badge badge-green">Report Ready</span></td>
<td><span class="ts">312</span></td>
<td><div class="risk-wrap"><div class="risk-track"><div class="risk-fill" style="width:64%;background:#C77A12;"></div></div><span class="risk-num" style="color:#C77A12;">64</span></div></td>
<td><span class="ts">1d ago</span></td>
</tr>
<tr>
<td><span class="case-id">INV-2026-0039</span></td>
<td><div class="title-main">Conflict of Interest — Procurement Board</div><div class="title-sub">Lead: P. Osei · Created 3 Jan 2026</div></td>
<td><span class="type-badge">Conflict of Interest</span></td>
<td><span class="badge badge-teal">Extracting</span></td>
<td><span class="ts">156</span></td>
<td><div class="risk-wrap"><div class="risk-track"><div class="risk-fill" style="width:41%;background:#0E7C86;"></div></div><span class="risk-num" style="color:#0E7C86;">41</span></div></td>
<td><span class="ts">4h ago</span></td>
</tr>
<tr class="stale-row">
<td><span class="case-id">INV-2026-0031</span></td>
<td><div class="title-main">Grant Disbursement Audit — Regional Office</div><div class="title-sub">Lead: Y. Tadesse · Created 28 Dec 2025</div></td>
<td><span class="type-badge">Audit</span></td>
<td><span class="badge badge-grey">Intake</span></td>
<td><span class="ts">68</span></td>
<td><div class="risk-wrap"><div class="risk-track"><div class="risk-fill" style="width:18%;background:#878E99;"></div></div><span class="risk-num" style="color:#878E99;">18</span></div></td>
<td><span class="ts">3d ago</span><span class="badge-stale">Stale</span></td>
</tr>
</tbody>
</table>
</div>
</div>""", unsafe_allow_html=True)
