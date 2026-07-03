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

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
      style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

export default function DocumentViewer({ doc, caseId, onExtract }: Props) {
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
  const pageContainerRef = useRef<HTMLDivElement>(null)
  const [pageRendered, setPageRendered] = useState(false)

  // Right panel collapsible sections
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [rawOpen, setRawOpen] = useState(false)

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

  // Track outer container width
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    setContainerWidth(el.clientWidth)
    const obs = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // PDF renders in the left 60% column; subtract padding for safe render width
  const pdfPanelWidth = Math.round(containerWidth * 0.6)
  const pageWidth = pdfPanelWidth > 64 ? Math.min(pdfPanelWidth - 32, 900) : undefined

  async function loadSummary() {
    setSummary(undefined)
    setSummaryError(null)
    try {
      const data = await fetchSummary(caseId, doc.document_id)
      setSummary(data?.summary ?? null)
    } catch (err: unknown) {
      setSummaryError(err instanceof Error ? err.message : 'Failed to load summary')
      setSummary(null)
    }
  }

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
        <div className="flex flex-1 overflow-hidden">

          {/* Left column — PDF viewer (60%) */}
          <div className="flex flex-col overflow-hidden" style={{ flex: '0 0 60%' }}>
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
                    {/* Chunk overlays */}
                    {showOverlay && pageRendered && chunks
                      .filter(c => c.page === pageNumber - 1 && Array.isArray(c.bbox) && c.bbox.length === 4)
                      .map(c => {
                        const [l, t, r, b] = c.bbox as [number, number, number, number]
                        const isHovered = hoveredChunk === c.chunk_id
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
                              backgroundColor: isHovered ? 'rgba(0,190,172,0.25)' : 'rgba(0,190,172,0.10)',
                              border: '1px solid rgba(0,190,172,0.5)',
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
              )}
            </div>
          </div>

          {/* Right column — extraction panel (40%) */}
          <div className="flex flex-col border-l border-border overflow-hidden" style={{ flex: '0 0 40%' }}>
            <div className="flex-1 overflow-y-auto bg-panel">

              {/* ── Section 1: Extracted Fields (always visible) ── */}
              <div>
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
                  <p className="text-xs text-text-mute text-center py-8">Loading…</p>
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
                    {fieldEntries.map(([key, val]) => (
                      <div key={key} className="px-4 py-2.5 border-b border-border last:border-0">
                        <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wide mb-0.5">
                          {formatFieldName(key)}
                        </p>
                        <p className="text-sm text-text">{renderFieldValue(val)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* ── Section 2: Summary (collapsible) ── */}
              <div className="border-t border-border">
                <button
                  onClick={() => setSummaryOpen(v => !v)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-panel-2 transition-colors duration-150"
                >
                  <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Summary</p>
                  <span className="text-text-mute">
                    <ChevronIcon open={summaryOpen} />
                  </span>
                </button>
                {summaryOpen && (
                  <div className="pb-4">
                    {status !== 'done' && (
                      <p className="text-xs text-text-mute px-4">Extract the document first.</p>
                    )}
                    {status === 'done' && summary === undefined && (
                      <div className="flex justify-center px-4">
                        <div className="w-3.5 h-3.5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
                      </div>
                    )}
                    {status === 'done' && summaryError && (
                      <div className="px-4 flex flex-col gap-1">
                        <p className="text-xs text-red">{summaryError}</p>
                        <button onClick={loadSummary} className="text-xs text-teal hover:underline self-start">
                          Retry
                        </button>
                      </div>
                    )}
                    {status === 'done' && summary === null && !summaryError && (
                      <div className="px-4">
                        <button
                          onClick={loadSummary}
                          className="text-xs font-medium text-white bg-teal hover:bg-teal-soft px-3 py-1.5 rounded-lg transition-colors duration-150"
                        >
                          Generate Summary
                        </button>
                      </div>
                    )}
                    {summary && (
                      <p className="text-sm text-text leading-relaxed px-4">{summary}</p>
                    )}
                  </div>
                )}
              </div>

              {/* ── Section 3: Raw Text (collapsible) ── */}
              <div className="border-t border-border">
                <button
                  onClick={() => setRawOpen(v => !v)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-panel-2 transition-colors duration-150"
                >
                  <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Raw Text</p>
                  <span className="text-text-mute">
                    <ChevronIcon open={rawOpen} />
                  </span>
                </button>
                {rawOpen && (
                  <div className="pb-4">
                    {status !== 'done' && (
                      <p className="text-xs text-text-mute px-4">Extract the document first.</p>
                    )}
                    {status === 'done' && extraction === undefined && !extractionError && (
                      <div className="flex justify-center px-4">
                        <div className="w-3.5 h-3.5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
                      </div>
                    )}
                    {status === 'done' && extractionError && (
                      <p className="text-xs text-red px-4">{extractionError}</p>
                    )}
                    {status === 'done' && extraction && !extraction.raw_text && (
                      <p className="text-xs text-text-mute px-4">No raw text available.</p>
                    )}
                    {extraction?.raw_text && (
                      <pre className="px-4 text-[11px] font-mono text-text-mid leading-relaxed whitespace-pre-wrap break-words overflow-x-auto max-h-96">
                        {extraction.raw_text}
                      </pre>
                    )}
                  </div>
                )}
              </div>

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
                <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">AI Summary</p>
                <p className="text-sm leading-relaxed text-text">{summary}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
