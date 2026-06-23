import streamlit as st

st.set_page_config(
    page_title="Workspace · Investigation Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.styles import inject_styles  # noqa: E402

inject_styles("Case Workspace")

active_case_id = st.session_state.get("active_case_id", "—")

st.markdown("""
<style>
/* Sub-header bar */
.case-subheader {
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  padding: 0 28px;
  display: flex; align-items: center; gap: 0;
  height: 46px;
}
.breadcrumb {
  display:flex; align-items:center; gap:8px; margin-right:24px; min-width:0; flex-shrink:0;
}
.breadcrumb-back {
  font-size:13px; font-weight:500; color:var(--teal); text-decoration:none; white-space:nowrap;
}
.breadcrumb-sep {
  font-size:13px; color:var(--border-strong); flex-shrink:0;
}
.breadcrumb-id {
  font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; color:var(--navy); white-space:nowrap;
}
.breadcrumb-title {
  font-size:13px; font-weight:400; color:var(--text-mid); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px;
}
.ws-tab {
  font-size: 13px; font-weight: 500; color: var(--text-mute);
  padding: 0 16px; height: 46px; display: flex; align-items: center;
  border-bottom: 2px solid transparent; cursor: pointer;
  white-space: nowrap; text-decoration: none;
}
.ws-tab.active { color: var(--navy); border-bottom-color: var(--teal); }
/* Three-panel layout */
.workspace-grid {
  display: grid;
  grid-template-columns: 260px 1fr 340px;
  height: calc(100vh - 98px);
  overflow: hidden;
}
.panel-left {
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  padding: 16px 16px 20px;
  overflow-y: auto;
}
.panel-center {
  background: var(--canvas-deep);
  display: flex; align-items: center; justify-content: center;
  padding: 32px;
}
.panel-right {
  background: var(--panel);
  border-left: 1px solid var(--border);
  display: flex; flex-direction: column;
  padding: 16px 16px 20px;
  overflow-y: auto;
}
.panel-header {
  display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; flex-shrink:0;
}
.panel-heading-txt {
  font-size: 11px; font-weight: 600; color: var(--text-mute);
  text-transform: uppercase; letter-spacing: .7px;
}
.collapse-btn {
  font-size:12px; color:var(--text-mute); cursor:pointer;
  padding:2px 7px; background:var(--panel-2); border:1px solid var(--border);
  border-radius:4px; line-height:1.4; user-select:none; flex-shrink:0;
}
.collapse-btn:hover { background:var(--panel-3); color:var(--text-mid); }
.placeholder-box {
  background: var(--panel-2);
  border: 1px dashed var(--border-strong);
  border-radius: 10px;
  padding: 40px 24px;
  text-align: center;
  color: var(--text-mute);
  font-size: 13px;
}
.doc-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: 7px;
  cursor: pointer; margin-bottom: 4px;
}
.doc-item:hover { background: var(--panel-2); }
.doc-icon {
  width: 28px; height: 28px; border-radius: 5px;
  background: var(--panel-3);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; color: var(--navy); flex-shrink: 0;
}
.doc-info { display:flex; flex-direction:column; gap:2px; min-width:0; flex:1; }
.doc-name { font-size:13px; color:var(--text-mid); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.doc-meta { display:flex; align-items:center; gap:8px; }
.doc-pages { font-size:10px; color:var(--text-mute); font-family:'IBM Plex Mono',monospace; }
.doc-status-ok   { font-size:10px; color:var(--green); font-weight:600; }
.doc-status-prog { font-size:10px; color:var(--amber); font-weight:600; }
.doc-status-pend { font-size:10px; color:var(--text-mute); }
.chat-bubble {
  background: var(--panel-2);
  border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 14px;
  font-size: 13px; color: var(--text-mid);
  margin-bottom: 10px;
}
.chat-input-wrap {
  margin-top: auto;
  background: var(--panel-2);
  border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 14px;
  font-size: 13px; color: var(--text-mute);
}
/* ── ← Cases invisible page_link overlay ── */
[data-testid="stPageLink"]:not([data-testid="stHorizontalBlock"] [data-testid="stPageLink"]) {
  position: fixed !important;
  top: 96px !important;
  left: 0 !important;
  width: 140px !important;
  height: 46px !important;
  z-index: 999 !important;
}
[data-testid="stPageLink"]:not([data-testid="stHorizontalBlock"] [data-testid="stPageLink"]) a {
  display: block !important;
  width: 100% !important;
  height: 100% !important;
  cursor: pointer !important;
}
</style>
""", unsafe_allow_html=True)

st.page_link("pages/1_Cases.py", label="← Cases")

st.markdown(f"""
<!-- Sub-header -->
<div class="case-subheader">
  <div class="breadcrumb">
    <span class="breadcrumb-back">← Cases</span>
    <span class="breadcrumb-sep">·</span>
    <span class="breadcrumb-id">{active_case_id}</span>
    <span class="breadcrumb-sep">·</span>
    <span class="breadcrumb-title">Case Workspace</span>
  </div>
  <a class="ws-tab active" href="#">Workspace</a>
  <a class="ws-tab" href="#">Entity Graph</a>
  <a class="ws-tab" href="#">Timeline</a>
  <a class="ws-tab" href="#">Findings</a>
  <a class="ws-tab" href="#">Report</a>
</div>

<!-- Three-panel layout -->
<div class="workspace-grid" id="ws-grid">

  <!-- Left: Documents -->
  <div class="panel-left">
    <div class="panel-header">
      <span class="panel-heading-txt">Documents</span>
      <span class="collapse-btn" title="Collapse panel" onclick="var g=document.getElementById('ws-grid');g.style.gridTemplateColumns=g.style.gridTemplateColumns==='0px 1fr 340px'?'260px 1fr 340px':'0px 1fr 340px'">◀</span>
    </div>
    <div class="doc-item">
      <div class="doc-icon">PDF</div>
      <div class="doc-info">
        <div class="doc-name">Contract_MoW_2024_Annex.pdf</div>
        <div class="doc-meta"><span class="doc-pages">24 pp</span><span class="doc-status-ok">✓ Extracted</span></div>
      </div>
    </div>
    <div class="doc-item">
      <div class="doc-icon">PDF</div>
      <div class="doc-info">
        <div class="doc-name">Tender_Evaluation_Report.pdf</div>
        <div class="doc-meta"><span class="doc-pages">18 pp</span><span class="doc-status-ok">✓ Extracted</span></div>
      </div>
    </div>
    <div class="doc-item">
      <div class="doc-icon">XLS</div>
      <div class="doc-info">
        <div class="doc-name">Payment_Register_Q3.xlsx</div>
        <div class="doc-meta"><span class="doc-pages">3 sheets</span><span class="doc-status-prog">◐ Processing</span></div>
      </div>
    </div>
    <div class="doc-item">
      <div class="doc-icon">PDF</div>
      <div class="doc-info">
        <div class="doc-name">Company_Registration_NovaBuild.pdf</div>
        <div class="doc-meta"><span class="doc-pages">8 pp</span><span class="doc-status-pend">○ Pending</span></div>
      </div>
    </div>
    <div style="margin-top:16px; padding-top:16px; border-top:1px solid var(--border);">
      <div style="font-size:12px; color:var(--teal); cursor:pointer;">+ Upload document</div>
    </div>
  </div>

  <!-- Center: Document Viewer -->
  <div class="panel-center">
    <div class="placeholder-box" style="max-width:480px; width:100%;">
      <div style="font-size:32px; margin-bottom:12px;">📄</div>
      <div style="font-weight:600; color:var(--text-mid); margin-bottom:6px;">Document Viewer</div>
      <div>Select a document from the left panel to view it here.<br>
      Extracted fields and visual grounding will appear as overlays.</div>
    </div>
  </div>

  <!-- Right: Case Assistant -->
  <div class="panel-right">
    <div class="panel-header">
      <span class="collapse-btn" title="Collapse panel" onclick="var g=document.getElementById('ws-grid');g.style.gridTemplateColumns=g.style.gridTemplateColumns==='260px 1fr 0px'?'260px 1fr 340px':'260px 1fr 0px'">▶</span>
      <span class="panel-heading-txt">Case Assistant</span>
    </div>
    <div class="chat-bubble">
      Hello. I'm ready to answer questions about <strong>{active_case_id}</strong>.
      Ask me about documents, entities, or findings.
    </div>
    <div class="chat-bubble" style="background:var(--panel-3);">
      <em style="color:var(--text-mute);">No messages yet — ask a question to get started.</em>
    </div>
    <div class="chat-input-wrap">
      Ask about this case…
    </div>
  </div>

</div>
""", unsafe_allow_html=True)
