import { useState, useEffect, useMemo } from 'react'
import type { Finding, Document as CaseDocument } from '../types'
import { fetchFindings, reviewFinding } from '../api'
import { useAuth } from '../context/AuthContext'

const SEVERITY_STYLES: Record<string, { badge: string; dot: string }> = {
  high:   { badge: 'bg-red-bg text-red border border-red/25',              dot: '#B4232A' },
  medium: { badge: 'bg-yellow-50 text-yellow-700 border border-yellow-200', dot: '#CA8A04' },
  low:    { badge: 'bg-panel-2 text-text-mute border border-border',        dot: '#9CA3AF' },
}

const REVIEW_STYLES: Record<string, { label: string; color: string }> = {
  pending:   { label: 'Pending Review', color: '#CA8A04' },
  confirmed: { label: 'Confirmed',      color: '#2E7D52' },
  dismissed: { label: 'Dismissed',      color: '#9CA3AF' },
}

function formatType(t: string) {
  return t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 75 ? '#2E7D52' : pct >= 50 ? '#CA8A04' : '#B4232A'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-panel-3 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-[10px] text-text-mute tabular-nums">{pct}%</span>
    </div>
  )
}

interface DismissState {
  findingId: string
  reason: string
}

export default function FindingsPanel({
  caseId,
  docs,
  onRunAnalysis,
  analysisState,
}: {
  caseId: string
  docs: CaseDocument[]
  onRunAnalysis?: () => void
  analysisState?: string
}) {
  const { user } = useAuth()
  const [findings, setFindings] = useState<Finding[] | null>(null)
  const [filterSeverity, setFilterSeverity] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [processing, setProcessing] = useState<Set<string>>(new Set())
  const [dismissState, setDismissState] = useState<DismissState | null>(null)
  const [error, setError] = useState<string | null>(null)

  const docMap = useMemo(
    () => Object.fromEntries(docs.map(d => [d.document_id, d.filename])),
    [docs],
  )

  useEffect(() => {
    fetchFindings(caseId)
      .then(setFindings)
      .catch(() => setError('Failed to load findings.'))
  }, [caseId])

  const filtered = useMemo(() => {
    if (!findings) return []
    return findings.filter(f => {
      if (filterSeverity !== 'all' && f.severity !== filterSeverity) return false
      if (filterStatus !== 'all' && f.human_review_status !== filterStatus) return false
      return true
    })
  }, [findings, filterSeverity, filterStatus])

  const counts = useMemo(() => {
    if (!findings) return { pending: 0, confirmed: 0, dismissed: 0 }
    return {
      pending:   findings.filter(f => f.human_review_status === 'pending').length,
      confirmed: findings.filter(f => f.human_review_status === 'confirmed').length,
      dismissed: findings.filter(f => f.human_review_status === 'dismissed').length,
    }
  }, [findings])

  async function handleConfirm(findingId: string) {
    const reviewer = user?.email ?? 'investigator'
    setProcessing(prev => new Set(prev).add(findingId))
    try {
      const updated = await reviewFinding(findingId, 'confirmed', reviewer)
      setFindings(prev => prev?.map(f => f.finding_id === findingId ? updated : f) ?? prev)
    } catch {
      setError('Failed to confirm finding.')
    } finally {
      setProcessing(prev => { const n = new Set(prev); n.delete(findingId); return n })
    }
  }

  async function handleDismiss(findingId: string, reason: string) {
    const reviewer = user?.email ?? 'investigator'
    setProcessing(prev => new Set(prev).add(findingId))
    setDismissState(null)
    try {
      const updated = await reviewFinding(findingId, 'dismissed', reviewer, reason || undefined)
      setFindings(prev => prev?.map(f => f.finding_id === findingId ? updated : f) ?? prev)
    } catch {
      setError('Failed to dismiss finding.')
    } finally {
      setProcessing(prev => { const n = new Set(prev); n.delete(findingId); return n })
    }
  }

  const PILL = (active: boolean) =>
    `px-3 py-1 rounded-full text-xs font-medium transition-colors duration-150 ${
      active ? 'bg-navy text-white' : 'text-text-mute hover:text-text hover:bg-panel-2'
    }`

  if (error) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <p className="text-sm text-red">{error}</p>
      </div>
    )
  }

  if (findings === null) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto bg-canvas-deep">
      <div className="max-w-3xl mx-auto px-6 py-6 flex flex-col gap-5">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-bold text-text">Findings</h2>
            <p className="text-xs text-text-mute mt-0.5">
              AI-generated findings requiring investigator review
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-text-mute">
            <span><span className="font-semibold text-yellow-600">{counts.pending}</span> pending</span>
            <span><span className="font-semibold text-green">{counts.confirmed}</span> confirmed</span>
            <span><span className="font-semibold text-text-mute">{counts.dismissed}</span> dismissed</span>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-semibold text-text-mute uppercase tracking-wide mr-1">Severity</span>
            {['all', 'high', 'medium', 'low'].map(s => (
              <button key={s} onClick={() => setFilterSeverity(s)} className={PILL(filterSeverity === s)}>
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-semibold text-text-mute uppercase tracking-wide mr-1">Status</span>
            {['all', 'pending', 'confirmed', 'dismissed'].map(s => (
              <button key={s} onClick={() => setFilterStatus(s)} className={PILL(filterStatus === s)}>
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Empty state */}
        {findings.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <div className="w-12 h-12 bg-panel border border-border rounded-xl flex items-center justify-center shadow-sm">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#878E99" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <p className="text-sm font-semibold text-text">No findings yet</p>
            <p className="text-xs text-text-mute max-w-xs">
              Run analysis on this case to detect anomalies and generate findings from the extracted documents.
            </p>
            {onRunAnalysis && (
              <button
                onClick={onRunAnalysis}
                disabled={analysisState === 'running'}
                className="mt-1 flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-teal hover:bg-teal-soft rounded-lg transition-colors duration-150 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {analysisState === 'running' && (
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                )}
                {analysisState === 'running' ? 'Running analysis…' : 'Run Analysis'}
              </button>
            )}
          </div>
        )}

        {filtered.length === 0 && findings.length > 0 && (
          <p className="text-sm text-text-mute text-center py-10">No findings match the current filters.</p>
        )}

        {/* Finding cards */}
        <div className="flex flex-col gap-3">
          {filtered.map(finding => {
            const sevStyle = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.low
            const revStyle = REVIEW_STYLES[finding.human_review_status] ?? REVIEW_STYLES.pending
            const isPending = finding.human_review_status === 'pending'
            const isProcessing = processing.has(finding.finding_id)
            const isDismissing = dismissState?.findingId === finding.finding_id

            return (
              <div
                key={finding.finding_id}
                className={`bg-panel border rounded-xl p-5 flex flex-col gap-4 transition-opacity duration-150 ${
                  finding.human_review_status === 'dismissed' ? 'opacity-60' : ''
                } ${isProcessing ? 'opacity-50 pointer-events-none' : ''} border-border`}
              >
                {/* Top row: badges + confidence */}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${sevStyle.badge}`}>
                    {finding.severity}
                  </span>
                  <span className="text-[10px] font-medium text-text-mid bg-panel-2 border border-border px-2 py-0.5 rounded-full">
                    {formatType(finding.finding_type)}
                  </span>
                  <div className="flex-1" />
                  <ConfidenceBar value={finding.confidence} />
                </div>

                {/* Statement */}
                <p className={`text-sm text-text leading-relaxed ${finding.human_review_status === 'dismissed' ? 'line-through text-text-mute' : ''}`}>
                  {finding.statement}
                </p>

                {/* Supporting documents */}
                {finding.supporting_document_ids.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] font-semibold text-text-mute uppercase tracking-wide shrink-0">Sources</span>
                    {finding.supporting_document_ids.map(id => (
                      <span key={id} className="text-[10px] bg-panel-2 border border-border text-text-mid px-2 py-0.5 rounded-full truncate max-w-[160px]" title={docMap[id] ?? id}>
                        {docMap[id] ?? id}
                      </span>
                    ))}
                  </div>
                )}

                {/* Review status + actions */}
                <div className="flex items-center gap-3 pt-1 border-t border-border flex-wrap">
                  <span className="flex items-center gap-1.5 text-xs" style={{ color: revStyle.color }}>
                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: revStyle.color }} />
                    {revStyle.label}
                  </span>
                  {finding.reviewed_by && (
                    <span className="text-[10px] text-text-mute">by {finding.reviewed_by}</span>
                  )}
                  {finding.dismissal_reason && (
                    <span className="text-[10px] text-text-mute italic">"{finding.dismissal_reason}"</span>
                  )}

                  {isPending && !isDismissing && (
                    <div className="flex items-center gap-2 ml-auto">
                      <button
                        onClick={() => handleConfirm(finding.finding_id)}
                        className="flex items-center gap-1.5 text-xs font-semibold text-green border border-green/30 hover:bg-green/5 px-3 py-1.5 rounded-lg transition-colors duration-150"
                      >
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                        Confirm
                      </button>
                      <button
                        onClick={() => setDismissState({ findingId: finding.finding_id, reason: '' })}
                        className="flex items-center gap-1.5 text-xs font-semibold text-text-mute border border-border hover:border-border-strong hover:text-text px-3 py-1.5 rounded-lg transition-colors duration-150"
                      >
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>

                {/* Inline dismiss form */}
                {isDismissing && (
                  <div className="flex flex-col gap-2 pt-2 border-t border-border">
                    <textarea
                      rows={2}
                      placeholder="Reason for dismissal (optional)…"
                      value={dismissState.reason}
                      onChange={e => setDismissState(s => s ? { ...s, reason: e.target.value } : s)}
                      className="border border-border-strong rounded-lg px-3 py-2 text-xs text-text bg-panel placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150 resize-none"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDismiss(finding.finding_id, dismissState.reason)}
                        className="text-xs font-semibold text-white bg-red hover:bg-red/80 px-4 py-1.5 rounded-lg transition-colors duration-150"
                      >
                        Confirm Dismissal
                      </button>
                      <button
                        onClick={() => setDismissState(null)}
                        className="text-xs text-text-mute hover:text-text transition-colors duration-150"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
