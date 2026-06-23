interface BadgeProps {
  status: string
}

function statusStyles(status: string): string {
  const s = status.toLowerCase()
  if (s === 'pending review') {
    return 'bg-amber-bg text-amber border border-amber/20'
  }
  if (s === 'report ready') {
    return 'bg-green-bg text-green border border-green/20'
  }
  if (s === 'extracting' || s === 'active') {
    return 'bg-teal/10 text-teal border border-teal/20'
  }
  // intake, archived, default
  return 'bg-panel-3 text-text-mute border border-border'
}

export default function Badge({ status }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize
        ${statusStyles(status)}
      `}
    >
      {status}
    </span>
  )
}
