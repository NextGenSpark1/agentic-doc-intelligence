import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchCase, fetchDocuments, uploadDocumentWithProgress, deleteDocument, extractDocument, updateCase } from '../api'
import type { Case, Document as CaseDocument } from '../types'

type PendingUpload = { tempId: string; filename: string; progress: number; error: string | null }
import DocumentViewer from '../components/DocumentViewer'
import CaseAssistantPanel from '../components/CaseAssistantPanel'
import FindingsPanel from '../components/FindingsPanel'
import TimelinePanel from '../components/TimelinePanel'

const SUBTABS = ['Workspace', 'Entity Graph', 'Timeline', 'Findings', 'Report', 'Settings']

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  uploaded:   { color: '#9CA3AF', label: 'Uploaded' },
  queued:     { color: '#C77A12', label: 'Queued' },
  processing: { color: '#C77A12', label: 'Processing' },
  done:       { color: '#2E7D52', label: 'Done' },
  failed:     { color: '#B4232A', label: 'Failed' },
}

function StatusDot({ status }: { status: string }) {
  const { color, label } = STATUS_MAP[status] ?? STATUS_MAP.uploaded
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

const CASE_STATUSES = ['Intake', 'Active', 'Pending Review', 'Closed', 'Archived']
const CASE_TYPES = ['procurement_fraud', 'financial_crime', 'corruption', 'general']
const INPUT_CLS = 'border border-border-strong rounded-lg px-3 py-2 text-sm text-text bg-panel placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150 w-full'

function CaseSettingsPanel({ caseData, caseId, onUpdate }: { caseData: Case; caseId: string; onUpdate: (c: Case) => void }) {
  const [form, setForm] = useState({
    title: caseData.title,
    case_type: caseData.case_type,
    lead_investigator: caseData.lead_investigator,
    allegation_summary: caseData.allegation_summary,
    status: caseData.status,
  })
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')

  useEffect(() => {
    setForm({
      title: caseData.title,
      case_type: caseData.case_type,
      lead_investigator: caseData.lead_investigator,
      allegation_summary: caseData.allegation_summary,
      status: caseData.status,
    })
  }, [caseData.case_id])

  async function handleSave() {
    setSaving(true)
    setSaveStatus('idle')
    try {
      const updated = await updateCase(caseId, form)
      onUpdate(updated)
      setSaveStatus('success')
      setTimeout(() => setSaveStatus('idle'), 3000)
    } catch {
      setSaveStatus('error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-canvas-deep py-8 px-6">
      <div className="max-w-2xl mx-auto flex flex-col gap-4">
        {/* Read-only info */}
        <div className="bg-panel border border-border rounded-xl p-5 flex flex-col gap-3">
          <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Case Information</p>
          <div className="flex gap-8 flex-wrap">
            <div>
              <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wide mb-1">Case ID</p>
              <p className="text-sm font-mono text-text">{caseData.case_id}</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wide mb-1">Created</p>
              <p className="text-sm text-text">
                {new Date(caseData.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wide mb-1">Risk Score</p>
              <p className="text-sm text-text">{caseData.risk_score}</p>
            </div>
          </div>
        </div>

        {/* Editable fields */}
        <div className="bg-panel border border-border rounded-xl p-5 flex flex-col gap-4">
          <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Edit Details</p>

          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Case Title</label>
            <input className={INPUT_CLS} value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
          </div>

          <div className="flex gap-4">
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Status</label>
              <select className={INPUT_CLS} value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
                {CASE_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Case Type</label>
              <select className={INPUT_CLS} value={form.case_type} onChange={e => setForm(f => ({ ...f, case_type: e.target.value }))}>
                {CASE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Lead Investigator</label>
            <input className={INPUT_CLS} value={form.lead_investigator} onChange={e => setForm(f => ({ ...f, lead_investigator: e.target.value }))} />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Allegation Summary</label>
            <textarea className={`${INPUT_CLS} resize-none`} rows={3} value={form.allegation_summary} onChange={e => setForm(f => ({ ...f, allegation_summary: e.target.value }))} />
          </div>

          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-sm font-semibold text-white bg-teal hover:bg-teal-soft px-5 py-2 rounded-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
            {saveStatus === 'success' && <span className="text-xs text-green">Changes saved</span>}
            {saveStatus === 'error' && <span className="text-xs text-red">Save failed — try again</span>}
          </div>
        </div>
      </div>
    </div>
  )
}

function PlaceholderPanel({ name }: { name: string }) {
  return (
    <div className="flex-1 bg-canvas-deep flex items-center justify-center">
      <div className="flex flex-col items-center gap-2 text-center px-6">
        <p className="text-sm font-semibold text-text-mid">{name}</p>
        <p className="text-xs text-text-mute">This section is coming soon.</p>
      </div>
    </div>
  )
}

export default function CaseWorkspacePage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()

  const [caseData, setCaseData] = useState<Case | null>(null)
  const [docs, setDocs] = useState<CaseDocument[]>([])
  const [docsLoading, setDocsLoading] = useState(true)
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [selectedDoc, setSelectedDoc] = useState<CaseDocument | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [activeSubtab, setActiveSubtab] = useState('Workspace')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false)
  const [docSearch, setDocSearch] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!caseId) return
    fetchCase(caseId).then(setCaseData).catch(() => {})
    fetchDocuments(caseId)
      .then(setDocs)
      .catch(() => {})
      .finally(() => setDocsLoading(false))
  }, [caseId])

  // Poll while any doc is queued/processing
  useEffect(() => {
    const hasInProgress = docs.some(d => d.extraction_status === 'queued' || d.extraction_status === 'processing')
    if (!hasInProgress) {
      if (pollIntervalRef.current) { clearInterval(pollIntervalRef.current); pollIntervalRef.current = null }
      return
    }
    if (pollIntervalRef.current) return
    pollIntervalRef.current = setInterval(async () => {
      if (!caseId) return
      try {
        const updated = await fetchDocuments(caseId)
        setDocs(updated)
        setSelectedDoc(prev => {
          if (!prev) return prev
          return updated.find(d => d.document_id === prev.document_id) ?? prev
        })
      } catch {}
    }, 4000)
  }, [docs, caseId])

  useEffect(() => {
    return () => { if (pollIntervalRef.current) clearInterval(pollIntervalRef.current) }
  }, [])

  async function handleDelete(doc: CaseDocument) {
    if (!caseId) return
    setDeletingId(doc.document_id)
    setConfirmDeleteId(null)
    try {
      await deleteDocument(caseId, doc.document_id)
      setDocs(prev => prev.filter(d => d.document_id !== doc.document_id))
      if (selectedDoc?.document_id === doc.document_id) setSelectedDoc(null)
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setDeletingId(null)
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (!files.length || !caseId) return
    setUploadError(null)
    const newPending: PendingUpload[] = files.map(f => ({
      tempId: crypto.randomUUID(),
      filename: f.name,
      progress: 0,
      error: null,
    }))
    setPendingUploads(prev => [...prev, ...newPending])
    if (fileInputRef.current) fileInputRef.current.value = ''
    await Promise.allSettled(
      files.map((file, i) => {
        const tempId = newPending[i].tempId
        return uploadDocumentWithProgress(caseId, file, (pct) => {
          setPendingUploads(prev => prev.map(p => p.tempId === tempId ? { ...p, progress: pct } : p))
        }).then(doc => {
          setPendingUploads(prev => prev.filter(p => p.tempId !== tempId))
          setDocs(prev => [...prev, doc])
        }).catch((err: unknown) => {
          setPendingUploads(prev => prev.map(p => p.tempId === tempId
            ? { ...p, error: err instanceof Error ? err.message : 'Upload failed' }
            : p
          ))
        })
      })
    )
  }

  async function handleExtract(documentId: string) {
    if (!caseId) return
    try {
      await extractDocument(caseId, documentId)
      const patch = (d: CaseDocument) =>
        d.document_id === documentId ? { ...d, extraction_status: 'queued' } : d
      setDocs(prev => prev.map(patch))
      setSelectedDoc(prev => (prev?.document_id === documentId ? { ...prev, extraction_status: 'queued' } : prev))
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Failed to start extraction')
    }
  }

  const filteredDocs = useMemo(() =>
    docSearch.trim()
      ? docs.filter(d => d.filename.toLowerCase().includes(docSearch.toLowerCase()))
      : docs,
    [docs, docSearch]
  )

  function toggleSelect(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const allFilteredSelected = filteredDocs.length > 0 && filteredDocs.every(d => selectedIds.has(d.document_id))
  const extractableSelectedCount = docs.filter(d =>
    selectedIds.has(d.document_id) && (d.extraction_status === 'uploaded' || d.extraction_status === 'failed')
  ).length

  async function handleBulkExtract() {
    if (!caseId) return
    const eligible = docs.filter(d =>
      selectedIds.has(d.document_id) && (d.extraction_status === 'uploaded' || d.extraction_status === 'failed')
    )
    await Promise.allSettled(eligible.map(d => extractDocument(caseId, d.document_id)))
    const eligibleIds = new Set(eligible.map(d => d.document_id))
    setDocs(prev => prev.map(d => eligibleIds.has(d.document_id) ? { ...d, extraction_status: 'queued' } : d))
    setSelectedIds(new Set())
  }

  async function handleBulkDelete() {
    if (!caseId) return
    const ids = Array.from(selectedIds)
    setConfirmBulkDelete(false)
    const docsToDelete = docs.filter(d => ids.includes(d.document_id))
    await Promise.allSettled(docsToDelete.map(d => deleteDocument(caseId, d.document_id)))
    setDocs(prev => prev.filter(d => !ids.includes(d.document_id)))
    if (selectedDoc && ids.includes(selectedDoc.document_id)) setSelectedDoc(null)
    setSelectedIds(new Set())
  }

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 96px)' }}>
      {/* Single-row header: breadcrumb left, sub-tabs right */}
      <div className="bg-panel border-b border-border px-4 h-12 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/cases')}
          className="text-teal text-sm font-medium hover:text-teal-soft transition-colors duration-150 shrink-0"
        >
          ← Cases
        </button>
        <span className="text-text-mute text-sm">/</span>
        <span className="text-xs font-mono text-text-mute shrink-0">{caseId}</span>
        {caseData && (
          <span className="text-sm font-semibold text-text truncate">{caseData.title}</span>
        )}
        <div className="flex-1" />
        <div className="flex items-center gap-0.5 shrink-0">
          {SUBTABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveSubtab(tab)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors duration-150
                ${activeSubtab === tab ? 'bg-navy text-white' : 'text-text-mute hover:text-text hover:bg-panel-2'}`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Findings tab */}
      {activeSubtab === 'Findings' && (
        <FindingsPanel caseId={caseId!} docs={docs} />
      )}

      {/* Timeline tab */}
      {activeSubtab === 'Timeline' && (
        <TimelinePanel caseId={caseId!} docs={docs} />
      )}

      {/* Placeholder tabs */}
      {!['Workspace', 'Settings', 'Findings', 'Timeline'].includes(activeSubtab) && (
        <PlaceholderPanel name={activeSubtab} />
      )}

      {/* Case Settings tab */}
      {activeSubtab === 'Settings' && (
        caseData
          ? <CaseSettingsPanel caseData={caseData} caseId={caseId!} onUpdate={setCaseData} />
          : <div className="flex-1 bg-canvas-deep flex items-center justify-center">
              <div className="w-5 h-5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
            </div>
      )}

      {/* Workspace — three-panel layout */}
      {activeSubtab === 'Workspace' && (
        <div className="flex flex-1 overflow-hidden">

          {/* Left panel */}
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

                {/* Search */}
                <div className="px-2 pt-2 pb-1 shrink-0">
                  <input
                    type="text"
                    value={docSearch}
                    onChange={e => setDocSearch(e.target.value)}
                    placeholder="Filter by filename…"
                    className="w-full border border-border rounded-md px-2.5 py-1.5 text-xs text-text bg-panel-2 placeholder:text-text-mute focus:outline-none focus:ring-1 focus:ring-teal/30 focus:border-teal transition-colors duration-150"
                  />
                </div>

                {/* Select all / clear */}
                {docs.length > 0 && (
                  <div className="px-3 py-1 shrink-0 flex items-center gap-2">
                    <button
                      onClick={() =>
                        allFilteredSelected
                          ? setSelectedIds(new Set())
                          : setSelectedIds(new Set(filteredDocs.map(d => d.document_id)))
                      }
                      className="text-[10px] text-teal hover:text-teal-soft font-medium"
                    >
                      {allFilteredSelected ? 'Clear' : 'Select all'}
                    </button>
                    {selectedIds.size > 0 && (
                      <span className="text-[10px] text-text-mute">{selectedIds.size} selected</span>
                    )}
                  </div>
                )}

                {/* Bulk action bar */}
                {selectedIds.size > 0 && (
                  <div className="mx-2 mb-1 shrink-0">
                    {confirmBulkDelete ? (
                      <div className="px-2 py-2 bg-red-bg border border-red/20 rounded-lg flex flex-col gap-1.5">
                        <span className="text-[10px] text-red font-medium">Delete {selectedIds.size} document(s)?</span>
                        <div className="flex gap-3">
                          <button onClick={handleBulkDelete} className="text-[10px] font-semibold text-red hover:underline">Delete</button>
                          <button onClick={() => setConfirmBulkDelete(false)} className="text-[10px] text-text-mute hover:underline">Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div className="px-2 py-1.5 bg-teal/10 border border-teal/20 rounded-lg flex items-center gap-2">
                        {extractableSelectedCount > 0 && (
                          <>
                            <button onClick={handleBulkExtract} className="text-[10px] font-semibold text-teal hover:text-teal-soft">
                              Extract ({extractableSelectedCount})
                            </button>
                            <span className="text-[10px] text-text-mute">·</span>
                          </>
                        )}
                        <button onClick={() => setConfirmBulkDelete(true)} className="text-[10px] font-semibold text-red hover:text-red/70">
                          Delete ({selectedIds.size})
                        </button>
                        <div className="flex-1" />
                        <button onClick={() => setSelectedIds(new Set())} className="text-[10px] text-text-mute hover:text-text">✕</button>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex-1 overflow-y-auto">
                  <div className="flex flex-col gap-0.5 p-2">
                    {docsLoading && <p className="text-xs text-text-mute px-2 py-2">Loading…</p>}
                    {!docsLoading && filteredDocs.length === 0 && pendingUploads.length === 0 && (
                      <p className="text-xs text-text-mute px-2 py-2">
                        {docSearch ? 'No matches.' : 'No documents yet.'}
                      </p>
                    )}
                    {filteredDocs.map((doc) => {
                      const ext = fileExt(doc.filename)
                      const isPdf = ext === 'PDF'
                      const isSelected = selectedDoc?.document_id === doc.document_id
                      const isDeleting = deletingId === doc.document_id
                      const isConfirming = confirmDeleteId === doc.document_id
                      const isChecked = selectedIds.has(doc.document_id)

                      if (isDeleting) return (
                        <div key={doc.document_id} className="flex items-center gap-2 px-2 py-2 rounded bg-panel-2">
                          <span className="text-xs text-text-mute italic">Deleting…</span>
                        </div>
                      )

                      if (isConfirming) return (
                        <div key={doc.document_id} className="flex items-center gap-1.5 px-2 py-2 rounded bg-red-bg border border-red/20">
                          <span className="text-[10px] text-red flex-1 leading-tight">Delete this document?</span>
                          <button onClick={() => handleDelete(doc)} className="text-[10px] font-semibold text-red hover:underline shrink-0">Yes</button>
                          <button onClick={() => setConfirmDeleteId(null)} className="text-[10px] text-text-mute hover:underline shrink-0">Cancel</button>
                        </div>
                      )

                      return (
                        <div
                          key={doc.document_id}
                          onClick={() => setSelectedDoc(doc)}
                          title={doc.filename}
                          className={`group flex items-start gap-2 px-2 py-2 rounded cursor-pointer transition-colors duration-150
                            ${isSelected ? 'bg-navy/10 border border-navy/20' : 'hover:bg-panel-2 border border-transparent'}`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onClick={e => e.stopPropagation()}
                            onChange={() => toggleSelect(doc.document_id)}
                            className="mt-0.5 shrink-0 accent-teal cursor-pointer"
                          />
                          <span className={`text-xs font-mono font-semibold px-1.5 py-0.5 rounded shrink-0 mt-0.5
                            ${isPdf ? 'bg-red-bg text-red' : 'bg-green-bg text-green'}`}>
                            {ext}
                          </span>
                          <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                            <span className={`text-xs truncate ${isSelected ? 'text-navy font-medium' : 'text-text'}`}>
                              {doc.filename}
                            </span>
                            <StatusDot status={doc.extraction_status} />
                          </div>
                          {(doc.extraction_status === 'uploaded' || doc.extraction_status === 'failed') && (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleExtract(doc.document_id) }}
                              title="Start extraction"
                              className="shrink-0 mt-0.5 text-[10px] font-semibold text-teal hover:text-teal-soft opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                            >
                              {doc.extraction_status === 'failed' ? 'Retry' : 'Extract'}
                            </button>
                          )}
                          <button
                            onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(doc.document_id) }}
                            title="Delete document"
                            className="opacity-0 group-hover:opacity-100 shrink-0 mt-0.5 text-text-mute hover:text-red transition-opacity duration-150"
                          >
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                            </svg>
                          </button>
                        </div>
                      )
                    })}
                    {pendingUploads.map(({ tempId, filename, progress, error }) => (
                      <div key={tempId} className="flex items-center gap-2 px-2 py-2 rounded bg-panel-2 border border-transparent">
                        <span className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded bg-panel-3 text-text-mute shrink-0 uppercase">
                          {filename.split('.').pop()?.toUpperCase() ?? '…'}
                        </span>
                        <div className="flex flex-col gap-1 min-w-0 flex-1">
                          <span className="text-xs text-text-mute truncate">{filename}</span>
                          {error ? (
                            <span className="text-[10px] text-red truncate">{error}</span>
                          ) : (
                            <div className="h-1 bg-panel-3 rounded-full overflow-hidden">
                              <div className="h-full bg-teal transition-all duration-300 rounded-full" style={{ width: `${progress}%` }} />
                            </div>
                          )}
                        </div>
                        {error && (
                          <button
                            onClick={() => setPendingUploads(prev => prev.filter(p => p.tempId !== tempId))}
                            className="shrink-0 text-sm text-text-mute hover:text-text"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="px-4 py-3 border-t border-border shrink-0 flex flex-col gap-1">
                  {uploadError && <p className="text-[10px] text-red leading-tight break-words">{uploadError}</p>}
                  <input ref={fileInputRef} type="file" multiple hidden onChange={handleFileChange} />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="text-teal text-xs font-medium hover:text-teal-soft transition-colors duration-150 text-left"
                  >
                    + Upload document(s)
                  </button>
                </div>
              </>
            )}
          </aside>

          {/* Center panel */}
          <main className="flex-1 overflow-hidden">
            {selectedDoc && caseId ? (
              <DocumentViewer doc={selectedDoc} caseId={caseId} onExtract={() => handleExtract(selectedDoc.document_id)} />
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

          {/* Right panel */}
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
                <CaseAssistantPanel caseId={caseId!} docs={docs} />
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
