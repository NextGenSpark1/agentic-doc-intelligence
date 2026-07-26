import { useState, useEffect, useMemo } from 'react'
import type { TimelineEvent, Document as CaseDocument } from '../types'
import { fetchTimeline, createTimelineEvent, updateTimelineEvent, deleteTimelineEvent } from '../api'

function parseDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatDay(date: Date): string {
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

function formatFull(date: Date): string {
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

interface EventFormState {
  event_date: string
  label: string
  document_id: string
}

function EventModal({
  initial,
  docs,
  onSave,
  onClose,
  saving,
}: {
  initial?: EventFormState
  docs: CaseDocument[]
  onSave: (data: EventFormState) => void
  onClose: () => void
  saving: boolean
}) {
  const [form, setForm] = useState<EventFormState>(
    initial ?? { event_date: '', label: '', document_id: '' }
  )

  function set(field: keyof EventFormState, value: string) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="bg-panel border border-border rounded-xl w-full max-w-md shadow-xl">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <p className="text-sm font-semibold text-text">{initial ? 'Edit event' : 'Add event'}</p>
          <button onClick={onClose} className="text-text-mute hover:text-text text-lg leading-none">×</button>
        </div>
        <div className="px-5 py-4 flex flex-col gap-4">
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">Date</label>
            <input
              type="date"
              value={form.event_date}
              onChange={e => set('event_date', e.target.value)}
              className="w-full bg-canvas-deep border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-teal/30"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">Label</label>
            <input
              type="text"
              value={form.label}
              onChange={e => set('label', e.target.value)}
              placeholder="e.g. Contract signed, Payment issued"
              className="w-full bg-canvas-deep border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">
              Document <span className="font-normal normal-case tracking-normal text-text-mute">(optional)</span>
            </label>
            <select
              value={form.document_id}
              onChange={e => set('document_id', e.target.value)}
              className="w-full bg-canvas-deep border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none"
            >
              <option value="">No document</option>
              {docs.map(d => (
                <option key={d.document_id} value={d.document_id}>{d.filename}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="px-5 py-4 border-t border-border flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-mute border border-border rounded-lg hover:border-border-strong transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onSave(form)}
            disabled={saving || !form.event_date || !form.label.trim()}
            className="px-4 py-2 text-sm font-semibold text-white bg-navy rounded-lg hover:bg-navy-soft transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
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
  const [modal, setModal] = useState<{ mode: 'add' } | { mode: 'edit'; event: TimelineEvent } | null>(null)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const docMap = useMemo(
    () => Object.fromEntries(docs.map(d => [d.document_id, d.filename])),
    [docs],
  )

  useEffect(() => {
    fetchTimeline(caseId)
      .then(setEvents)
      .catch(() => setError('Failed to load timeline.'))
  }, [caseId])

  const grouped = useMemo(() => {
    if (!events) return []
    const byYear = new Map<number, TimelineEvent[]>()
    for (const e of events) {
      const year = parseDate(e.event_date).getFullYear()
      if (!byYear.has(year)) byYear.set(year, [])
      byYear.get(year)!.push(e)
    }
    return Array.from(byYear.entries()).sort(([a], [b]) => a - b)
  }, [events])

  async function handleSave(form: EventFormState) {
    setSaving(true)
    try {
      if (modal?.mode === 'edit') {
        const updated = await updateTimelineEvent(caseId, modal.event.event_id, {
          event_date: form.event_date,
          label: form.label,
          document_id: form.document_id || null,
        })
        setEvents(prev => prev ? prev.map(e => e.event_id === updated.event_id ? updated : e).sort((a, b) => a.event_date.localeCompare(b.event_date)) : prev)
      } else {
        const created = await createTimelineEvent(caseId, {
          event_date: form.event_date,
          label: form.label,
          document_id: form.document_id || null,
        })
        setEvents(prev => prev ? [...prev, created].sort((a, b) => a.event_date.localeCompare(b.event_date)) : [created])
      }
      setModal(null)
    } catch {
      // keep modal open on error
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(eventId: string) {
    if (!confirm('Delete this event?')) return
    setDeletingId(eventId)
    try {
      await deleteTimelineEvent(caseId, eventId)
      setEvents(prev => prev ? prev.filter(e => e.event_id !== eventId) : prev)
    } finally {
      setDeletingId(null)
    }
  }

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
      <>
        {modal && (
          <EventModal
            initial={modal.mode === 'edit' ? { event_date: modal.event.event_date, label: modal.event.label, document_id: modal.event.document_id ?? '' } : undefined}
            docs={docs}
            onSave={handleSave}
            onClose={() => setModal(null)}
            saving={saving}
          />
        )}
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
              Run analysis to extract events, or add them manually.
            </p>
            <div className="flex items-center gap-2 mt-1">
              <button
                onClick={() => setModal({ mode: 'add' })}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-navy hover:bg-navy-soft rounded-lg transition-colors"
              >
                + Add Event
              </button>
              {onRunAnalysis && (
                <button
                  onClick={onRunAnalysis}
                  disabled={analysisState === 'running'}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-teal hover:bg-teal-soft rounded-lg transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {analysisState === 'running' && (
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  {analysisState === 'running' ? 'Running…' : 'Run Analysis'}
                </button>
              )}
            </div>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      {modal && (
        <EventModal
          initial={modal.mode === 'edit' ? { event_date: modal.event.event_date, label: modal.event.label, document_id: modal.event.document_id ?? '' } : undefined}
          docs={docs}
          onSave={handleSave}
          onClose={() => setModal(null)}
          saving={saving}
        />
      )}

      <div className="flex-1 overflow-y-auto bg-canvas-deep">
        <div className="max-w-2xl mx-auto px-6 py-6 flex flex-col gap-0">

          {/* Header */}
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-text">Timeline</h2>
              <p className="text-xs text-text-mute mt-0.5">
                {events.length} event{events.length !== 1 ? 's' : ''} across all documents
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setModal({ mode: 'add' })}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-navy hover:bg-navy-soft rounded-lg transition-colors"
              >
                + Add
              </button>
              {onRunAnalysis && (
                <button
                  onClick={onRunAnalysis}
                  disabled={analysisState === 'running'}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-teal hover:bg-teal-soft rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {analysisState === 'running' && (
                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  {analysisState === 'running' ? 'Running…' : 'Re-run Analysis'}
                </button>
              )}
            </div>
          </div>

          {grouped.map(([year, yearEvents], groupIdx) => (
            <div key={year}>
              <div className="flex items-center gap-3 mb-4" style={{ marginTop: groupIdx > 0 ? '2rem' : 0 }}>
                <span className="text-xs font-bold text-text-mute uppercase tracking-widest">{year}</span>
                <div className="flex-1 h-px bg-border" />
              </div>

              <div className="relative pl-6">
                <div
                  className="absolute left-[7px] top-2 bottom-2 w-px"
                  style={{ backgroundColor: 'rgba(var(--color-teal-rgb, 0,153,153), 0.25)' }}
                />

                <div className="flex flex-col gap-0">
                  {yearEvents.map((event, idx) => {
                    const date = parseDate(event.event_date)
                    const isLast = idx === yearEvents.length - 1
                    const isDeleting = deletingId === event.event_id
                    const isManual = (event as TimelineEvent & { source?: string }).source === 'manual'

                    return (
                      <div key={event.event_id} className={`relative flex items-start gap-4 ${isLast ? 'pb-0' : 'pb-5'}`}>
                        <div className="absolute left-[-20px] top-[5px] w-3.5 h-3.5 rounded-full border-2 border-teal bg-canvas-deep shrink-0 z-10" />

                        <div className="flex-1 bg-panel border border-border rounded-xl px-4 py-3 flex flex-col gap-1.5 hover:border-border-strong transition-colors duration-150 group">
                          <div className="flex items-start justify-between gap-3">
                            <p className="text-sm text-text leading-snug">{event.label}</p>
                            <div className="flex items-center gap-2 shrink-0">
                              <time className="text-[10px] font-mono text-text-mute mt-0.5" title={formatFull(date)}>
                                {formatDay(date)}
                              </time>
                              {/* Edit / Delete — always visible, not just on hover */}
                              <button
                                onClick={() => setModal({ mode: 'edit', event })}
                                className="text-text-mute hover:text-text transition-colors text-xs px-1"
                                title="Edit event"
                              >
                                ✎
                              </button>
                              <button
                                onClick={() => handleDelete(event.event_id)}
                                disabled={isDeleting}
                                className="text-text-mute hover:text-red-500 transition-colors text-xs px-1 disabled:opacity-40"
                                title="Delete event"
                              >
                                {isDeleting ? '…' : '✕'}
                              </button>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-wrap">
                            {event.document_id && docMap[event.document_id] && (
                              <span className="text-[10px] bg-panel-2 border border-border text-text-mid px-2 py-0.5 rounded-full truncate max-w-[220px]" title={docMap[event.document_id]}>
                                {docMap[event.document_id]}
                              </span>
                            )}
                            {isManual && (
                              <span className="text-[10px] text-text-mute border border-border px-2 py-0.5 rounded-full">manual</span>
                            )}
                          </div>
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
    </>
  )
}
