import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderOpen, Clock, TrendingUp, AlertCircle,
  ArrowRight, CalendarDays, CheckCircle2, XCircle,
} from 'lucide-react';
import { getDashboardStats, getWorkspaces } from '../api/tenders';
import { StageBadge, BidDecisionBadge } from '../components/Badge';
import { StatCard } from '../components/StatCard';
import { daysUntil } from '../lib/utils';
import type { DashboardStats, TenderWorkspace, WorkspaceStage } from '../types';

const STAGE_ORDER: WorkspaceStage[] = ['new', 'analysing', 'preparing', 'submitted', 'awarded', 'lost', 'no_bid'];
const ACTIVE_STAGES: WorkspaceStage[] = ['new', 'analysing', 'preparing', 'submitted'];

function DeadlineBar({ workspace }: { workspace: TenderWorkspace }) {
  const navigate = useNavigate();
  const days = daysUntil(workspace.closing_date);
  const urgent = days <= 14;
  const overdue = days < 0;

  return (
    <div
      onClick={() => navigate(`/tenders/${workspace.id}`)}
      className="flex items-center gap-4 px-5 py-4 hover:bg-panel-2 cursor-pointer transition-colors group"
    >
      {/* Urgency strip */}
      <div className={`w-1 h-10 rounded-full flex-shrink-0 ${overdue ? 'bg-text-mute' : urgent ? 'bg-red' : 'bg-teal'}`} />

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text truncate group-hover:text-teal transition-colors">
          {workspace.title}
        </p>
        <p className="text-xs text-text-mute mt-0.5">{workspace.buyer}</p>
      </div>

      {/* Readiness */}
      <div className="hidden sm:flex flex-col items-end gap-1 flex-shrink-0 w-28">
        <div className="flex items-center gap-1.5 w-full">
          <div className="flex-1 h-1.5 bg-canvas-deep rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                workspace.readiness_score >= 80
                  ? 'bg-green'
                  : workspace.readiness_score >= 50
                  ? 'bg-teal'
                  : 'bg-amber'
              }`}
              style={{ width: `${workspace.readiness_score}%` }}
            />
          </div>
          <span className="text-xs font-medium text-text-mid w-8 text-right">{workspace.readiness_score}%</span>
        </div>
        <span className="text-[11px] text-text-mute">readiness</span>
      </div>

      {/* Deadline */}
      <div className="flex-shrink-0 text-right">
        {overdue ? (
          <span className="text-xs font-medium text-text-mute">Closed</span>
        ) : (
          <>
            <p className={`text-sm font-semibold ${urgent ? 'text-red' : 'text-text-mid'}`}>
              {days}d left
            </p>
            <p className="text-[11px] text-text-mute">
              {new Date(workspace.closing_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
            </p>
          </>
        )}
      </div>

      <ArrowRight size={14} className="text-text-mute group-hover:text-teal transition-colors flex-shrink-0" />
    </div>
  );
}

function PipelineStageCol({ stage, workspaces }: { stage: WorkspaceStage; workspaces: TenderWorkspace[] }) {
  const navigate = useNavigate();
  const stageWorkspaces = workspaces.filter((w) => w.stage === stage);

  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-2">
        <StageBadge stage={stage} />
        <span className="text-xs text-text-mute font-medium">{stageWorkspaces.length}</span>
      </div>
      <div className="space-y-2">
        {stageWorkspaces.length === 0 ? (
          <div className="h-16 border-2 border-dashed border-border rounded-lg flex items-center justify-center">
            <span className="text-xs text-text-mute">—</span>
          </div>
        ) : (
          stageWorkspaces.map((w) => (
            <div
              key={w.id}
              onClick={() => navigate(`/tenders/${w.id}`)}
              className="bg-panel border border-border rounded-lg p-3 cursor-pointer hover:border-teal hover:shadow-sm transition-all group"
            >
              <p className="text-xs font-medium text-text line-clamp-2 mb-2 group-hover:text-teal transition-colors">
                {w.title}
              </p>
              <div className="flex items-center justify-between gap-1">
                <div className="flex items-center gap-1">
                  <div className={`w-1.5 h-1.5 rounded-full ${
                    w.readiness_score >= 80 ? 'bg-green' : w.readiness_score >= 50 ? 'bg-teal' : 'bg-amber'
                  }`} />
                  <span className="text-[11px] text-text-mute">{w.readiness_score}%</span>
                </div>
                <BidDecisionBadge decision={w.bid_decision} />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [workspaces, setWorkspaces] = useState<TenderWorkspace[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDashboardStats(), getWorkspaces()]).then(([s, ws]) => {
      setStats(s);
      setWorkspaces(ws);
    }).finally(() => setLoading(false));
  }, []);

  const activeWorkspaces = workspaces
    .filter((w) => ACTIVE_STAGES.includes(w.stage))
    .sort((a, b) => daysUntil(a.closing_date) - daysUntil(b.closing_date));

  const closingSoon = activeWorkspaces.filter((w) => daysUntil(w.closing_date) <= 21);

  return (
    <div className="pt-[6.5rem] px-6 pb-12 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-7">
        <h1 className="text-xl font-bold text-text">Dashboard</h1>
        <p className="text-sm text-text-mute mt-0.5">Your tendering pipeline at a glance</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Active Tenders"
          value={loading ? '—' : stats?.active_workspaces ?? 0}
          icon={FolderOpen}
          accent="teal"
        />
        <StatCard
          label="Closing in 21 Days"
          value={loading ? '—' : stats?.closing_soon ?? 0}
          icon={Clock}
          accent="amber"
        />
        <StatCard
          label="Avg. Readiness"
          value={loading ? '—' : `${stats?.avg_readiness ?? 0}%`}
          icon={TrendingUp}
          accent="teal"
        />
        <StatCard
          label="Pending Decisions"
          value={loading ? '—' : stats?.pending_decisions ?? 0}
          icon={AlertCircle}
          accent="red"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-8">

        {/* Deadline board */}
        <div className="lg:col-span-3 bg-panel rounded-xl border border-border overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2">
              <CalendarDays size={16} className="text-teal" />
              <h2 className="text-sm font-semibold text-text">Deadline Countdown</h2>
            </div>
            <button
              onClick={() => navigate('/tenders')}
              className="text-xs text-teal hover:text-teal-soft font-medium flex items-center gap-1"
            >
              View all <ArrowRight size={12} />
            </button>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-text-mute">Loading...</div>
          ) : activeWorkspaces.length === 0 ? (
            <div className="p-8 text-center text-sm text-text-mute">No active workspaces.</div>
          ) : (
            <div className="divide-y divide-border">
              {activeWorkspaces.map((w) => (
                <DeadlineBar key={w.id} workspace={w} />
              ))}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="lg:col-span-2 flex flex-col gap-6">

          {/* Closing soon alert */}
          {!loading && closingSoon.length > 0 && (
            <div className="bg-amber-bg border border-amber/30 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertCircle size={15} className="text-amber" />
                <span className="text-sm font-semibold text-amber">Closing Soon</span>
              </div>
              <div className="space-y-2">
                {closingSoon.map((w) => (
                  <div
                    key={w.id}
                    onClick={() => navigate(`/tenders/${w.id}`)}
                    className="flex items-center justify-between cursor-pointer group"
                  >
                    <p className="text-xs text-text-mid group-hover:text-text truncate flex-1 mr-2 transition-colors">
                      {w.title}
                    </p>
                    <span className="text-xs font-semibold text-amber flex-shrink-0">
                      {daysUntil(w.closing_date)}d
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Bid decisions pending */}
          {!loading && (
            <div className="bg-panel border border-border rounded-xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 size={15} className="text-teal" />
                <span className="text-sm font-semibold text-text">Bid Decisions</span>
              </div>
              <div className="space-y-3">
                {workspaces
                  .filter((w) => ACTIVE_STAGES.includes(w.stage))
                  .map((w) => (
                    <div
                      key={w.id}
                      onClick={() => navigate(`/tenders/${w.id}`)}
                      className="flex items-center justify-between cursor-pointer group"
                    >
                      <p className="text-xs text-text-mid group-hover:text-text truncate flex-1 mr-2 transition-colors">
                        {w.title.split('—')[0].trim()}
                      </p>
                      <BidDecisionBadge decision={w.bid_decision} />
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Outcomes */}
          {!loading && (
            <div className="bg-panel border border-border rounded-xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <XCircle size={15} className="text-text-mute" />
                <span className="text-sm font-semibold text-text">Recent Outcomes</span>
              </div>
              <div className="space-y-3">
                {workspaces
                  .filter((w) => ['awarded', 'lost', 'no_bid'].includes(w.stage))
                  .map((w) => (
                    <div
                      key={w.id}
                      onClick={() => navigate(`/tenders/${w.id}`)}
                      className="flex items-center justify-between cursor-pointer group"
                    >
                      <p className="text-xs text-text-mid group-hover:text-text truncate flex-1 mr-2 transition-colors">
                        {w.title.split('—')[0].trim()}
                      </p>
                      <StageBadge stage={w.stage} />
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Pipeline stages overview */}
      <div className="bg-panel border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Pipeline Overview</h2>
          <p className="text-xs text-text-mute mt-0.5">All workspaces by stage</p>
        </div>
        <div className="p-5">
          {loading ? (
            <div className="text-center text-sm text-text-mute py-4">Loading...</div>
          ) : (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {STAGE_ORDER.map((stage) => (
                <PipelineStageCol key={stage} stage={stage} workspaces={workspaces} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
