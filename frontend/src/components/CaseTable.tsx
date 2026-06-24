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
      <div className="bg-panel border border-border rounded-lg px-6 py-10 text-center text-text-mute text-sm">
        No cases found.
      </div>
    )
  }

  return (
    <div className="bg-panel border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-[160px_1fr_140px_160px_90px_120px_130px] gap-x-4 bg-panel-2 border-b border-border px-4 py-2">
        {columns.map((col) => (
          <span key={col} className="text-xs font-semibold text-text-mute uppercase tracking-wide">
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
              items-center px-4 py-3 cursor-pointer
              hover:bg-panel-2 transition-colors duration-150
              ${!isLast ? 'border-b border-border' : ''}
            `}
            style={stale ? { borderLeft: '3px solid #C77A12' } : { borderLeft: '3px solid transparent' }}
          >
            {/* Case ID */}
            <span className="font-mono text-sm text-navy font-medium truncate">{c.case_id}</span>

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
            <span className="text-sm text-text-mid tabular-nums">
              {c.doc_count ?? '—'}
            </span>

            {/* Risk */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-panel-3 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${riskPct}%`, backgroundColor: color }}
                />
              </div>
              <span className="text-xs font-mono text-text-mid w-6 text-right">{riskPct}</span>
            </div>

            {/* Last Activity */}
            <span className="text-xs text-text-mute">{relativeTime(c.created_at)}</span>

          </div>
        )
      })}
    </div>
  )
}
