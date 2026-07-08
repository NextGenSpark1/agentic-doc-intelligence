import { useState, useEffect, useMemo } from 'react'
import type { TimelineEvent, Document as CaseDocument } from '../types'
import { fetchTimeline } from '../api'

function parseDate(dateStr: string): Date {
  // event_date is a Postgres date: "YYYY-MM-DD"
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatDay(date: Date): string {
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

function formatFull(date: Date): string {
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function TimelinePanel({
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
  const [events, setEvents] = useState<TimelineEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const docMap = useMemo(
    () => Object.fromEntries(docs.map(d => [d.document_id, d.filename])),
    [docs],
  )

  useEffect(() => {
    fetchTimeline(caseId)
      .then(setEvents)
      .catch(() => setError('Failed to load timeline.'))
  }, [caseId])

  // Group events by year
  const grouped = useMemo(() => {
    if (!events) return []
    const map = new Map<number, TimelineEvent[]>()
    for (const e of events) {
      const year = parseDate(e.event_date).getFullYear()
      if (!map.has(year)) map.set(year, [])
      map.get(year)!.push(e)
    }
    return Array.from(map.entries()).sort(([a], [b]) => a - b)
  }, [events])

  if (error) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <p className="text-sm text-red">{error}</p>
      </div>
    )
  }

  if (events === null) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center px-6">
          <div className="w-12 h-12 bg-panel border border-border rounded-xl flex items-center justify-center shadow-sm">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#878E99" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-text">No timeline events</p>
          <p className="text-xs text-text-mute max-w-xs">
            Run analysis to extract and sequence events from the documents in this case.
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
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto bg-canvas-deep">
      <div className="max-w-2xl mx-auto px-6 py-6 flex flex-col gap-0">

        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-text">Timeline</h2>
            <p className="text-xs text-text-mute mt-0.5">
              {events.length} event{events.length !== 1 ? 's' : ''} extracted across all documents
            </p>
          </div>
          {onRunAnalysis && (
            <button
              onClick={onRunAnalysis}
              disabled={analysisState === 'running'}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-teal hover:bg-teal-soft rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              {analysisState === 'running' && (
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              {analysisState === 'running' ? 'Running…' : 'Re-run Analysis'}
            </button>
          )}
        </div>

        {grouped.map(([year, yearEvents], groupIdx) => (
          <div key={year}>
            {/* Year marker */}
            <div className="flex items-center gap-3 mb-4" style={{ marginTop: groupIdx > 0 ? '2rem' : 0 }}>
              <span className="text-xs font-bold text-text-mute uppercase tracking-widest">{year}</span>
              <div className="flex-1 h-px bg-border" />
            </div>

            {/* Events for this year */}
            <div className="relative pl-6">
              {/* Vertical stem */}
              <div
                className="absolute left-[7px] top-2 bottom-2 w-px"
                style={{ backgroundColor: 'rgba(var(--color-teal-rgb, 0,153,153), 0.25)' }}
              />

              <div className="flex flex-col gap-0">
                {yearEvents.map((event, idx) => {
                  const date = parseDate(event.event_date)
                  const isLast = idx === yearEvents.length - 1

                  return (
                    <div key={event.event_id} className={`relative flex items-start gap-4 ${isLast ? 'pb-0' : 'pb-5'}`}>
                      {/* Dot */}
                      <div
                        className="absolute left-[-20px] top-[5px] w-3.5 h-3.5 rounded-full border-2 border-teal bg-canvas-deep shrink-0 z-10"
                      />

                      {/* Content */}
                      <div className="flex-1 bg-panel border border-border rounded-xl px-4 py-3 flex flex-col gap-1.5 hover:border-border-strong transition-colors duration-150">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm text-text leading-snug">{event.label}</p>
                          <time
                            className="text-[10px] font-mono text-text-mute shrink-0 mt-0.5"
                            title={formatFull(date)}
                          >
                            {formatDay(date)}
                          </time>
                        </div>
                        {event.document_id && docMap[event.document_id] && (
                          <span className="self-start text-[10px] bg-panel-2 border border-border text-text-mid px-2 py-0.5 rounded-full truncate max-w-[260px]" title={docMap[event.document_id]}>
                            {docMap[event.document_id]}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
