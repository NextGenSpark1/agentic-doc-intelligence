import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, SlidersHorizontal } from 'lucide-react';
import { getTenders } from '../api/tenders';
import { StatusBadge } from '../components/Badge';
import type { Tender, TenderStatus } from '../types';

const ALL_STATUSES: TenderStatus[] = ['open', 'closed', 'draft', 'awarded'];

function formatBudget(tender: Tender): string {
  if (!tender.budget_min && !tender.budget_max) return 'N/A';
  const fmt = (n: number) =>
    n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : `${(n / 1_000).toFixed(0)}K`;
  if (tender.budget_min && tender.budget_max) return `${tender.currency} ${fmt(tender.budget_min)} – ${fmt(tender.budget_max)}`;
  return `${tender.currency} ${fmt(tender.budget_min ?? tender.budget_max!)}`;
}

export function TenderListPage() {
  const navigate = useNavigate();
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<TenderStatus | 'all'>('all');

  useEffect(() => {
    getTenders().then(setTenders).finally(() => setLoading(false));
  }, []);

  const filtered = tenders.filter((t) => {
    const matchesSearch =
      t.title.toLowerCase().includes(search.toLowerCase()) ||
      t.issuer.toLowerCase().includes(search.toLowerCase()) ||
      t.category.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="pt-[6.5rem] px-6 pb-10 max-w-6xl mx-auto">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-text">Tender Library</h1>
          <p className="text-sm text-text-mute mt-0.5">{tenders.length} tenders available</p>
        </div>
      </div>

      {/* Filters bar */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-mute" />
          <input
            type="text"
            placeholder="Search tenders…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm bg-panel border border-border rounded-lg outline-none focus:border-teal transition-colors"
          />
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={14} className="text-text-mute" />
          <div className="flex gap-1">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                statusFilter === 'all' ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              All
            </button>
            {ALL_STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1.5 rounded text-xs font-medium capitalize transition-colors ${
                  statusFilter === s ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tender cards */}
      {loading ? (
        <div className="text-center text-sm text-text-mute py-16">Loading tenders...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center text-sm text-text-mute py-16">No tenders match your search.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((tender) => (
            <div
              key={tender.id}
              onClick={() => navigate(`/tenders/${tender.id}`)}
              className="bg-panel border border-border rounded-lg p-5 hover:border-teal hover:shadow-sm cursor-pointer transition-all group"
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <h3 className="text-sm font-semibold text-text group-hover:text-teal transition-colors line-clamp-2">
                  {tender.title}
                </h3>
                <StatusBadge status={tender.status} />
              </div>

              <p className="text-xs text-text-mute mb-3 line-clamp-2">{tender.description}</p>

              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-mid">
                <span><span className="text-text-mute">Issuer:</span> {tender.issuer}</span>
                <span><span className="text-text-mute">Category:</span> {tender.category}</span>
                <span><span className="text-text-mute">Budget:</span> {formatBudget(tender)}</span>
                <span className={tender.status === 'open' ? 'text-amber font-medium' : ''}>
                  <span className="text-text-mute">Deadline:</span> {new Date(tender.deadline).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
