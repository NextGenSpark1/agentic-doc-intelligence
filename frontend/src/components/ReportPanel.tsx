import { useState } from 'react'
import { marked } from 'marked'
import { generateReport } from '../api'

interface Props {
  caseId: string
}

marked.setOptions({ gfm: true, breaks: true })

const PRINT_STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'IBM Plex Sans', Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #1e293b; line-height: 1.7; font-size: 13px; padding: 0 20px; }
  .brand-header { display: flex; align-items: flex-start; justify-content: space-between; padding-bottom: 16px; margin-bottom: 28px; border-bottom: 3px solid #1558D4; }
  .brand-name { font-size: 11px; font-weight: 700; letter-spacing: 0.14em; color: #1558D4; text-transform: uppercase; }
  .brand-sub { font-size: 9px; color: #94a3b8; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 2px; }
  .brand-meta { text-align: right; font-size: 9px; color: #94a3b8; line-height: 1.6; }
  .brand-meta .confidential { font-weight: 700; color: #dc2626; text-transform: uppercase; letter-spacing: 0.08em; }
  h1 { font-size: 1.45em; font-weight: 700; color: #0f172a; margin-bottom: 6px; }
  h2 { font-size: 0.9em; font-weight: 700; color: #1558D4; margin: 2em 0 0.6em; padding-bottom: 5px; border-bottom: 1px solid #e2e8f0; text-transform: uppercase; letter-spacing: 0.07em; }
  h3 { font-size: 0.92em; font-weight: 600; color: #334155; margin: 1.2em 0 0.3em; }
  p { margin-bottom: 0.75em; }
  ul, ol { padding-left: 18px; margin-bottom: 0.75em; }
  li { margin-bottom: 3px; }
  strong { font-weight: 700; color: #0f172a; }
  .brand-footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; font-size: 9px; color: #94a3b8; }
  @media print { body { margin: 20px; } }
`

export default function ReportPanel({ caseId }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [findingCount, setFindingCount] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const today = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })

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
    const html = marked.parse(markdown) as string
    const win = window.open('', '_blank')
    if (!win) return
    win.document.write(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Investigation Report</title>
  <style>${PRINT_STYLES}</style>
</head>
<body>
  <div class="brand-header">
    <div>
      <div class="brand-name">NextGen Spark</div>
      <div class="brand-sub">Investigation Intelligence Platform</div>
    </div>
    <div class="brand-meta">
      <div class="confidential">Confidential</div>
      <div>${today}</div>
    </div>
  </div>
  ${html}
  <div class="brand-footer">
    <span>NextGen Spark — Investigation Intelligence Platform</span>
    <span>For authorised personnel only</span>
  </div>
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
              Compiles confirmed findings into a structured report with executive summary, risk assessment, and recommendations.
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

  const html = marked.parse(markdown ?? '') as string

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
        <div className="max-w-3xl mx-auto bg-panel border border-border rounded-xl overflow-hidden shadow-sm">

          {/* Branded header */}
          <div className="px-8 pt-6 pb-5 flex items-start justify-between border-b-[3px] border-[#1558D4]">
            <div>
              <p className="text-[10px] font-bold tracking-[0.14em] text-[#1558D4] uppercase">NextGen Spark</p>
              <p className="text-[9px] text-text-mute tracking-[0.08em] uppercase mt-0.5">Investigation Intelligence Platform</p>
            </div>
            <div className="text-right">
              <p className="text-[9px] font-bold text-red-500 uppercase tracking-wider">Confidential</p>
              <p className="text-[9px] text-text-mute mt-0.5">{today}</p>
            </div>
          </div>

          {/* Rendered markdown */}
          <div className="px-8 py-7 report-body" dangerouslySetInnerHTML={{ __html: html }} />

          {/* Footer */}
          <div className="px-8 py-3 border-t border-border flex items-center justify-between bg-canvas-deep/40">
            <p className="text-[9px] text-text-mute">NextGen Spark — Investigation Intelligence Platform</p>
            <p className="text-[9px] text-text-mute">For authorised personnel only</p>
          </div>

        </div>
      </div>
    </div>
  )
}
