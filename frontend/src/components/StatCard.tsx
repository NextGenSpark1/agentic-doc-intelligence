interface StatCardProps {
  label: string
  value: string | number
  note?: string
  accent?: 'teal' | 'red' | 'default'
}

const accentBorder: Record<string, string> = {
  teal: '#0E7C86',
  red: '#B4232A',
  default: '#D5DAE1',
}

export default function StatCard({ label, value, note, accent = 'default' }: StatCardProps) {
  const borderColor = accentBorder[accent]

  return (
    <div
      className="bg-panel border border-border shadow-sm rounded-lg px-4 py-3 flex flex-col gap-1"
      style={{ borderLeft: `3px solid ${borderColor}` }}
    >
      <span className="text-xs text-text-mute font-medium uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-semibold text-text">{value}</span>
      {note && <span className="text-xs text-text-mute">{note}</span>}
    </div>
  )
}
