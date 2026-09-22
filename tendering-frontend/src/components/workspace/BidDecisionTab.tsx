import { useState } from 'react';
import { Loader2, Sparkles, ThumbsUp, ThumbsDown, Download } from 'lucide-react';
import toast from 'react-hot-toast';
import { updateWorkspace, generateBidDecision } from '../../api/tenders';
import { BidDecisionBadge } from '../Badge';
import { formatDate, formatCurrency } from '../../lib/utils';
import type { BidDecisionReport, TenderWorkspace } from '../../types';

export function BidDecisionTab({
  report,
  workspace,
  onWorkspaceChange,
  onReportGenerated,
}: {
  report: BidDecisionReport | null;
  workspace: TenderWorkspace;
  onWorkspaceChange?: (patch: Partial<TenderWorkspace>) => void;
  onReportGenerated?: (report: BidDecisionReport) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState<'bid' | 'no_bid' | null>(null);
  const [exporting, setExporting] = useState(false);
  const [generating, setGenerating] = useState(false);

  async function handleExport() {
    if (!report) return;
    setExporting(true);

    const teamDecision = confirmed ?? workspace.bid_decision;
    const decisionLabel = teamDecision === 'bid' ? 'BID' : teamDecision === 'no_bid' ? 'NO BID' : 'PENDING';
    const decisionColour = teamDecision === 'bid' ? '#2E7D52' : teamDecision === 'no_bid' ? '#B91C1C' : '#92400E';
    const scoreColour = report.score >= 70 ? '#2E7D52' : report.score >= 50 ? '#0F766E' : '#C77A12';
    const recLabel = report.recommendation === 'bid' ? 'BID' : report.recommendation === 'no_bid' ? 'NO BID' : report.recommendation.toUpperCase();
    const generatedDate = formatDate(report.generated_at ?? report.analysed_at ?? '', { day: 'numeric', month: 'long', year: 'numeric' });

    const strengthsHtml = report.strengths.map((s) =>
      `<li><span style="color:#2E7D52;font-weight:700;margin-right:6px">✓</span>${s}</li>`
    ).join('');
    const risksHtml = report.risks.map((r) =>
      `<li><span style="color:#B91C1C;font-weight:700;margin-right:6px">!</span>${r}</li>`
    ).join('');

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Bid Decision Report — ${workspace.title}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',Arial,sans-serif;color:#111;background:#fff;padding:40px 48px;max-width:820px;margin:0 auto}
  @media print{body{padding:20px 28px}@page{margin:18mm 18mm}}
  .header{border-bottom:3px solid #0F766E;padding-bottom:16px;margin-bottom:24px}
  .logo{font-size:11px;font-weight:700;letter-spacing:.12em;color:#0F766E;text-transform:uppercase;margin-bottom:8px}
  h1{font-size:20px;font-weight:700;line-height:1.3;color:#0B1525;margin-bottom:4px}
  .meta{display:grid;grid-template-columns:1fr 1fr;gap:6px 32px;margin-top:14px}
  .meta-row{display:flex;gap:8px;font-size:12px}
  .meta-label{color:#6B7280;min-width:80px;font-weight:600}
  .score-row{display:flex;align-items:center;gap:24px;margin:24px 0;padding:20px;background:#F8FAFC;border-radius:12px;border:1px solid #E5E7EB}
  .score-circle{width:80px;height:80px;border-radius:50%;border:5px solid ${scoreColour};display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0}
  .score-num{font-size:26px;font-weight:800;color:${scoreColour};line-height:1}
  .score-denom{font-size:11px;color:#9CA3AF}
  .rec-badge{display:inline-block;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:700;background:${report.recommendation === 'bid' ? '#DCFCE7' : report.recommendation === 'no_bid' ? '#FEE2E2' : '#FEF3C7'};color:${report.recommendation === 'bid' ? '#166534' : report.recommendation === 'no_bid' ? '#991B1B' : '#92400E'}}
  .rationale{font-size:13px;color:#374151;line-height:1.7;margin-top:10px}
  .section-title{font-size:13px;font-weight:700;color:#374151;margin-bottom:10px;padding-bottom:4px;border-bottom:1px solid #E5E7EB}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}
  .card{border-radius:10px;padding:16px}
  .card-green{background:#F0FDF4;border:1px solid #BBF7D0}
  .card-red{background:#FEF2F2;border:1px solid #FECACA}
  .card-title{font-size:12px;font-weight:700;margin-bottom:10px}
  .card-title-green{color:#166534}
  .card-title-red{color:#991B1B}
  ul{list-style:none;padding:0}
  li{font-size:12px;color:#374151;line-height:1.6;padding:2px 0}
  .decision-box{margin-top:24px;padding:18px;border-radius:10px;border:2px solid ${decisionColour};background:${teamDecision === 'bid' ? '#F0FDF4' : teamDecision === 'no_bid' ? '#FEF2F2' : '#FFFBEB'}}
  .decision-label{font-size:11px;color:#6B7280;font-weight:600;margin-bottom:4px}
  .decision-value{font-size:22px;font-weight:800;color:${decisionColour}}
  .footer{margin-top:32px;font-size:10px;color:#9CA3AF;border-top:1px solid #E5E7EB;padding-top:12px;display:flex;justify-content:space-between}
</style>
</head>
<body>
<div class="header">
  <div class="logo">NG Tendering Platform</div>
  <h1>${workspace.title}</h1>
  <div class="meta">
    <div class="meta-row"><span class="meta-label">Reference</span>${workspace.reference || '—'}</div>
    <div class="meta-row"><span class="meta-label">Buyer</span>${workspace.buyer || '—'}</div>
    <div class="meta-row"><span class="meta-label">Value</span>${formatCurrency(workspace.contract_value, workspace.currency)}</div>
    <div class="meta-row"><span class="meta-label">Closing</span>${workspace.closing_date || '—'}</div>
  </div>
</div>

<div class="score-row">
  <div class="score-circle">
    <span class="score-num">${report.score}</span>
    <span class="score-denom">/ 100</span>
  </div>
  <div>
    <div style="font-size:11px;color:#6B7280;font-weight:600;margin-bottom:6px">AI Recommendation</div>
    <span class="rec-badge">${recLabel}</span>
    <p class="rationale">${report.rationale}</p>
  </div>
</div>

<div class="cols">
  <div class="card card-green">
    <div class="section-title card-title card-title-green">✓ Strengths</div>
    <ul>${strengthsHtml}</ul>
  </div>
  <div class="card card-red">
    <div class="section-title card-title card-title-red">! Risks</div>
    <ul>${risksHtml}</ul>
  </div>
</div>

<div class="decision-box">
  <div class="decision-label">Team Decision</div>
  <div class="decision-value">${decisionLabel}</div>
</div>

<div class="footer">
  <span>Generated ${generatedDate}</span>
  <span>Confidential — NG Tendering Platform</span>
</div>

<script>window.onload = function(){ window.print(); }<\/script>
</body>
</html>`;

    const popup = window.open('', '_blank', 'width=900,height=700');
    if (popup) {
      popup.document.write(html);
      popup.document.close();
    }

    setExporting(false);
    toast.success('Print dialog opened — save as PDF');
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      const generated = await generateBidDecision(workspace.id);
      onReportGenerated?.(generated);
      toast.success('Bid decision report generated');
    } catch {
      toast.error('Failed to generate bid decision — ensure analysis has completed');
    } finally {
      setGenerating(false);
    }
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
          <p className="text-xs text-text-mute mb-5">Run analysis and review requirements first, then generate the AI bid decision report.</p>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal text-white text-sm font-semibold rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {generating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {generating ? 'Generating…' : 'Generate Bid Decision'}
          </button>
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
                    <span className="break-words min-w-0">{strength}</span>
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
                    <span className="break-words min-w-0">{risk}</span>
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
