import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, CalendarDays, ArrowRight } from 'lucide-react';
import { getWorkspaces } from '../api/tenders';
import { StageBadge, BidDecisionBadge } from '../components/Badge';
import { daysUntil, formatCurrency } from '../lib/utils';
import type { TenderWorkspace, WorkspaceStage } from '../types';
import toast from 'react-hot-toast';

const STAGE_FILTERS: { label: string; value: WorkspaceStage | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'new' },
  { label: 'Analysing', value: 'analysing' },
  { label: 'Preparing', value: 'preparing' },
  { label: 'Submitted', value: 'submitted' },
  { label: 'Awarded', value: 'awarded' },
  { label: 'Lost', value: 'lost' },
];

// ─── Create Workspace Modal ───────────────────────────────────────────────────

function CreateWorkspaceModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({
    title: '',
    reference: '',
    buyer: '',
    category: '',
    closing_date: '',
    contract_value: '',
    currency: 'USD',
  });
  const [submitting, setSubmitting] = useState(false);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    setForm((previous) => ({ ...previous, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    await new Promise((resolve) => setTimeout(resolve, 900)); // mock API call
    toast.success('Workspace created — uploading documents next');
    setSubmitting(false);
    onClose();
  }

  const isValid = form.title.trim() && form.buyer.trim() && form.closing_date;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-lg">
        <div className="px-6 py-5 border-b border-border">
          <h2 className="text-base font-semibold text-text">New Tender Workspace</h2>
          <p className="text-xs text-text-mute mt-0.5">Create a workspace to track and prepare your bid</p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* Title */}
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
              Tender Title <span className="text-red">*</span>
            </label>
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              placeholder="e.g. National Broadband Infrastructure — Phase 3"
              required
              className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
            />
          </div>

          {/* Reference + Buyer in a row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Tender Reference
              </label>
              <input
                name="reference"
                value={form.reference}
                onChange={handleChange}
                placeholder="ICT/INFRA/2026/047"
                className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Category
              </label>
              <input
                name="category"
                value={form.category}
                onChange={handleChange}
                placeholder="e.g. IT & Software"
                className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
              />
            </div>
          </div>

          {/* Buyer */}
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
              Issuing Organisation <span className="text-red">*</span>
            </label>
            <input
              name="buyer"
              value={form.buyer}
              onChange={handleChange}
              placeholder="e.g. Ministry of ICT & Digital Economy"
              required
              className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
            />
          </div>

          {/* Closing date + Contract value */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Closing Date <span className="text-red">*</span>
              </label>
              <input
                name="closing_date"
                type="date"
                value={form.closing_date}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Contract Value
              </label>
              <div className="flex gap-2">
                <select
                  name="currency"
                  value={form.currency}
                  onChange={handleChange}
                  className="px-2 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal transition-colors"
                >
                  <option>USD</option>
                  <option>EUR</option>
                  <option>GBP</option>
                  <option>AED</option>
                </select>
                <input
                  name="contract_value"
                  value={form.contract_value}
                  onChange={handleChange}
                  placeholder="e.g. 12500000"
                  type="number"
                  className="flex-1 min-w-0 px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
                />
              </div>
            </div>
          </div>

          <div className="pt-2 bg-panel-2 -mx-6 px-6 py-4 -mb-5 rounded-b-xl border-t border-border flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-text-mid hover:text-text transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isValid || submitting}
              className="px-5 py-2 bg-navy hover:bg-navy-soft disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating…
                </>
              ) : (
                'Create Workspace'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Workspace Card ───────────────────────────────────────────────────────────

function WorkspaceCard({ workspace }: { workspace: TenderWorkspace }) {
  const navigate = useNavigate();
  const days = daysUntil(workspace.closing_date);
  const isActive = ['new', 'analysing', 'preparing', 'submitted'].includes(workspace.stage);
  const urgent = isActive && days <= 14;

  const readinessBg =
    workspace.readiness_score >= 80 ? 'bg-green' :
    workspace.readiness_score >= 50 ? 'bg-teal' : 'bg-amber';

  return (
    <div
      onClick={() => navigate(`/tenders/${workspace.id}`)}
      className={`bg-panel border rounded-xl p-5 cursor-pointer hover:shadow-md transition-all group ${
        urgent ? 'border-amber/50 hover:border-amber' : 'border-border hover:border-teal'
      }`}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-text group-hover:text-teal transition-colors line-clamp-2 leading-snug">
            {workspace.title}
          </h3>
          <p className="text-xs text-text-mute mt-1">{workspace.reference}</p>
        </div>
        <StageBadge stage={workspace.stage} />
      </div>

      {/* Buyer + Category */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-mid mb-4">
        <span className="flex items-center gap-1">
          <span className="text-text-mute">Buyer:</span> {workspace.buyer}
        </span>
        {workspace.category && (
          <span className="flex items-center gap-1">
            <span className="text-text-mute">Category:</span> {workspace.category}
          </span>
        )}
        <span className="flex items-center gap-1">
          <span className="text-text-mute">Value:</span> {formatCurrency(workspace.contract_value, workspace.currency)}
        </span>
      </div>

      {/* Readiness bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-text-mute">Readiness</span>
          <span className={`text-xs font-semibold ${
            workspace.readiness_score >= 80 ? 'text-green' :
            workspace.readiness_score >= 50 ? 'text-teal' : 'text-amber'
          }`}>{workspace.readiness_score}%</span>
        </div>
        <div className="w-full h-2 bg-canvas-deep rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${readinessBg}`}
            style={{ width: `${workspace.readiness_score}%` }}
          />
        </div>
        <div className="flex gap-3 mt-1.5 text-[11px] text-text-mute">
          <span><span className="text-green font-medium">{workspace.requirements_met}</span> met</span>
          <span><span className="text-amber font-medium">{workspace.requirements_partial}</span> partial</span>
          <span><span className="text-red font-medium">{workspace.requirements_gap}</span> gap</span>
          <span className="ml-auto">{workspace.requirements_count} requirements</span>
        </div>
      </div>

      {/* Bottom row */}
      <div className="flex items-center justify-between">
        <BidDecisionBadge decision={workspace.bid_decision} />

        <div className="flex items-center gap-2 text-xs">
          <CalendarDays size={12} className={urgent ? 'text-amber' : 'text-text-mute'} />
          {days < 0 ? (
            <span className="text-text-mute">Closed {new Date(workspace.closing_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span>
          ) : (
            <span className={urgent ? 'text-amber font-semibold' : 'text-text-mid'}>
              {days}d · {new Date(workspace.closing_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
            </span>
          )}
          <ArrowRight size={12} className="text-text-mute group-hover:text-teal transition-colors ml-1" />
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function TenderListPage() {
  const [workspaces, setWorkspaces] = useState<TenderWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState<WorkspaceStage | 'all'>('all');
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    getWorkspaces().then(setWorkspaces).finally(() => setLoading(false));
  }, []);

  const filtered = workspaces.filter((workspace) => {
    const searchQuery = search.toLowerCase();
    const matchesSearch =
      workspace.title.toLowerCase().includes(searchQuery) ||
      workspace.buyer.toLowerCase().includes(searchQuery) ||
      workspace.reference.toLowerCase().includes(searchQuery) ||
      workspace.category.toLowerCase().includes(searchQuery);
    const matchesStage = stageFilter === 'all' || workspace.stage === stageFilter;
    return matchesSearch && matchesStage;
  });

  return (
    <div className="pt-[6.5rem] px-6 pb-12 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-text">My Tenders</h1>
          <p className="text-sm text-text-mute mt-0.5">
            {workspaces.length} workspace{workspaces.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-navy hover:bg-navy-soft text-white text-sm font-semibold rounded-lg transition-colors self-start"
        >
          <Plus size={15} />
          New Tender
        </button>
      </div>

      {/* Search + Stage filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative max-w-xs w-full">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-mute" />
          <input
            type="text"
            placeholder="Search tenders…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm bg-panel border border-border rounded-lg outline-none focus:border-teal transition-colors"
          />
        </div>

        <div className="flex gap-1.5 flex-wrap">
          {STAGE_FILTERS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setStageFilter(value as WorkspaceStage | 'all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                stageFilter === value
                  ? 'bg-navy text-white'
                  : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Workspace grid */}
      {loading ? (
        <div className="text-center text-sm text-text-mute py-16">Loading workspaces...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-sm text-text-mute mb-2">No workspaces match your filters.</p>
          <button onClick={() => setShowCreate(true)} className="text-sm text-teal hover:underline font-medium">
            Create your first workspace →
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((workspace) => (
            <WorkspaceCard key={workspace.id} workspace={workspace} />
          ))}
        </div>
      )}

      {/* Modal */}
      {showCreate && <CreateWorkspaceModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
