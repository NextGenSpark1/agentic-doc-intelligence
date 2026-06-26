import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  note?: string
  accent?: 'teal' | 'red' | 'default'
  icon?: LucideIcon
}

const accentMap = {
  teal:    { border: '#0E7C86', iconClass: 'bg-teal/10 text-teal' },
  red:     { border: '#B4232A', iconClass: 'bg-red-bg text-red' },
  default: { border: '#D5DAE1', iconClass: 'bg-panel-3 text-text-mute' },
}

export default function StatCard({ label, value, note, accent = 'default', icon: Icon }: StatCardProps) {
  const { border, iconClass } = accentMap[accent]

  return (
    <div
      className="bg-panel border border-border shadow-sm rounded-xl px-5 py-4 flex items-start justify-between gap-3 hover:-translate-y-0.5 hover:shadow-md transition-all duration-150"
      style={{ borderLeft: `4px solid ${border}` }}
    >
      <div className="flex flex-col min-w-0">
        <span className="text-[11px] font-semibold text-text-mute uppercase tracking-widest">{label}</span>
        <span className="text-3xl font-bold text-text tabular-nums leading-none mt-2">{value}</span>
        {note && <span className="text-xs text-text-mute mt-1.5">{note}</span>}
      </div>
      {Icon && (
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${iconClass}`}>
          <Icon size={17} strokeWidth={1.75} />
        </div>
      )}
    </div>
  )
}
