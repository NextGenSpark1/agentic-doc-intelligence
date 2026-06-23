import { useState, useEffect, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { fetchFileUrl, fetchExtraction } from '../api'
import type { Document as CaseDocument, Extraction } from '../types'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

type Tab = 'document' | 'fields' | 'raw'

interface Props {
  doc: CaseDocument
  caseId: string
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

function EmptyState({ status }: { status: string }) {
  const notDone = status !== 'done'
  return (
    <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-6">
      <div
        className="w-2 h-2 rounded-full mb-1"
        style={{ backgroundColor: notDone ? '#C77A12' : '#878E99' }}
      />
      <p className="text-sm font-medium text-text-mid">
        {notDone ? 'Not yet processed' : 'No data available'}
      </p>
      <p className="text-xs text-text-mute">
        {notDone
          ? `Extraction status: ${status}`
          : 'No extraction data found for this document.'}
      </p>
    </div>
  )
}

export default function DocumentViewer({ doc, caseId }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('document')

  // Document tab state
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [urlLoading, setUrlLoading] = useState(true)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [numPages, setNumPages] = useState<number | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

  // Extraction tab state
  const [extraction, setExtraction] = useState<Extraction | null | undefined>(undefined) // undefined = loading
  const [extractionError, setExtractionError] = useState<string | null>(null)

  // Reset everything when document changes
  useEffect(() => {
    setActiveTab('document')
    setFileUrl(null)
    setUrlLoading(true)
    setUrlError(null)
    setNumPages(null)
    setPageNumber(1)
    setExtraction(undefined)
    setExtractionError(null)

    fetchFileUrl(caseId, doc.document_id)
      .then((url) => { setFileUrl(url); setUrlLoading(false) })
      .catch((err: Error) => { setUrlError(err.message); setUrlLoading(false) })

    fetchExtraction(caseId, doc.document_id)
      .then(setExtraction)
      .catch((err: Error) => { setExtractionError(err.message); setExtraction(null) })
  }, [doc.document_id, caseId])

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

  const TABS: { id: Tab; label: string }[] = [
    { id: 'document', label: 'Document' },
    { id: 'fields',   label: 'Extracted Fields' },
    { id: 'raw',      label: 'Raw Text' },
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
                {/* Relative wrapper intentional — Phase 2 extraction overlays go here */}
                <div className="relative shadow-md">
                  <Page
                    pageNumber={pageNumber}
                    width={pageWidth}
                    renderTextLayer
                    renderAnnotationLayer
                  />
                </div>
              </Document>
            )}
          </div>

          {numPages !== null && (
            <div className="shrink-0 border-t border-border bg-panel flex items-center justify-center gap-4 px-4 py-2">
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
            </div>
          )}
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
            <EmptyState status={doc.extraction_status} />
          )}
          {extraction && (
            <>
              {Object.keys(extraction.extracted_json).length === 0 ? (
                <EmptyState status={doc.extraction_status} />
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
            <EmptyState status={doc.extraction_status} />
          )}
          {extraction && !extraction.raw_text && (
            <EmptyState status={doc.extraction_status} />
          )}
          {extraction?.raw_text && (
            <pre className="p-4 text-[11px] font-mono text-text-mid leading-relaxed whitespace-pre-wrap break-words">
              {extraction.raw_text}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
