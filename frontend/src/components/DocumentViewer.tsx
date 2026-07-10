import { useState, useEffect, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { fetchFileUrl, fetchExtraction, fetchSummary, fetchDocumentChunks } from '../api'
import type { Document as CaseDocument, Extraction, DocumentChunk } from '../types'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

type Tab = 'viewer' | 'raw' | 'summary'

interface Props {
  doc: CaseDocument
  caseId: string
  onExtract: () => void
  jumpToPage?: number | null
  onJumpHandled?: () => void
}

function formatFieldName(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function renderFieldValue(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'string') return val || '—'
  if (typeof val === 'number' || typeof val === 'boolean') return String(val)
  if (Array.isArray(val)) return val.length ? val.join(', ') : '—'
  return JSON.stringify(val)
}

const CHUNK_LEGEND = [
  { label: 'Text',   color: '#0E7C86' },
  { label: 'Table',  color: '#F59E0B' },
  { label: 'Figure', color: '#8B5CF6' },
  { label: 'Header', color: '#1E3A5F' },
]

function chunkColors(type: string, hovered: boolean): { bg: string; border: string } {
  const t = type.toLowerCase()
  if (t === 'table') {
    return { bg: `rgba(245,158,11,${hovered ? 0.30 : 0.15})`, border: '#F59E0B' }
  }
  if (t.startsWith('fig') || t === 'image') {
    return { bg: `rgba(139,92,246,${hovered ? 0.30 : 0.15})`, border: '#8B5CF6' }
  }
  if (t === 'header' || t === 'title') {
    return { bg: `rgba(30,58,95,${hovered ? 0.25 : 0.12})`, border: '#1E3A5F' }
  }
  if (t === 'text' || t === 'paragraph' || t === '') {
    return { bg: `rgba(14,124,134,${hovered ? 0.25 : 0.10})`, border: '#0E7C86' }
  }
  return { bg: `rgba(156,163,175,${hovered ? 0.25 : 0.10})`, border: '#9CA3AF' }
}


export default function DocumentViewer({ doc, caseId, onExtract, jumpToPage, onJumpHandled }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('viewer')

  // PDF state
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [urlLoading, setUrlLoading] = useState(true)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [numPages, setNumPages] = useState<number | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

  // Extraction state — undefined = loading, null = unavailable
  const [extraction, setExtraction] = useState<Extraction | null | undefined>(undefined)
  const [extractionError, setExtractionError] = useState<string | null>(null)

  // Summary state — undefined = loading, null = unavailable
  const [summary, setSummary] = useState<string | null | undefined>(undefined)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  // Chunk overlay state
  const [chunks, setChunks] = useState<DocumentChunk[]>([])
  const [showOverlay, setShowOverlay] = useState(false)
  const [hoveredChunk, setHoveredChunk] = useState<string | null>(null)
  const [locatedChunk, setLocatedChunk] = useState<DocumentChunk | null>(null)
  const pageContainerRef = useRef<HTMLDivElement>(null)
  const [pageRendered, setPageRendered] = useState(false)

  // Draggable split between PDF (left) and extracted fields (right).
  // Percentage of horizontal space taken by the PDF column.
  const [pdfSplit, setPdfSplit] = useState(60)
  const splitContainerRef = useRef<HTMLDivElement | null>(null)
  const isDraggingRef = useRef(false)

  function handleDragStart(e: React.MouseEvent) {
    e.preventDefault()
    isDraggingRef.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  function findChunkForField(value: string): DocumentChunk | null {
    if (!value || value === '—') return null
    const needle = value.toLowerCase().trim()
    const valid = chunks.filter(c => Array.isArray(c.bbox) && c.bbox.length === 4 && typeof c.page === 'number')
    if (!valid.length) return null
    const exact = valid.find(c => c.text.toLowerCase().includes(needle))
    if (exact) return exact
    // For comma-separated list values try the first item
    const firstItem = needle.split(',')[0].trim()
    if (firstItem !== needle && firstItem.length > 2) {
      const m = valid.find(c => c.text.toLowerCase().includes(firstItem))
      if (m) return m
    }
    // Word-based fuzzy fallback
    const words = needle.split(/\s+/).filter(w => w.length > 2)
    if (words.length < 2) return null
    let best: DocumentChunk | null = null, bestScore = 0
    for (const c of valid) {
      const ct = c.text.toLowerCase()
      const score = words.filter(w => ct.includes(w)).length
      if (score > bestScore) { bestScore = score; best = c }
    }
    return bestScore >= 2 ? best : null
  }

  function handleFieldLocate(val: unknown) {
    const str = renderFieldValue(val)
    const chunk = findChunkForField(str)
    if (!chunk || typeof chunk.page !== 'number') return
    setLocatedChunk(chunk)
    const targetPage = chunk.page + 1
    if (targetPage !== pageNumber) {
      setPageRendered(false)
      setPageNumber(targetPage)
    }
  }

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!isDraggingRef.current || !splitContainerRef.current) return
      const rect = splitContainerRef.current.getBoundingClientRect()
      if (rect.width <= 0) return
      const pct = ((e.clientX - rect.left) / rect.width) * 100
      setPdfSplit(Math.min(75, Math.max(35, pct)))
      setPageRendered(false)  // page will re-render at new width; re-arm overlay guard
    }
    function onUp() {
      if (!isDraggingRef.current) return
      isDraggingRef.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [])

  // Reset when document changes
  useEffect(() => {
    setActiveTab('viewer')
    setFileUrl(null)
    setUrlLoading(true)
    setUrlError(null)
    setNumPages(null)
    setPageNumber(1)
    setShowOverlay(false)
    setHoveredChunk(null)
    setLocatedChunk(null)
    setPageRendered(false)

    fetchFileUrl(caseId, doc.document_id)
      .then((url) => { setFileUrl(url); setUrlLoading(false) })
      .catch((err: Error) => { setUrlError(err.message); setUrlLoading(false) })
  }, [doc.document_id, caseId])

  // Fetch extraction data when status becomes 'done'
  useEffect(() => {
    const isDone = doc.extraction_status === 'done'
    setExtraction(isDone ? undefined : null)
    setExtractionError(null)
    setSummary(isDone ? undefined : null)
    setSummaryError(null)
    setChunks([])

    if (!isDone) return

    fetchExtraction(caseId, doc.document_id)
      .then(setExtraction)
      .catch((err: Error) => { setExtractionError(err.message); setExtraction(null) })

    fetchSummary(caseId, doc.document_id)
      .then((data) => setSummary(data?.summary ?? null))
      .catch((err: Error) => { setSummaryError(err.message); setSummary(null) })

    fetchDocumentChunks(caseId, doc.document_id)
      .then(setChunks)
      .catch(() => setChunks([]))
  }, [doc.document_id, caseId, doc.extraction_status])

  // Jump to a target page (from citation click). Switch to Viewer tab, turn overlays on,
  // and mark the page dirty so onRenderSuccess flips pageRendered back to true.
  useEffect(() => {
    if (jumpToPage === null || jumpToPage === undefined) return
    setActiveTab('viewer')
    setPageNumber(jumpToPage)
    setPageRendered(false)
    setShowOverlay(true)
    onJumpHandled?.()
  }, [jumpToPage, onJumpHandled])

  // Track outer container width
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    setContainerWidth(el.clientWidth)
    const obs = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // PDF renders in the left column at the current split percentage; subtract padding for safe render width
  const pdfPanelWidth = Math.round(containerWidth * (pdfSplit / 100))
  const pageWidth = pdfPanelWidth > 64 ? Math.min(pdfPanelWidth - 32, 900) : undefined

  const TABS: { id: Tab; label: string }[] = [
    { id: 'viewer',  label: 'Viewer' },
    { id: 'raw',     label: 'Raw Text' },
    { id: 'summary', label: 'Summary' },
  ]

  const status = doc.extraction_status
  const fieldEntries = extraction ? Object.entries(extraction.extracted_json) : []

  return (
    <div className="flex flex-col h-full" ref={containerRef}>
      {/* Tab strip */}
      <div className="shrink-0 flex items-center border-b border-border bg-panel px-4 gap-1">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`px-3 py-2.5 text-xs font-medium border-b-2 transition-colors duration-150 -mb-px ${
              activeTab === id
                ? 'text-navy border-teal'
                : 'text-text-mute border-transparent hover:text-text hover:border-border-strong'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Viewer tab: side-by-side PDF + extraction panel ── */}
      {activeTab === 'viewer' && (
        <div className="flex flex-1 overflow-hidden" ref={splitContainerRef}>

          {/* Left column — PDF viewer */}
          <div className="flex flex-col overflow-hidden" style={{ flex: `0 0 ${pdfSplit}%` }}>
            <div className="flex-1 overflow-y-auto flex flex-col items-center py-6 bg-canvas-deep">
              {urlLoading && <p className="text-xs text-text-mute mt-10">Loading…</p>}
              {urlError && (
                <p className="text-xs text-red mt-10 px-6 text-center">
                  Failed to load document: {urlError}
                </p>
              )}
              {fileUrl && (
                <Document
                  file={fileUrl}
                  onLoadSuccess={({ numPages: n }) => setNumPages(n)}
                  onLoadError={(err) => { setUrlError(err.message); setUrlLoading(false) }}
                  loading={<p className="text-xs text-text-mute mt-10">Rendering PDF…</p>}
                  error={<p className="text-xs text-red mt-10">Could not render PDF.</p>}
                >
                  <div className="relative shadow-md" ref={pageContainerRef}>
                    <Page
                      pageNumber={pageNumber}
                      width={pageWidth}
                      renderTextLayer
                      renderAnnotationLayer
                      onRenderSuccess={() => setPageRendered(true)}
                    />
                    {/* Field location highlight — shown when a field row is clicked */}
                    {pageRendered && locatedChunk && locatedChunk.page === pageNumber - 1 &&
                      Array.isArray(locatedChunk.bbox) && locatedChunk.bbox.length === 4 && (
                      <div
                        style={{
                          position: 'absolute',
                          left: `${locatedChunk.bbox[0] * 100}%`,
                          top: `${locatedChunk.bbox[1] * 100}%`,
                          width: `${(locatedChunk.bbox[2] - locatedChunk.bbox[0]) * 100}%`,
                          height: `${(locatedChunk.bbox[3] - locatedChunk.bbox[1]) * 100}%`,
                          backgroundColor: 'rgba(234,179,8,0.22)',
                          border: '2px solid #EAB308',
                          borderRadius: 3,
                          boxShadow: '0 0 0 3px rgba(234,179,8,0.12)',
                          zIndex: 20,
                          pointerEvents: 'none',
                        }}
                      />
                    )}
                    {/* Chunk overlays — color coded by type */}
                    {showOverlay && pageRendered && chunks
                      .filter(c => c.page === pageNumber - 1 && Array.isArray(c.bbox) && c.bbox.length === 4)
                      .map(c => {
                        const [l, t, r, b] = c.bbox as [number, number, number, number]
                        const isHovered = hoveredChunk === c.chunk_id
                        const { bg, border } = chunkColors(c.type, isHovered)
                        return (
                          <div
                            key={c.chunk_id}
                            onMouseEnter={() => setHoveredChunk(c.chunk_id)}
                            onMouseLeave={() => setHoveredChunk(null)}
                            style={{
                              position: 'absolute',
                              left: `${l * 100}%`,
                              top: `${t * 100}%`,
                              width: `${(r - l) * 100}%`,
                              height: `${(b - t) * 100}%`,
                              backgroundColor: bg,
                              border: `1px solid ${border}`,
                              borderRadius: 2,
                              cursor: 'default',
                              zIndex: 10,
                            }}
                          >
                            {isHovered && (
                              <div style={{
                                position: 'absolute',
                                top: '100%',
                                left: 0,
                                zIndex: 20,
                                background: '#1C2333',
                                border: '1px solid #2E3A4E',
                                borderRadius: 6,
                                padding: '6px 8px',
                                maxWidth: 260,
                                fontSize: 11,
                                color: '#CBD2DE',
                                lineHeight: 1.5,
                                pointerEvents: 'none',
                                marginTop: 4,
                                boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}>
                                <span style={{ color: border, fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                  {c.type || 'text'}
                                </span>
                                <br />
                                {c.text.slice(0, 200)}{c.text.length > 200 ? '…' : ''}
                              </div>
                            )}
                          </div>
                        )
                      })}
                  </div>
                </Document>
              )}
            </div>

            {/* PDF footer: page nav + overlay toggle */}
            <div className="shrink-0 border-t border-border bg-panel flex items-center gap-3 px-4 py-2">
              {numPages !== null && (
                <>
                  <button
                    onClick={() => { setPageNumber(p => Math.max(1, p - 1)); setPageRendered(false) }}
                    disabled={pageNumber <= 1}
                    className="text-xs px-2.5 py-1 rounded border border-border text-text-mid hover:bg-panel-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
                  >
                    ←
                  </button>
                  <span className="text-xs font-mono text-text-mute tabular-nums select-none">
                    {pageNumber} / {numPages}
                  </span>
                  <button
                    onClick={() => { setPageNumber(p => Math.min(numPages!, p + 1)); setPageRendered(false) }}
                    disabled={pageNumber >= numPages}
                    className="text-xs px-2.5 py-1 rounded border border-border text-text-mid hover:bg-panel-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
                  >
                    →
                  </button>
                </>
              )}
              <div className="flex-1" />
              {chunks.length > 0 && (
                <>
                  {showOverlay && (
                    <div className="flex items-center gap-2">
                      {CHUNK_LEGEND.map(({ label, color }) => (
                        <span key={label} className="flex items-center gap-1">
                          <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: color, display: 'inline-block', flexShrink: 0 }} />
                          <span className="text-[10px] text-text-mute">{label}</span>
                        </span>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => setShowOverlay(v => !v)}
                    className={`text-xs px-3 py-1 rounded border transition-colors duration-150 ${
                      showOverlay
                        ? 'border-teal text-teal bg-teal/10'
                        : 'border-border text-text-mute hover:border-border-strong hover:text-text'
                    }`}
                  >
                    {showOverlay ? 'Hide regions' : 'Show regions'}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Draggable divider */}
          <div
            onMouseDown={handleDragStart}
            className="w-1 bg-border hover:bg-teal/40 cursor-col-resize shrink-0 transition-colors duration-150"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize PDF panel"
          />

          {/* Right column — extracted fields panel */}
          <div className="flex flex-col overflow-hidden" style={{ flex: `1 1 ${100 - pdfSplit}%` }}>
            <div className="flex-1 overflow-y-auto bg-panel">
              <div className="px-4 py-3 border-b border-border">
                <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">
                  Extracted Fields
                </p>
              </div>

              {status === 'uploaded' && (
                <div className="flex flex-col items-center gap-2 py-8 text-center px-4">
                  <p className="text-xs text-text-mute">Run extraction to see fields.</p>
                  <button
                    onClick={onExtract}
                    className="text-xs font-semibold text-white bg-teal hover:bg-teal-soft px-3 py-1.5 rounded-lg transition-colors duration-150"
                  >
                    Extract Document
                  </button>
                </div>
              )}

              {(status === 'queued' || status === 'processing') && (
                <div className="flex flex-col items-center gap-2 py-8 text-center px-4">
                  <div className="w-4 h-4 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
                  <p className="text-xs font-medium text-text-mid">Extracting…</p>
                  <p className="text-[10px] text-text-mute">Usually 20–30 seconds</p>
                </div>
              )}

              {status === 'failed' && (
                <div className="flex flex-col items-center gap-2 py-8 text-center px-4">
                  <p className="text-xs font-medium text-text-mid">Extraction failed</p>
                  <button
                    onClick={onExtract}
                    className="text-xs text-white bg-red hover:bg-red/80 px-3 py-1.5 rounded transition-colors duration-150"
                  >
                    Retry Extraction
                  </button>
                </div>
              )}

              {status === 'done' && extraction === undefined && !extractionError && (
                <div className="flex flex-col">
                  {[0, 1, 2, 3, 4].map(i => (
                    <div key={i} className="px-4 py-2.5 border-b border-border last:border-0 flex flex-col gap-1.5">
                      <div className="h-2 bg-panel-3 rounded animate-pulse w-20" />
                      <div className="h-4 bg-panel-3 rounded animate-pulse w-3/4" />
                    </div>
                  ))}
                </div>
              )}

              {status === 'done' && extractionError && (
                <p className="text-xs text-red text-center py-8 px-4">{extractionError}</p>
              )}

              {status === 'done' && extraction !== undefined && !extractionError && fieldEntries.length === 0 && (
                <p className="text-xs text-text-mute text-center py-8">No fields extracted.</p>
              )}

              {status === 'done' && extraction && fieldEntries.length > 0 && (
                <div className="flex flex-col">
                  <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider px-4 pt-3 pb-1">
                    {extraction.schema_name ?? 'Fields'}
                  </p>
                  {fieldEntries.map(([key, val]) => {
                    const str = renderFieldValue(val)
                    const locatable = str !== '—'
                    const isLocated = locatable && locatedChunk !== null && findChunkForField(str) === locatedChunk
                    return (
                      <div
                        key={key}
                        onClick={locatable ? () => handleFieldLocate(val) : undefined}
                        title={locatable ? 'Click to locate in document' : undefined}
                        className={`px-4 py-2.5 border-b border-border last:border-0 group transition-colors duration-150 ${
                          locatable ? 'cursor-pointer hover:bg-panel-2' : ''
                        } ${isLocated ? 'bg-amber-500/10' : ''}`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className={`text-[10px] font-semibold uppercase tracking-wide mb-0.5 ${isLocated ? 'text-amber-500' : 'text-text-mute'}`}>
                              {formatFieldName(key)}
                            </p>
                            <p className="text-sm text-text">{str}</p>
                          </div>
                          {locatable && (
                            <svg
                              width="12" height="12" viewBox="0 0 24 24" fill="none"
                              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                              className={`mt-1 shrink-0 transition-opacity duration-150 ${isLocated ? 'opacity-100 text-amber-500' : 'opacity-0 group-hover:opacity-50 text-text-mute'}`}
                            >
                              <circle cx="11" cy="11" r="8" />
                              <path d="m21 21-4.35-4.35" />
                            </svg>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Raw Text tab (full-width, for reading/copying) ── */}
      {activeTab === 'raw' && (
        <div className="flex-1 overflow-y-auto bg-panel">
          {status !== 'done' && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
              <p className="text-sm font-medium text-text-mid">Not yet extracted</p>
              <p className="text-xs text-text-mute">Run extraction to view raw text.</p>
              <button
                onClick={onExtract}
                className="mt-1 text-xs font-semibold text-white bg-teal hover:bg-teal-soft px-4 py-2 rounded-lg transition-colors duration-150"
              >
                Extract Document
              </button>
            </div>
          )}
          {status === 'done' && extraction === undefined && !extractionError && (
            <p className="text-xs text-text-mute text-center mt-10">Loading…</p>
          )}
          {status === 'done' && extractionError && (
            <p className="text-xs text-red text-center mt-10 px-6">{extractionError}</p>
          )}
          {status === 'done' && extraction && !extraction.raw_text && !extractionError && (
            <p className="text-xs text-text-mute text-center mt-10">No raw text available.</p>
          )}
          {extraction?.raw_text && (
            <pre className="p-4 text-[11px] font-mono text-text-mid leading-relaxed whitespace-pre-wrap break-words">
              {extraction.raw_text}
            </pre>
          )}
        </div>
      )}

      {/* ── Summary tab (full-width) ── */}
      {activeTab === 'summary' && (
        <div className="flex-1 overflow-y-auto bg-panel">
          {status !== 'done' && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
              <p className="text-sm font-medium text-text-mid">Not yet extracted</p>
              <p className="text-xs text-text-mute">Run extraction to generate a summary.</p>
              <button
                onClick={onExtract}
                className="mt-1 text-xs font-semibold text-white bg-teal hover:bg-teal-soft px-4 py-2 rounded-lg transition-colors duration-150"
              >
                Extract Document
              </button>
            </div>
          )}
          {status === 'done' && summary === undefined && (
            <p className="text-xs text-text-mute text-center mt-10">Loading…</p>
          )}
          {status === 'done' && summaryError && (
            <p className="text-xs text-red text-center mt-10 px-6">{summaryError}</p>
          )}
          {status === 'done' && summary && (
            <div className="p-5">
              <div className="rounded-lg border border-border bg-canvas p-5 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">AI Summary</p>
                  <button
                    onClick={() => {
                      setSummary(undefined)
                      setSummaryError(null)
                      if (doc) {
                        fetchSummary(caseId, doc.document_id)
                          .then(data => setSummary(data?.summary ?? null))
                          .catch((err: Error) => { setSummaryError(err.message); setSummary(null) })
                      }
                    }}
                    className="text-[10px] font-semibold text-text-mute hover:text-teal transition-colors duration-150"
                  >
                    Regenerate
                  </button>
                </div>
                <p className="text-sm leading-relaxed text-text">{summary}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
