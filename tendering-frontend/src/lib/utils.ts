export function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

export function formatCurrency(value?: number, currency?: string): string {
  if (!value) return 'N/A';
  const cur = currency ?? 'USD';
  if (value >= 1_000_000) return `${cur} ${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${cur} ${(value / 1_000).toFixed(0)}K`;
  return `${cur} ${value}`;
}

export function formatDate(dateStr: string, opts?: Intl.DateTimeFormatOptions): string {
  return new Date(dateStr).toLocaleDateString('en-GB', opts ?? { day: 'numeric', month: 'short', year: 'numeric' });
}

export function readinessColour(score: number): { bar: string; text: string } {
  if (score >= 80) return { bar: 'bg-green', text: 'text-green' };
  if (score >= 50) return { bar: 'bg-teal', text: 'text-teal' };
  return { bar: 'bg-amber', text: 'text-amber' };
}
