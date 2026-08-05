import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  accent?: 'teal' | 'green' | 'amber' | 'red';
}

const ACCENT_CLASSES = {
  teal: 'bg-teal/10 text-teal',
  green: 'bg-green-bg text-green',
  amber: 'bg-amber-bg text-amber',
  red: 'bg-red-bg text-red',
};

export function StatCard({ label, value, icon: Icon, accent = 'teal' }: StatCardProps) {
  return (
    <div className="bg-panel rounded-lg border border-border p-5 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${ACCENT_CLASSES[accent]}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-2xl font-bold text-text leading-none">{value}</p>
        <p className="text-xs text-text-mute mt-1">{label}</p>
      </div>
    </div>
  );
}
