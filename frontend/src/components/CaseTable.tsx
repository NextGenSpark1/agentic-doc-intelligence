import { useNavigate } from 'react-router-dom'
import type { Case } from '../types'
import Badge from './Badge'
import { relativeTime, riskColor, isStale, formatCaseType } from '../utils'

interface CaseTableProps {
  cases: Case[]
}

const columns = ['Case ID', 'Title', 'Type', 'Status', 'Docs', 'Risk', 'Last Activity']

export default function CaseTable({ cases }: CaseTableProps) {
  const navigate = useNavigate()

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
        <p className="text-xs text-text-mute mt-1">Create a new case to get started</p>
      </div>
    )
  }

  return (
    <div className="bg-panel border border-border rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-[160px_1fr_140px_160px_90px_120px_130px] gap-x-4 bg-panel-3 border-b-2 border-border px-5 py-3">
        {columns.map((col) => (
          <span key={col} className="text-[11px] font-semibold text-text-mid uppercase tracking-widest">
            {col}
          </span>
        ))}
      </div>

      {/* Rows */}
      {cases.map((c, idx) => {
        const stale = isStale(c.created_at)
        const isLast = idx === cases.length - 1
        const color = riskColor(c.risk_score)
        const riskPct = Math.round(c.risk_score * 100)

        return (
          <div
            key={c.case_id}
            onClick={() => navigate(`/cases/${c.case_id}`)}
            className={`
              grid grid-cols-[160px_1fr_140px_160px_90px_120px_130px] gap-x-4
              items-center px-5 py-3.5 cursor-pointer
              hover:bg-teal/[0.04] transition-colors duration-150 group
              ${!isLast ? 'border-b border-border' : ''}
            `}
            style={stale ? { borderLeft: '3px solid #C77A12' } : { borderLeft: '3px solid transparent' }}
          >
            {/* Case ID */}
            <span className="font-mono text-sm text-teal font-semibold truncate group-hover:text-teal-soft transition-colors">
              {c.case_id}
            </span>

            {/* Title + subtitle */}
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-medium text-text truncate">{c.title}</span>
              <span className="text-xs text-text-mute truncate">{c.lead_investigator}</span>
            </div>

            {/* Type */}
            <span className="text-xs text-text-mid">{formatCaseType(c.case_type)}</span>

            {/* Status */}
            <Badge status={c.status} />

            {/* Docs */}
            <span className="text-sm text-text-mid tabular-nums font-medium">
              {c.doc_count ?? '—'}
            </span>

            {/* Risk */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-panel-3 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${riskPct}%`, backgroundColor: color }}
                />
              </div>
              <span className="text-xs font-mono text-text-mid w-6 text-right tabular-nums">{riskPct}</span>
            </div>

            {/* Last Activity */}
            <span className="text-xs text-text-mute">{relativeTime(c.created_at)}</span>
          </div>
        )
      })}
    </div>
  )
}
