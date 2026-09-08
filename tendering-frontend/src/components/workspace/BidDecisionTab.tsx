import { useState } from 'react';
import { Loader2, Sparkles, ThumbsUp, ThumbsDown, Download } from 'lucide-react';
import toast from 'react-hot-toast';
import { updateWorkspace } from '../../api/tenders';
import { BidDecisionBadge } from '../Badge';
import { formatDate, formatCurrency } from '../../lib/utils';
import type { BidDecisionReport, TenderWorkspace } from '../../types';

export function BidDecisionTab({
  report,
  workspace,
  onWorkspaceChange,
}: {
  report: BidDecisionReport | null;
  workspace: TenderWorkspace;
  onWorkspaceChange?: (patch: Partial<TenderWorkspace>) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState<'bid' | 'no_bid' | null>(null);
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    if (!report) return;
    setExporting(true);
    await new Promise((resolve) => setTimeout(resolve, 800));

    const lines = [
      `BID DECISION REPORT`,
      `===================`,
      ``,
      `Tender:       ${workspace.title}`,
      `Reference:    ${workspace.reference}`,
      `Buyer:        ${workspace.buyer}`,
      `Value:        ${formatCurrency(workspace.contract_value, workspace.currency)}`,
      `Closing:      ${workspace.closing_date}`,
      `Generated:    ${formatDate(report.generated_at ?? report.analysed_at ?? '', { day: 'numeric', month: 'long', year: 'numeric' })}`,
      ``,
      `AI SCORE: ${report.score}/100`,
      `RECOMMENDATION: ${report.recommendation.toUpperCase()}`,
      ``,
      `RATIONALE`,
      `---------`,
      report.rationale,
      ``,
      `STRENGTHS`,
      `---------`,
      ...report.strengths.map((strength) => `  ✓ ${strength}`),
      ``,
      `RISKS`,
      `-----`,
      ...report.risks.map((risk) => `  ! ${risk}`),
      ``,
      `TEAM DECISION: ${(confirmed ?? workspace.bid_decision).toUpperCase()}`,
    ];

    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bid-report-${workspace.reference || workspace.id}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    setExporting(false);
    toast.success('Report downloaded');
  }

  async function handleConfirm(decision: 'bid' | 'no_bid') {
    setConfirming(true);
    try {
      const patch: Parameters<typeof updateWorkspace>[1] = { bid_decision: decision };
      if (['new', 'analysing', 'preparing'].includes(workspace.stage)) {
        patch.stage = decision === 'bid' ? 'submitted' : 'no_bid';
      }
      await updateWorkspace(workspace.id, patch);
      setConfirmed(decision);
      onWorkspaceChange?.(patch);
      toast.success(decision === 'bid' ? 'Bid decision confirmed — stage set to Submitted' : 'No-bid decision recorded');
    } catch {
      toast.error('Failed to save decision');
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="space-y-5">

      {/* Current decision banner */}
      <div className="bg-panel border border-border rounded-xl p-5 flex items-center justify-between">
        <div>
          <p className="text-xs text-text-mute mb-1">Current Decision</p>
          <BidDecisionBadge decision={confirmed ?? workspace.bid_decision} />
        </div>
        {report && (
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-xs text-text-mute mb-1">AI Analysis</p>
              <p className="text-[11px] text-text-mute">
                {formatDate(report.generated_at ?? report.analysed_at ?? '', { day: 'numeric', month: 'short', year: 'numeric' })}
              </p>
            </div>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center gap-1.5 px-4 py-2 bg-panel-2 border border-border text-text-mid hover:text-text hover:bg-panel-3 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
              Export Report
            </button>
          </div>
        )}
      </div>

      {!report ? (
        <div className="bg-panel border border-border rounded-xl p-10 text-center">
          <Sparkles size={28} className="text-text-mute mx-auto mb-3" />
          <p className="text-sm font-medium text-text mb-1">No bid analysis generated yet</p>
          <p className="text-xs text-text-mute">Complete the requirements and compliance review first.</p>
        </div>
      ) : (
        <>
          {/* Score + rationale */}
          <div className="bg-panel border border-border rounded-xl p-6">
            <div className="flex items-center gap-6 mb-5">
              {/* Circular score gauge */}
              <div className="relative w-24 h-24 flex-shrink-0">
                <svg viewBox="0 0 36 36" className="w-24 h-24 -rotate-90">
                  <circle cx="18" cy="18" r="15.9155" fill="none" stroke="#DEE1E6" strokeWidth="3" />
                  <circle
                    cx="18" cy="18" r="15.9155" fill="none"
                    stroke={report.score >= 70 ? '#2E7D52' : report.score >= 50 ? '#1558D4' : '#C77A12'}
                    strokeWidth="3"
                    strokeDasharray={`${report.score} ${100 - report.score}`}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={`text-2xl font-bold ${
                    report.score >= 70 ? 'text-green' : report.score >= 50 ? 'text-teal' : 'text-amber'
                  }`}>
                    {report.score}
                  </span>
                  <span className="text-[11px] text-text-mute">/ 100</span>
                </div>
              </div>

              <div>
                <p className="text-xs text-text-mute mb-1">AI Recommendation</p>
                <BidDecisionBadge decision={report.recommendation} />
                <p className="text-sm text-text-mid leading-relaxed mt-3 max-w-lg">{report.rationale}</p>
              </div>
            </div>
          </div>

          {/* Strengths + Risks */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="bg-green-bg border border-green/20 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <ThumbsUp size={15} className="text-green" />
                <span className="text-sm font-semibold text-green">Strengths</span>
              </div>
              <ul className="space-y-2">
                {report.strengths.map((strength, index) => (
                  <li key={index} className="flex items-start gap-2 text-xs text-text-mid">
                    <span className="text-green mt-0.5 flex-shrink-0">✓</span>
                    {strength}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-red-bg border border-red/20 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <ThumbsDown size={15} className="text-red" />
                <span className="text-sm font-semibold text-red">Risks</span>
              </div>
              <ul className="space-y-2">
                {report.risks.map((risk, index) => (
                  <li key={index} className="flex items-start gap-2 text-xs text-text-mid">
                    <span className="text-red mt-0.5 flex-shrink-0">!</span>
                    {risk}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Confirm decision */}
          {!confirmed && (
            <div className="bg-panel border border-border rounded-xl p-5">
              <p className="text-sm font-semibold text-text mb-1">Confirm Decision</p>
              <p className="text-xs text-text-mute mb-4">
                Once confirmed this will be recorded and the workspace stage updated.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleConfirm('bid')}
                  disabled={confirming}
                  className="flex items-center gap-2 px-5 py-2.5 bg-green text-white text-sm font-semibold rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  {confirming ? <Loader2 size={14} className="animate-spin" /> : <ThumbsUp size={14} />}
                  Confirm Bid
                </button>
                <button
                  onClick={() => handleConfirm('no_bid')}
                  disabled={confirming}
                  className="flex items-center gap-2 px-5 py-2.5 bg-panel-3 border border-border text-text text-sm font-medium rounded-lg hover:bg-canvas transition-colors disabled:opacity-50"
                >
                  <ThumbsDown size={14} />
                  No Bid
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
