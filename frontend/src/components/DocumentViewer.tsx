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

type Tab = 'document' | 'fields' | 'raw' | 'summary'

interface Props {
  doc: CaseDocument
  caseId: string
  onExtract: () => void
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

function ExtractionEmptyState({ status, onExtract }: { status: string; onExtract: () => void }) {
  if (status === 'queued' || status === 'processing') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
        <div className="w-5 h-5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
        <p className="text-sm font-medium text-text-mid">Extracting document…</p>
        <p className="text-xs text-text-mute">This usually takes 20–30 seconds</p>
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
        <div className="w-9 h-9 bg-red-bg border border-red/20 rounded-lg flex items-center justify-center">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#B4232A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <p className="text-sm font-medium text-text-mid">Extraction failed</p>
        <p className="text-xs text-text-mute">Something went wrong during document processing.</p>
        <button
          onClick={onExtract}
          className="mt-1 text-xs font-semibold text-white bg-red hover:bg-red/80 px-4 py-2 rounded-lg transition-colors duration-150"
        >
          Retry Extraction
        </button>
      </div>
    )
  }

  if (status === 'done') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-6">
        <div className="w-2 h-2 rounded-full mb-1 bg-[#878E99]" />
        <p className="text-sm font-medium text-text-mid">No data available</p>
        <p className="text-xs text-text-mute">No extraction data found for this document.</p>
      </div>
    )
  }

  // "uploaded" — default
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
      <div className="w-9 h-9 bg-panel-2 border border-border rounded-lg flex items-center justify-center">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#878E99" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="9" y1="13" x2="15" y2="13" />
          <line x1="9" y1="17" x2="15" y2="17" />
        </svg>
      </div>
      <p className="text-sm font-medium text-text-mid">Not yet extracted</p>
      <p className="text-xs text-text-mute">Run extraction to view fields, raw text, and summary.</p>
      <button
        onClick={onExtract}
        className="mt-1 text-xs font-semibold text-white bg-teal hover:bg-teal-soft px-4 py-2 rounded-lg transition-colors duration-150"
      >
        Extract Document
      </button>
    </div>
  )
}

export default function DocumentViewer({ doc, caseId, onExtract }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('document')

  // Document tab state
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [urlLoading, setUrlLoading] = useState(true)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [numPages, setNumPages] = useState<number | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

  // Extraction tab state — undefined = loading, null = not available
  const [extraction, setExtraction] = useState<Extraction | null | undefined>(undefined)
  const [extractionError, setExtractionError] = useState<string | null>(null)

  // Summary tab state — undefined = loading, null = not available
  const [summary, setSummary] = useState<string | null | undefined>(undefined)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  // Chunk overlay state
  const [chunks, setChunks] = useState<DocumentChunk[]>([])
  const [showOverlay, setShowOverlay] = useState(false)
  const [hoveredChunk, setHoveredChunk] = useState<string | null>(null)
  const pageContainerRef = useRef<HTMLDivElement>(null)
  const [pageSize, setPageSize] = useState<{ w: number; h: number } | null>(null)

  // Reset file viewer and fetch URL when document changes
  useEffect(() => {
    setActiveTab('document')
    setFileUrl(null)
    setUrlLoading(true)
    setUrlError(null)
    setNumPages(null)
    setPageNumber(1)

    fetchFileUrl(caseId, doc.document_id)
      .then((url) => { setFileUrl(url); setUrlLoading(false) })
      .catch((err: Error) => { setUrlError(err.message); setUrlLoading(false) })
  }, [doc.document_id, caseId])

  // Fetch extraction data when document changes or extraction_status becomes "done"
  useEffect(() => {
    const isDone = doc.extraction_status === 'done'
    setExtraction(isDone ? undefined : null)
    setExtractionError(null)
    setSummary(isDone ? undefined : null)
    setSummaryError(null)

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

  // Track container width for Phase 2 overlays
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    setContainerWidth(el.clientWidth)
    const obs = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const pageWidth = containerWidth > 64 ? Math.min(containerWidth - 64, 900) : undefined

  // Observe the rendered page element to get actual pixel dimensions for bbox overlays
  useEffect(() => {
    const el = pageContainerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      setPageSize({ w: entry.contentRect.width, h: entry.contentRect.height })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [pageNumber, pageWidth])

  const TABS: { id: Tab; label: string }[] = [
    { id: 'document', label: 'Document' },
    { id: 'fields',   label: 'Extracted Fields' },
    { id: 'raw',      label: 'Raw Text' },
    { id: 'summary',  label: 'Summary' },
  ]

  return (
    <div className="flex flex-col h-full" ref={containerRef}>
      {/* Tab strip */}
      <div className="shrink-0 flex items-center border-b border-border bg-panel px-4 gap-1">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`
              px-3 py-2.5 text-xs font-medium border-b-2 transition-colors duration-150 -mb-px
              ${activeTab === id
                ? 'text-navy border-teal'
                : 'text-text-mute border-transparent hover:text-text hover:border-border-strong'}
            `}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Document tab ── */}
      {activeTab === 'document' && (
        <>
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
                    onRenderSuccess={() => {
                      if (pageContainerRef.current) {
                        const el = pageContainerRef.current
                        setPageSize({ w: el.clientWidth, h: el.clientHeight })
                      }
                    }}
                  />
                  {/* Chunk overlays */}
                  {showOverlay && pageSize && chunks
                    .filter(c => c.page === pageNumber - 1 && Array.isArray(c.bbox) && c.bbox.length === 4)
                    .map(c => {
                      const [l, t, r, b] = c.bbox as [number, number, number, number]
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
                            backgroundColor: hoveredChunk === c.chunk_id ? 'rgba(0,190,172,0.25)' : 'rgba(0,190,172,0.10)',
                            border: '1px solid rgba(0,190,172,0.5)',
                            borderRadius: 2,
                            cursor: 'default',
                            zIndex: 10,
                          }}
                        >
                          {hoveredChunk === c.chunk_id && (
                            <div
                              style={{
                                position: 'absolute',
                                top: '100%',
                                left: 0,
                                zIndex: 20,
                                background: '#1C2333',
                                border: '1px solid #2E3A4E',
                                borderRadius: 6,
                                padding: '6px 8px',
                                maxWidth: 280,
                                fontSize: 11,
                                color: '#CBD2DE',
                                lineHeight: 1.5,
                                pointerEvents: 'none',
                                marginTop: 4,
                                boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}
                            >
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

          <div className="shrink-0 border-t border-border bg-panel flex items-center gap-4 px-4 py-2">
            {numPages !== null && (
              <>
                <button
                  onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
                  disabled={pageNumber <= 1}
                  className="text-xs px-3 py-1.5 rounded border border-border text-text-mid hover:bg-panel-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
                >
                  ← Prev
                </button>
                <span className="text-xs font-mono text-text-mute tabular-nums select-none">
                  {pageNumber} / {numPages}
                </span>
                <button
                  onClick={() => setPageNumber((p) => Math.min(numPages!, p + 1))}
                  disabled={pageNumber >= numPages}
                  className="text-xs px-3 py-1.5 rounded border border-border text-text-mid hover:bg-panel-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
                >
                  Next →
                </button>
              </>
            )}
            <div className="flex-1" />
            {chunks.length > 0 && (
              <button
                onClick={() => setShowOverlay(v => !v)}
                className={`text-xs px-3 py-1.5 rounded border transition-colors duration-150 ${
                  showOverlay
                    ? 'border-teal text-teal bg-teal/10'
                    : 'border-border text-text-mute hover:border-border-strong hover:text-text'
                }`}
              >
                {showOverlay ? 'Hide regions' : 'Show regions'}
              </button>
            )}
          </div>
        </>
      )}

      {/* ── Extracted Fields tab ── */}
      {activeTab === 'fields' && (
        <div className="flex-1 overflow-y-auto bg-panel">
          {extraction === undefined && (
            <p className="text-xs text-text-mute text-center mt-10">Loading…</p>
          )}
          {extractionError && (
            <p className="text-xs text-red text-center mt-10 px-6">{extractionError}</p>
          )}
          {extraction === null && !extractionError && (
            <ExtractionEmptyState status={doc.extraction_status} onExtract={onExtract} />
          )}
          {extraction && (
            <>
              {Object.keys(extraction.extracted_json).length === 0 ? (
                <ExtractionEmptyState status={doc.extraction_status} onExtract={onExtract} />
              ) : (
                <div className="p-4 flex flex-col gap-0">
                  <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider mb-3">
                    {extraction.schema_name ?? 'Extracted Fields'}
                  </p>
                  {Object.entries(extraction.extracted_json).map(([key, val]) => (
                    <div
                      key={key}
                      className="flex flex-col gap-0.5 py-2.5 border-b border-border last:border-0"
                    >
                      <span className="text-[10px] font-semibold text-text-mute uppercase tracking-wide">
                        {formatFieldName(key)}
                      </span>
                      <span className="text-sm text-text">{renderFieldValue(val)}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Raw Text tab ── */}
      {activeTab === 'raw' && (
        <div className="flex-1 overflow-y-auto bg-panel">
          {extraction === undefined && (
            <p className="text-xs text-text-mute text-center mt-10">Loading…</p>
          )}
          {extractionError && (
            <p className="text-xs text-red text-center mt-10 px-6">{extractionError}</p>
          )}
          {extraction === null && !extractionError && (
            <ExtractionEmptyState status={doc.extraction_status} onExtract={onExtract} />
          )}
          {extraction && !extraction.raw_text && (
            <ExtractionEmptyState status={doc.extraction_status} onExtract={onExtract} />
          )}
          {extraction?.raw_text && (
            <pre className="p-4 text-[11px] font-mono text-text-mid leading-relaxed whitespace-pre-wrap break-words">
              {extraction.raw_text}
            </pre>
          )}
        </div>
      )}

      {/* ── Summary tab ── */}
      {activeTab === 'summary' && (
        <div className="flex-1 overflow-y-auto bg-panel">
          {summary === undefined && (
            <p className="text-xs text-text-mute text-center mt-10">Loading…</p>
          )}
          {summaryError && (
            <p className="text-xs text-red text-center mt-10 px-6">{summaryError}</p>
          )}
          {summary === null && !summaryError && (
            <ExtractionEmptyState status={doc.extraction_status} onExtract={onExtract} />
          )}
          {summary && (
            <div className="p-5">
              <div className="rounded-lg border border-border bg-canvas p-5 flex flex-col gap-3">
                <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">
                  AI Summary
                </p>
                <p className="text-sm leading-relaxed text-text">{summary}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
