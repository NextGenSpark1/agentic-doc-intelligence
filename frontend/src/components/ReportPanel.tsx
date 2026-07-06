import { useState } from 'react'
import { generateReport } from '../api'

interface Props {
  caseId: string
}

export default function ReportPanel({ caseId }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [findingCount, setFindingCount] = useState(0)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate() {
    setState('loading')
    setError(null)
    try {
      const result = await generateReport(caseId)
      setMarkdown(result.markdown)
      setFindingCount(result.finding_count)
      setState('done')
    } catch {
      setError('Failed to generate report. Please try again.')
      setState('error')
    }
  }

  function handlePrint() {
    if (!markdown) return
    const win = window.open('', '_blank')
    if (!win) return
    win.document.write(`<!DOCTYPE html>
<html>
<head>
  <title>Investigation Report</title>
  <style>
    body { font-family: Georgia, serif; max-width: 800px; margin: 40px auto; color: #1a1a1a; line-height: 1.6; }
    h1 { font-size: 1.6em; border-bottom: 2px solid #1a1a1a; padding-bottom: 8px; }
    h2 { font-size: 1.2em; margin-top: 2em; color: #1a1a1a; }
    h3 { font-size: 1em; color: #333; }
    ul { padding-left: 20px; }
    li { margin-bottom: 4px; }
    strong { font-weight: 600; }
    @media print { body { margin: 0; } }
  </style>
</head>
<body>
<pre style="white-space:pre-wrap;font-family:inherit">${markdown.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
</body>
</html>`)
    win.document.close()
    win.print()
  }

  if (state === 'idle' || state === 'error') {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-center px-6 max-w-sm">
          <div className="w-12 h-12 bg-panel border border-border rounded-xl flex items-center justify-center">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4A5568" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="13" x2="15" y2="13" />
              <line x1="9" y1="17" x2="15" y2="17" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-text-mid">Generate Investigation Report</p>
            <p className="text-xs text-text-mute mt-1">
              Compiles confirmed findings into a structured markdown report with executive summary, risk assessment, and recommendations.
            </p>
          </div>
          {error && (
            <p className="text-xs text-red bg-red-bg border border-red/20 rounded px-3 py-2">{error}</p>
          )}
          <button
            onClick={handleGenerate}
            className="px-5 py-2 text-sm font-semibold text-white bg-navy rounded-lg hover:bg-navy-soft transition-colors duration-150"
          >
            Generate Report
          </button>
        </div>
      </div>
    )
  }

  if (state === 'loading') {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center px-6">
          <div className="w-5 h-5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
          <p className="text-sm font-medium text-text-mid">Generating report…</p>
          <p className="text-xs text-text-mute">Analysing confirmed findings</p>
        </div>
      </div>
    )
  }

  // state === 'done'
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-canvas-deep">
      {/* Toolbar */}
      <div className="shrink-0 bg-panel border-b border-border px-5 py-3 flex items-center gap-3">
        <p className="text-xs text-text-mute flex-1">
          {findingCount === 0
            ? 'Generated from case details (no confirmed findings)'
            : `Based on ${findingCount} confirmed finding${findingCount !== 1 ? 's' : ''}`}
        </p>
        <button
          onClick={handleGenerate}
          className="text-xs text-text-mute hover:text-text border border-border hover:border-border-strong rounded px-3 py-1.5 transition-colors duration-150"
        >
          Regenerate
        </button>
        <button
          onClick={handlePrint}
          className="text-xs font-medium text-white bg-navy hover:bg-navy-soft rounded px-3 py-1.5 transition-colors duration-150"
        >
          Print / Export
        </button>
      </div>

      {/* Report content */}
      <div className="flex-1 overflow-y-auto py-8 px-6">
        <div className="max-w-3xl mx-auto bg-panel border border-border rounded-xl p-8">
          <pre className="text-sm text-text leading-relaxed whitespace-pre-wrap break-words font-sans">
            {markdown}
          </pre>
        </div>
      </div>
    </div>
  )
}
