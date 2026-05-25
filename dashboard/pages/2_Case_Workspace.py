import streamlit as st

st.set_page_config(
    page_title="Workspace · Investigation Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.styles import inject_styles  # noqa: E402

inject_styles("Case Workspace")

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
.case-title {
  font-size: 13px; font-weight: 600; color: var(--text);
  margin-right: 28px; white-space: nowrap;
}
.case-title span { font-family: var(--font-mono); color: var(--navy); }
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
  height: calc(100vh - 98px); /* navbar + subheader */
  overflow: hidden;
}
.panel-left {
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  padding: 20px 16px;
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
  padding: 20px 16px;
  overflow-y: auto;
}
.panel-heading {
  font-size: 11px; font-weight: 600; color: var(--text-mute);
  text-transform: uppercase; letter-spacing: .7px;
  margin-bottom: 14px;
}
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
  color: var(--text-mid); font-size: 13px;
}
.doc-item:hover { background: var(--panel-2); }
.doc-icon {
  width: 28px; height: 28px; border-radius: 5px;
  background: var(--panel-3);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; color: var(--navy); flex-shrink: 0;
}
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
</style>

<!-- Sub-header -->
<div class="case-subheader">
  <div class="case-title">
    <span>INV-2026-0047</span> · Ministry of Public Works
  </div>
  <a class="ws-tab active" href="#">Workspace</a>
  <a class="ws-tab" href="#">Entity Graph</a>
  <a class="ws-tab" href="#">Timeline</a>
  <a class="ws-tab" href="#">Findings</a>
  <a class="ws-tab" href="#">Report</a>
</div>

<!-- Three-panel layout -->
<div class="workspace-grid">

  <!-- Left: Documents -->
  <div class="panel-left">
    <div class="panel-heading">Documents</div>
    <div class="doc-item">
      <div class="doc-icon">PDF</div>
      Contract_MoW_2024_Annex.pdf
    </div>
    <div class="doc-item">
      <div class="doc-icon">PDF</div>
      Tender_Evaluation_Report.pdf
    </div>
    <div class="doc-item">
      <div class="doc-icon">XLS</div>
      Payment_Register_Q3.xlsx
    </div>
    <div class="doc-item">
      <div class="doc-icon">PDF</div>
      Company_Registration_NovaBuild.pdf
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
    <div class="panel-heading">Case Assistant</div>
    <div class="chat-bubble">
      Hello. I'm ready to answer questions about <strong>INV-2026-0047</strong>.
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
