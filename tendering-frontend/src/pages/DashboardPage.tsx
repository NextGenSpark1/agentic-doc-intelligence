import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileSearch, Clock, CheckCircle, TrendingUp } from 'lucide-react';
import { getDashboardStats, getTenders } from '../api/tenders';
import { StatCard } from '../components/StatCard';
import { StatusBadge } from '../components/Badge';
import type { DashboardStats, Tender } from '../types';

export function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentTenders, setRecentTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDashboardStats(), getTenders()]).then(([s, tenders]) => {
      setStats(s);
      setRecentTenders(tenders.slice(0, 4));
    }).finally(() => setLoading(false));
  }, []);

  return (
    <div className="pt-[6.5rem] px-6 pb-10 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text">Dashboard</h1>
        <p className="text-sm text-text-mute mt-0.5">Overview of active tenders and compliance status</p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Active Tenders" value={loading ? '—' : stats?.active_tenders ?? 0} icon={FileSearch} accent="teal" />
        <StatCard label="Closing Soon" value={loading ? '—' : stats?.closing_soon ?? 0} icon={Clock} accent="amber" />
        <StatCard label="Compliance Checks" value={loading ? '—' : stats?.compliance_checks ?? 0} icon={CheckCircle} accent="green" />
        <StatCard label="Avg. Compliance Score" value={loading ? '—' : `${stats?.avg_compliance_score ?? 0}%`} icon={TrendingUp} accent="teal" />
      </div>

      {/* Recent tenders */}
      <div className="bg-panel rounded-lg border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Recent Tenders</h2>
          <button onClick={() => navigate('/tenders')} className="text-xs text-teal hover:underline font-medium">
            View all
          </button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-sm text-text-mute">Loading...</div>
        ) : (
          <div className="divide-y divide-border">
            {recentTenders.map((tender) => (
              <div
                key={tender.id}
                onClick={() => navigate(`/tenders/${tender.id}`)}
                className="flex items-center justify-between px-5 py-3.5 hover:bg-panel-2 cursor-pointer transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text truncate">{tender.title}</p>
                  <p className="text-xs text-text-mute mt-0.5">{tender.issuer} · {tender.category}</p>
                </div>
                <div className="flex items-center gap-4 ml-4 flex-shrink-0">
                  <span className="text-xs text-text-mute hidden sm:block">
                    Deadline: {new Date(tender.deadline).toLocaleDateString()}
                  </span>
                  <StatusBadge status={tender.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
