import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, FileText, Loader2,
  ClipboardCheck, BarChart3, ThumbsUp, MessageSquare,
} from 'lucide-react';
import { getWorkspace, getRequirements, getBidDecision } from '../api/tenders';
import { StageBadge, BidDecisionBadge } from '../components/Badge';
import { SummaryTab } from '../components/workspace/SummaryTab';
import { RequirementsTab } from '../components/workspace/RequirementsTab';
import { ComplianceMatrixTab } from '../components/workspace/ComplianceMatrixTab';
import { BidDecisionTab } from '../components/workspace/BidDecisionTab';
import { ChatTab } from '../components/workspace/ChatTab';
import { daysUntil } from '../lib/utils';
import type { TenderWorkspace, Requirement, BidDecisionReport } from '../types';

type Tab = 'summary' | 'requirements' | 'compliance' | 'bid' | 'chat';

const TABS: { id: Tab; label: string; icon: typeof FileText }[] = [
  { id: 'summary', label: 'Summary', icon: FileText },
  { id: 'requirements', label: 'Requirements', icon: ClipboardCheck },
  { id: 'compliance', label: 'Compliance Matrix', icon: BarChart3 },
  { id: 'bid', label: 'Bid Decision', icon: ThumbsUp },
  { id: 'chat', label: 'AI Assistant', icon: MessageSquare },
];

export function TenderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [workspace, setWorkspace] = useState<TenderWorkspace | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [bidReport, setBidReport] = useState<BidDecisionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('summary');

  const prevStageRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      getWorkspace(id),
      getRequirements(id),
      getBidDecision(id),
    ]).then(([ws, reqs, bid]) => {
      setWorkspace(ws);
      prevStageRef.current = ws.stage;
      setRequirements(reqs);
      setBidReport(bid);
    }).finally(() => setLoading(false));
  }, [id]);

  const handleWorkspaceChange = useCallback((patch: Partial<TenderWorkspace>) => {
    setWorkspace((previous) => {
      if (!previous) return previous;
      const updated = { ...previous, ...patch };
      const stageJustCompleted =
        prevStageRef.current === 'analysing' && updated.stage === 'preparing';
      prevStageRef.current = updated.stage;
      if (stageJustCompleted && id) {
        getRequirements(id).then(setRequirements);
        getBidDecision(id).then(setBidReport);
      }
      return updated;
    });
  }, [id]);

  if (loading) {
    return (
      <div className="pt-[6.5rem] flex items-center justify-center py-24">
        <Loader2 size={20} className="animate-spin text-text-mute" />
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="pt-[6.5rem] px-6 text-center py-16">
        <p className="text-sm text-text-mute">Workspace not found.</p>
      </div>
    );
  }

  const days = daysUntil(workspace.closing_date);
  const isActive = ['new', 'analysing', 'preparing'].includes(workspace.stage);
  const urgent = isActive && days <= 14;

  const readinessBg =
    workspace.readiness_score >= 80 ? 'bg-green' :
    workspace.readiness_score >= 50 ? 'bg-teal' : 'bg-amber';

  return (
    <div className="pt-[6.5rem] pb-12">

      {/* Workspace header */}
      <div className={`border-b ${urgent ? 'border-amber/30 bg-amber-bg/30' : 'border-border bg-panel'}`}>
        <div className="max-w-6xl mx-auto px-6 py-5">
          <button
            onClick={() => navigate('/tenders')}
            className="flex items-center gap-1.5 text-xs text-text-mute hover:text-teal transition-colors mb-3"
          >
            <ArrowLeft size={13} />
            Tenders
          </button>

          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3 flex-wrap mb-1">
                <StageBadge stage={workspace.stage} />
                <BidDecisionBadge decision={workspace.bid_decision} />
                {workspace.reference && (
                  <span className="text-xs font-mono text-text-mute">{workspace.reference}</span>
                )}
              </div>
              <h1 className="text-xl font-bold text-text leading-snug">{workspace.title}</h1>
              <p className="text-sm text-text-mute mt-0.5">{workspace.buyer}</p>
            </div>

            {/* Readiness + deadline */}
            <div className="flex items-center gap-5 flex-shrink-0">
              <div className="text-right">
                <p className="text-xs text-text-mute mb-1">Readiness</p>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-canvas-deep rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${readinessBg}`} style={{ width: `${workspace.readiness_score}%` }} />
                  </div>
                  <span className="text-sm font-semibold text-text">{workspace.readiness_score}%</span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-text-mute mb-1">Closing</p>
                {days < 0 ? (
                  <p className="text-sm font-semibold text-text-mute">Closed</p>
                ) : (
                  <p className={`text-sm font-bold ${urgent ? 'text-amber' : 'text-text'}`}>{days} days</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Tab bar */}
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex gap-0 -mb-px overflow-x-auto">
            {TABS.map(({ id: tabId, label, icon: Icon }) => {
              const count =
                tabId === 'requirements' || tabId === 'compliance' ? requirements.length : undefined;
              return (
                <button
                  key={tabId}
                  onClick={() => setActiveTab(tabId)}
                  className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                    activeTab === tabId
                      ? 'text-teal border-teal'
                      : 'text-text-mute border-transparent hover:text-text'
                  }`}
                >
                  <Icon size={14} />
                  {label}
                  {count !== undefined && count > 0 && (
                    <span className={`text-[11px] px-1.5 rounded-full ${
                      activeTab === tabId ? 'bg-teal/15 text-teal' : 'bg-panel-3 text-text-mute'
                    }`}>
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tab content */}
      <div className="max-w-6xl mx-auto px-6 py-6">
        {activeTab === 'summary' && <SummaryTab workspace={workspace} onWorkspaceChange={handleWorkspaceChange} />}
        {activeTab === 'requirements' && <RequirementsTab requirements={requirements} />}
        {activeTab === 'compliance' && <ComplianceMatrixTab requirements={requirements} />}
        {activeTab === 'bid' && <BidDecisionTab report={bidReport} workspace={workspace} />}
        {activeTab === 'chat' && <ChatTab workspace={workspace} />}
      </div>
    </div>
  );
}
