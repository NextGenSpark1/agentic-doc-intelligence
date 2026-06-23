import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchDocuments, uploadDocument } from '../api'
import type { Document as CaseDocument } from '../types'
import DocumentViewer from '../components/DocumentViewer'

const SUBTABS = ['Workspace', 'Entity Graph', 'Timeline', 'Findings', 'Report']

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  queued:     { color: '#878E99', label: 'Queued' },
  processing: { color: '#C77A12', label: 'Processing' },
  done:       { color: '#2E7D52', label: 'Done' },
  failed:     { color: '#B4232A', label: 'Failed' },
}

function StatusDot({ status }: { status: string }) {
  const { color, label } = STATUS_MAP[status] ?? STATUS_MAP.queued
  return (
    <span className="flex items-center gap-1">
      <span className="shrink-0 rounded-full" style={{ width: 6, height: 6, backgroundColor: color }} />
      <span className="text-[10px] leading-none" style={{ color }}>{label}</span>
    </span>
  )
}

function fileExt(filename: string): string {
  return filename.split('.').pop()?.toUpperCase() ?? 'FILE'
}

function CollapseBtn({ onClick, title, children }: { onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="w-5 h-5 flex items-center justify-center rounded text-text-mute hover:text-text hover:bg-panel-3 text-sm leading-none shrink-0"
    >
      {children}
    </button>
  )
}

export default function CaseWorkspacePage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()

  const [docs, setDocs] = useState<CaseDocument[]>([])
  const [docsLoading, setDocsLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [selectedDoc, setSelectedDoc] = useState<CaseDocument | null>(null)
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!caseId) return
    fetchDocuments(caseId)
      .then(setDocs)
      .catch(() => {})
      .finally(() => setDocsLoading(false))
  }, [caseId])

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !caseId) return
    setUploadError(null)
    setUploading(true)
    try {
      await uploadDocument(caseId, file)
      const updated = await fetchDocuments(caseId)
      setDocs(updated)
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 96px)' }}>
      {/* Sub-header */}
      <div className="bg-panel border-b border-border px-6 py-3 flex flex-col gap-2 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/cases')}
            className="text-teal text-sm font-medium hover:text-teal-soft transition-colors duration-150"
          >
            ← Cases
          </button>
          <span className="text-text-mute text-sm">/</span>
          <span className="text-sm font-mono text-text-mid">{caseId}</span>
          <span className="text-sm font-semibold text-text">Case Workspace</span>
        </div>
        <div className="flex items-center gap-1">
          {SUBTABS.map((tab) => (
            <span
              key={tab}
              className={`px-3 py-1 rounded text-sm font-medium cursor-pointer transition-colors duration-150
                ${tab === 'Workspace' ? 'bg-navy text-white' : 'text-text-mute hover:text-text hover:bg-panel-2'}`}
            >
              {tab}
            </span>
          ))}
        </div>
      </div>

      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Left panel — Documents ── */}
        <aside
          className="bg-panel border-r border-border flex flex-col shrink-0 overflow-hidden transition-all duration-200"
          style={{ width: leftCollapsed ? 32 : 240 }}
        >
          {leftCollapsed ? (
            <div className="flex flex-col items-center pt-3">
              <CollapseBtn onClick={() => setLeftCollapsed(false)} title="Expand documents">›</CollapseBtn>
            </div>
          ) : (
            <>
              <div className="px-3 py-3 border-b border-border shrink-0 flex items-center justify-between">
                <span className="text-xs font-semibold text-text-mute uppercase tracking-wide">Documents</span>
                <CollapseBtn onClick={() => setLeftCollapsed(true)} title="Collapse panel">‹</CollapseBtn>
              </div>

              <div className="flex-1 overflow-y-auto">
                <div className="flex flex-col gap-0.5 p-2">
                  {docsLoading && <p className="text-xs text-text-mute px-2 py-2">Loading…</p>}
                  {!docsLoading && docs.length === 0 && !uploading && (
                    <p className="text-xs text-text-mute px-2 py-2">No documents yet.</p>
                  )}
                  {docs.map((doc) => {
                    const ext = fileExt(doc.filename)
                    const isPdf = ext === 'PDF'
                    const isSelected = selectedDoc?.document_id === doc.document_id
                    return (
                      <div
                        key={doc.document_id}
                        onClick={() => setSelectedDoc(doc)}
                        title={doc.filename}
                        className={`flex items-start gap-2 px-2 py-2 rounded cursor-pointer transition-colors duration-150
                          ${isSelected ? 'bg-navy/10 border border-navy/20' : 'hover:bg-panel-2 border border-transparent'}`}
                      >
                        <span className={`text-xs font-mono font-semibold px-1.5 py-0.5 rounded shrink-0 mt-0.5
                          ${isPdf ? 'bg-red-bg text-red' : 'bg-green-bg text-green'}`}>
                          {ext}
                        </span>
                        <div className="flex flex-col gap-0.5 min-w-0">
                          <span className={`text-xs truncate ${isSelected ? 'text-navy font-medium' : 'text-text'}`}>
                            {doc.filename}
                          </span>
                          <StatusDot status={doc.extraction_status} />
                        </div>
                      </div>
                    )
                  })}
                  {uploading && (
                    <div className="flex items-center gap-2 px-2 py-2 rounded bg-panel-2">
                      <span className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded bg-panel-3 text-text-mute shrink-0">…</span>
                      <span className="text-xs text-text-mute italic">Uploading…</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="px-4 py-3 border-t border-border shrink-0 flex flex-col gap-1">
                {uploadError && <p className="text-[10px] text-red leading-tight break-words">{uploadError}</p>}
                <input ref={fileInputRef} type="file" hidden onChange={handleFileChange} />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="text-teal text-xs font-medium hover:text-teal-soft transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed text-left"
                >
                  + Upload document
                </button>
              </div>
            </>
          )}
        </aside>

        {/* ── Center panel — Document Viewer ── */}
        <main className="flex-1 overflow-hidden">
          {selectedDoc && caseId ? (
            <DocumentViewer doc={selectedDoc} caseId={caseId} />
          ) : (
            <div className="h-full bg-canvas-deep flex items-center justify-center">
              <div className="flex flex-col items-center gap-3 text-center px-6">
                <div className="w-14 h-14 bg-panel border border-border rounded-xl flex items-center justify-center shadow-sm">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#878E99" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="9" y1="13" x2="15" y2="13" />
                    <line x1="9" y1="17" x2="15" y2="17" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-text">Document Viewer</h3>
                <p className="text-xs text-text-mute max-w-[220px]">Select a document from the left panel to view its contents here.</p>
              </div>
            </div>
          )}
        </main>

        {/* ── Right panel — Case Assistant ── */}
        <aside
          className="bg-panel border-l border-border flex flex-col shrink-0 overflow-hidden transition-all duration-200"
          style={{ width: rightCollapsed ? 32 : 300 }}
        >
          {rightCollapsed ? (
            <div className="flex flex-col items-center pt-3">
              <CollapseBtn onClick={() => setRightCollapsed(false)} title="Expand assistant">‹</CollapseBtn>
            </div>
          ) : (
            <>
              <div className="px-3 py-3 border-b border-border shrink-0 flex items-center justify-between">
                <CollapseBtn onClick={() => setRightCollapsed(true)} title="Collapse panel">›</CollapseBtn>
                <span className="text-xs font-semibold text-text-mute uppercase tracking-wide">Case Assistant</span>
              </div>

              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
                <div className="bg-teal/10 border border-teal/20 rounded-lg px-3 py-2.5">
                  <p className="text-xs text-text">
                    Hi! I'm your Case Assistant for{' '}
                    <span className="font-mono font-semibold text-teal">{caseId}</span>. Ask me anything about the documents in this case.
                  </p>
                </div>
                <p className="text-xs text-text-mute text-center">No messages yet</p>
              </div>

              <div className="border-t border-border p-3 shrink-0">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Ask the assistant…"
                    className="flex-1 border border-border-strong rounded-md px-3 py-2 text-xs text-text bg-panel placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150"
                  />
                  <button className="bg-teal text-white text-xs font-medium px-3 py-2 rounded-md hover:bg-teal-soft transition-colors duration-150 shrink-0">
                    Send
                  </button>
                </div>
              </div>
            </>
          )}
        </aside>

      </div>
    </div>
  )
}
