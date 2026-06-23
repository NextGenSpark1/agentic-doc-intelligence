export function relativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffMs = now - then
  const diffMins = Math.floor(diffMs / 60_000)
  const diffHours = Math.floor(diffMs / 3_600_000)
  const diffDays = Math.floor(diffMs / 86_400_000)

  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

export function formatDate(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function riskColor(score: number): string {
  if (score >= 0.75) return '#B4232A'
  if (score >= 0.5) return '#C77A12'
  if (score >= 0.25) return '#0E7C86'
  return '#878E99'
}

export function isStale(iso: string): boolean {
  const diffMs = Date.now() - new Date(iso).getTime()
  return diffMs >= 3 * 86_400_000
}

export function formatCaseType(ct: string): string {
  return ct
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
