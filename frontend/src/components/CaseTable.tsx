import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Case } from '../types'
import Badge from './Badge'
import { relativeTime, riskColor, formatCaseType } from '../utils'

const COLS = 'grid-cols-[36px_160px_1fr_140px_160px_90px_120px_130px_32px]'
const HEADER_COLS = ['', 'Case ID', 'Title', 'Type', 'Status', 'Docs', 'Risk', 'Last Activity', '']

function statusAccent(status: string): string {
  const s = status.toLowerCase()
  if (s === 'active') return '#0E7C86'
  if (s === 'pending review') return '#C77A12'
  if (s === 'closed' || s === 'archived') return '#878E99'
  return '#1E3A5F' // intake / default
}

interface CaseTableProps {
  cases: Case[]
  onDelete: (caseId: string) => Promise<void>
  onBulkDelete: (caseIds: string[]) => Promise<void>
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}

export default function CaseTable({ cases, onDelete, onBulkDelete }: CaseTableProps) {
  const navigate = useNavigate()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false)
  const [bulkDeleting, setBulkDeleting] = useState(false)

  const allSelected = cases.length > 0 && cases.every(c => selectedIds.has(c.case_id))
  const someSelected = selectedIds.size > 0

  function toggleAll() {
    setSelectedIds(allSelected ? new Set() : new Set(cases.map(c => c.case_id)))
  }

  function toggleOne(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  async function handleConfirmDelete(caseId: string) {
    setDeletingId(caseId)
    setConfirmDeleteId(null)
    try {
      await onDelete(caseId)
    } finally {
      setDeletingId(null)
      setSelectedIds(prev => { const next = new Set(prev); next.delete(caseId); return next })
    }
  }

  async function handleConfirmBulkDelete() {
    setBulkDeleting(true)
    setConfirmBulkDelete(false)
    try {
      await onBulkDelete(Array.from(selectedIds))
      setSelectedIds(new Set())
    } finally {
      setBulkDeleting(false)
    }
  }

  if (cases.length === 0) {
    return (
      <div className="bg-panel border border-border rounded-xl shadow-sm px-6 py-14 text-center">
        <div className="w-10 h-10 bg-panel-3 rounded-full flex items-center justify-center mx-auto mb-3">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#878E99" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </div>
        <p className="text-sm font-medium text-text-mid">No cases found</p>
        <p className="text-xs text-text-mute mt-1">Try a different filter or search term</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Bulk action bar */}
      {someSelected && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-panel border border-border rounded-xl shadow-sm">
          {confirmBulkDelete ? (
            <>
              <span className="text-sm text-red font-medium flex-1">
                Delete {selectedIds.size} case{selectedIds.size > 1 ? 's' : ''}? This cannot be undone.
              </span>
              <button
                onClick={handleConfirmBulkDelete}
                disabled={bulkDeleting}
                className="text-sm font-semibold text-red hover:underline disabled:opacity-50"
              >
                {bulkDeleting ? 'Deleting…' : 'Delete'}
              </button>
              <button onClick={() => setConfirmBulkDelete(false)} className="text-sm text-text-mute hover:text-text">
                Cancel
              </button>
            </>
          ) : (
            <>
              <span className="text-sm text-text-mid flex-1">{selectedIds.size} selected</span>
              <button
                onClick={() => setConfirmBulkDelete(true)}
                className="text-sm font-semibold text-red hover:text-red/80 transition-colors flex items-center gap-1.5"
              >
                <TrashIcon /> Delete selected
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-sm text-text-mute hover:text-text transition-colors"
              >
                ✕ Clear
              </button>
            </>
          )}
        </div>
      )}

      <div className="bg-panel border border-border rounded-xl shadow-sm overflow-hidden">
        {/* Header */}
        <div className={`grid ${COLS} gap-x-4 bg-panel-3 border-b-2 border-border px-5 py-3 items-center`}>
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleAll}
            className="accent-teal cursor-pointer"
            title={allSelected ? 'Deselect all' : 'Select all'}
          />
          {HEADER_COLS.slice(1).map((col) => (
            <span key={col} className="text-[11px] font-semibold text-text-mid uppercase tracking-widest">
              {col}
            </span>
          ))}
        </div>

        {/* Rows */}
        {cases.map((c, idx) => {
          const isLast = idx === cases.length - 1
          const color = riskColor(c.risk_score)
          const riskPct = Math.round(c.risk_score * 100)

          if (deletingId === c.case_id) {
            return (
              <div
                key={c.case_id}
                className={`px-5 py-3.5 flex items-center gap-2 ${!isLast ? 'border-b border-border' : ''}`}
              >
                <span className="text-sm text-text-mute italic">Deleting…</span>
              </div>
            )
          }

          if (confirmDeleteId === c.case_id) {
            return (
              <div
                key={c.case_id}
                className={`px-5 py-3 flex items-center gap-3 bg-red-bg ${!isLast ? 'border-b border-border' : ''}`}
              >
                <span className="text-sm text-red flex-1">
                  Delete <span className="font-semibold">"{c.title}"</span>? This cannot be undone.
                </span>
                <button
                  onClick={() => handleConfirmDelete(c.case_id)}
                  className="text-sm font-semibold text-red hover:underline shrink-0"
                >
                  Delete
                </button>
                <button
                  onClick={() => setConfirmDeleteId(null)}
                  className="text-sm text-text-mute hover:text-text shrink-0"
                >
                  Cancel
                </button>
              </div>
            )
          }

          return (
            <div
              key={c.case_id}
              onClick={() => navigate(`/cases/${c.case_id}`)}
              className={`
                grid ${COLS} gap-x-4 items-center px-5 py-3.5 cursor-pointer
                hover:bg-teal/[0.06] transition-colors duration-150 group
                ${!isLast ? 'border-b border-border' : ''}
              `}
              style={{ borderLeft: `3px solid ${statusAccent(c.status)}` }}
            >
              {/* Checkbox */}
              <input
                type="checkbox"
                checked={selectedIds.has(c.case_id)}
                onClick={e => e.stopPropagation()}
                onChange={() => toggleOne(c.case_id)}
                className="accent-teal cursor-pointer"
              />

              {/* Case ID */}
              <span className="font-mono text-sm text-teal font-semibold truncate group-hover:text-teal-soft transition-colors">
                {c.case_id}
              </span>

              {/* Title + investigator */}
              <div className="flex flex-col min-w-0">
                <span className="text-sm font-medium text-text truncate">{c.title}</span>
                <span className="text-xs text-text-mute truncate">{c.lead_investigator}</span>
              </div>

              {/* Type */}
              <span className="text-xs text-text-mid">{formatCaseType(c.case_type)}</span>

              {/* Status */}
              <Badge status={c.status} />

              {/* Docs */}
              <span className="text-sm text-text-mid tabular-nums font-medium">{c.doc_count ?? '—'}</span>

              {/* Risk */}
              <div
                className="flex items-center gap-2"
                title={`Risk score: ${riskPct}% — derived from confirmed finding severity and count`}
              >
                <div className="flex-1 h-1.5 bg-panel-3 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${riskPct}%`, backgroundColor: color }} />
                </div>
                <span className="text-xs font-mono text-text-mid w-6 text-right tabular-nums">{riskPct}</span>
              </div>

              {/* Last Activity */}
              <span className="text-xs text-text-mute">{relativeTime(c.created_at)}</span>

              {/* Delete button */}
              <button
                onClick={e => { e.stopPropagation(); setConfirmDeleteId(c.case_id) }}
                title="Delete case"
                className="opacity-0 group-hover:opacity-100 text-text-mute hover:text-red transition-all duration-150 flex items-center justify-center"
              >
                <TrashIcon />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
