import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ArrowLeft, FileText, Loader2,
  ClipboardCheck, BarChart3, ThumbsUp, MessageSquare, Sparkles,
} from 'lucide-react';
import { getWorkspace, getRequirements, getBidDecision, getLibraryDocuments, getEvidenceLinks, reviewEvidenceLink, generateBidDecision } from '../api/tenders';
import { StageBadge, BidDecisionBadge } from '../components/Badge';
import { SummaryTab } from '../components/workspace/SummaryTab';
import { RequirementsTab } from '../components/workspace/RequirementsTab';
import { ComplianceMatrixTab } from '../components/workspace/ComplianceMatrixTab';
import { BidDecisionTab } from '../components/workspace/BidDecisionTab';
import { ChatTab, CHAT_STARTER } from '../components/workspace/ChatTab';
import type { ChatMsg } from '../components/workspace/ChatTab';
import { daysUntil } from '../lib/utils';
import type { TenderWorkspace } from '../types';

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
  const queryClient = useQueryClient();
  const [workspace, setWorkspace] = useState<TenderWorkspace | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('summary');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>(CHAT_STARTER);
  const [generatingBidDecision, setGeneratingBidDecision] = useState(false);
  const prevStageRef = useRef<string | null>(null);
  const analysisStartRef = useRef(0);

  const { data: fetchedWorkspace, isLoading: loadingWorkspace } = useQuery({
    queryKey: ['workspace', id],
    queryFn: () => getWorkspace(id!),
    enabled: !!id,
  });
  const { data: requirements = [], isLoading: loadingRequirements } = useQuery({
    queryKey: ['requirements', id],
    queryFn: () => getRequirements(id!),
    enabled: !!id,
  });
  const { data: bidReport = null, isLoading: loadingBid } = useQuery({
    queryKey: ['bid-report', id],
    queryFn: () => getBidDecision(id!).catch(() => null),
    enabled: !!id,
  });
  const { data: libraryDocs = [] } = useQuery({
    queryKey: ['library-docs'],
    queryFn: getLibraryDocuments,
  });
  const { data: evidenceLinks = [], refetch: refetchEvidence } = useQuery({
    queryKey: ['evidence-links', id],
    queryFn: () => getEvidenceLinks(id!),
    enabled: !!id,
  });

  const loading = loadingWorkspace || loadingRequirements || loadingBid;

  useEffect(() => {
    if (!fetchedWorkspace) return;
    setWorkspace((prev) => {
      if (!prev) {
        prevStageRef.current = fetchedWorkspace.stage;
        return fetchedWorkspace;
      }
      if (prev.readiness_score === fetchedWorkspace.readiness_score) return prev;
      return { ...prev, readiness_score: fetchedWorkspace.readiness_score };
    });
  }, [fetchedWorkspace]);

  const handleWorkspaceChange = useCallback((patch: Partial<TenderWorkspace>) => {
    setWorkspace((previous) => {
      if (!previous) return previous;
      const updated = { ...previous, ...patch };
      const stageJustCompleted =
        prevStageRef.current === 'analysing' && updated.stage === 'preparing';
      prevStageRef.current = updated.stage;
      if (stageJustCompleted && id) {
        queryClient.invalidateQueries({ queryKey: ['requirements', id] });
        queryClient.invalidateQueries({ queryKey: ['bid-report', id] });
        queryClient.invalidateQueries({ queryKey: ['evidence-links', id] });
      }
      // Track when analysis begins so the polling loop knows how long it's been running.
      if (patch.stage === 'analysing' && analysisStartRef.current === 0) {
        analysisStartRef.current = Date.now();
      }
      return updated;
    });
  }, [id, queryClient]);

  // Workspace-level analysis polling. Lives here (not in SummaryTab) so it keeps running while
  // the user reads requirements or the compliance matrix — otherwise the loading toast stays
  // stuck at 'running' because the transition detector was unmounted with the tab.
  const isAnalysing = workspace?.stage === 'analysing';
  useEffect(() => {
    if (!id || !isAnalysing) return;
    if (analysisStartRef.current === 0) {
      analysisStartRef.current = Date.now();
    }
    const interval = setInterval(async () => {
      try {
        const updated = await getWorkspace(id);
        if (updated.stage !== 'analysing') {
          if (updated.stage === 'preparing') {
            toast.success('Analysis complete — check the Requirements tab', { id: 'analysis' });
          }
          analysisStartRef.current = 0;
          handleWorkspaceChange({
            stage: updated.stage,
            ai_summary: updated.ai_summary,
            readiness_score: updated.readiness_score,
          });
          queryClient.invalidateQueries({ queryKey: ['workspace', id] });
        } else if (Date.now() - analysisStartRef.current > 10 * 60 * 1000) {
          toast.error('Analysis is taking too long — check Railway logs for errors',
                      { id: 'analysis' });
          analysisStartRef.current = 0;
        }
      } catch { /* silent — next poll retries */ }
    }, 4000);
    return () => clearInterval(interval);
  }, [id, isAnalysing, handleWorkspaceChange, queryClient]);

  // Bid decision generation lives at page level so leaving the Bid Decision tab does not lose
  // the spinner or the request. BidDecisionTab reads `generatingBidDecision` as a prop.
  const handleGenerateBidDecision = useCallback(async () => {
    if (!id || generatingBidDecision) return;
    setGeneratingBidDecision(true);
    toast.loading('Generating bid decision…', { id: 'bid-decision' });
    try {
      const generated = await generateBidDecision(id);
      queryClient.setQueryData(['bid-report', id], generated);
      toast.success('Bid decision generated', { id: 'bid-decision' });
    } catch {
      toast.error('Failed to generate bid decision — ensure analysis has completed',
                  { id: 'bid-decision' });
    } finally {
      setGeneratingBidDecision(false);
    }
  }, [id, generatingBidDecision, queryClient]);

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

        {/* Running-operation banner — always visible while an op is in flight, on every tab */}
        {(isAnalysing || generatingBidDecision) && (
          <div className="bg-teal/10 border-t border-teal/20">
            <div className="max-w-6xl mx-auto px-6 py-2 flex items-center gap-2 text-xs text-teal">
              <Loader2 size={13} className="animate-spin flex-shrink-0" />
              <span className="font-medium">
                {isAnalysing && generatingBidDecision
                  ? 'Running analysis and generating bid decision…'
                  : isAnalysing
                    ? 'Running analysis — extracting requirements and matching evidence…'
                    : 'Generating bid decision…'}
              </span>
              <Sparkles size={11} className="flex-shrink-0 ml-auto opacity-60" />
              <span className="opacity-70 text-[11px]">You can switch tabs — this keeps running.</span>
            </div>
          </div>
        )}

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
        {activeTab === 'compliance' && (
          <ComplianceMatrixTab
            requirements={requirements}
            libraryDocs={libraryDocs}
            evidenceLinks={evidenceLinks}
            onReviewLink={async (linkId, status) => {
              await reviewEvidenceLink(linkId, status);
              queryClient.invalidateQueries({ queryKey: ['requirements', id] });
              refetchEvidence();
            }}
          />
        )}
        {activeTab === 'bid' && (
          <BidDecisionTab
            report={bidReport}
            workspace={workspace}
            onWorkspaceChange={handleWorkspaceChange}
            onGenerate={handleGenerateBidDecision}
            generating={generatingBidDecision}
          />
        )}
        {activeTab === 'chat' && (
          <ChatTab
            workspace={workspace}
            messages={chatMessages}
            onMessages={setChatMessages}
          />
        )}
      </div>
    </div>
  );
}
