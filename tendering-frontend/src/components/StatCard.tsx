import type { LucideIcon } from 'lucide-react';

type Accent = 'teal' | 'amber' | 'red';

const ACCENT_STYLES: Record<Accent, { icon: string; border: string }> = {
  teal:  { icon: 'text-teal bg-teal/10',   border: 'border-teal/20' },
  amber: { icon: 'text-amber bg-amber/10',  border: 'border-amber/20' },
  red:   { icon: 'text-red bg-red/10',      border: 'border-red/20' },
};

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  accent: Accent;
}

export function StatCard({ label, value, icon: Icon, accent }: StatCardProps) {
  const styles = ACCENT_STYLES[accent];
  return (
    <div className={`bg-panel rounded-xl border ${styles.border} p-5 flex items-start gap-4`}>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${styles.icon}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-text leading-none mb-1">{value}</p>
        <p className="text-xs text-text-mute">{label}</p>
      </div>
    </div>
  );
}
