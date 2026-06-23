import { useState, useEffect, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { fetchFileUrl } from '../api'
import type { Document as CaseDocument } from '../types'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface Props {
  doc: CaseDocument
  caseId: string
}

export default function DocumentViewer({ doc, caseId }: Props) {
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [urlLoading, setUrlLoading] = useState(true)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [numPages, setNumPages] = useState<number | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

  // Fetch signed URL whenever document changes
  useEffect(() => {
    setFileUrl(null)
    setUrlLoading(true)
    setUrlError(null)
    setNumPages(null)
    setPageNumber(1)
    fetchFileUrl(caseId, doc.document_id)
      .then((url) => { setFileUrl(url); setUrlLoading(false) })
      .catch((err: Error) => { setUrlError(err.message); setUrlLoading(false) })
  }, [doc.document_id, caseId])

  // Track container width for accurate page sizing (needed for Phase 2 overlays)
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    setContainerWidth(el.clientWidth)
    const obs = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const pageWidth = containerWidth > 64 ? Math.min(containerWidth - 64, 900) : undefined

  return (
    <div className="flex flex-col h-full" ref={containerRef}>
      {/* Scrollable PDF area */}
      <div className="flex-1 overflow-y-auto flex flex-col items-center py-6 bg-canvas-deep">
        {urlLoading && (
          <p className="text-xs text-text-mute mt-10">Loading…</p>
        )}
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
            {/* Relative wrapper intentional — Phase 2 will position extraction overlays here */}
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

      {/* Page navigation — shown once PDF loads */}
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
    </div>
  )
}
