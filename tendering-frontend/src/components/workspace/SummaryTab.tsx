import { FileText, Users, Upload, Download } from 'lucide-react';
import { StageBadge } from '../Badge';
import { daysUntil, formatCurrency, formatDate, readinessColour } from '../../lib/utils';
import type { TenderWorkspace } from '../../types';

export function SummaryTab({ workspace }: { workspace: TenderWorkspace }) {
  const days = daysUntil(workspace.closing_date);
  const isActive = ['new', 'analysing', 'preparing'].includes(workspace.stage);
  const { bar, text } = readinessColour(workspace.readiness_score);

  const details = [
    { label: 'Reference', value: workspace.reference || '—' },
    { label: 'Issuing Body', value: workspace.buyer },
    { label: 'Category', value: workspace.category || '—' },
    { label: 'Contract Value', value: formatCurrency(workspace.contract_value, workspace.currency) },
    { label: 'Closing Date', value: formatDate(workspace.closing_date, { day: 'numeric', month: 'long', year: 'numeric' }) },
    { label: 'Time Remaining', value: days < 0 ? 'Closed' : `${days} days`, urgent: isActive && days <= 14 },
  ];

  const memberColours = ['bg-teal/20 text-teal', 'bg-amber-bg text-amber', 'bg-green-bg text-green', 'bg-red-bg text-red'];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

      {/* Left — details + documents */}
      <div className="lg:col-span-2 space-y-5">

        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text mb-4">Tender Details</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {details.map(({ label, value, urgent }) => (
              <div key={label}>
                <p className="text-xs text-text-mute mb-0.5">{label}</p>
                <p className={`text-sm font-semibold ${urgent ? 'text-amber' : 'text-text'}`}>{value}</p>
              </div>
            ))}
          </div>
          {workspace.description && (
            <div className="mt-4 pt-4 border-t border-border">
              <p className="text-xs text-text-mute mb-1">Description</p>
              <p className="text-sm text-text-mid leading-relaxed">{workspace.description}</p>
            </div>
          )}
        </div>

        <div className="bg-panel border border-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-text">Tender Documents</h3>
            <button className="flex items-center gap-1.5 text-xs text-teal hover:text-teal-soft font-medium transition-colors">
              <Upload size={12} /> Upload
            </button>
          </div>
          {workspace.documents.length === 0 ? (
            <div className="border-2 border-dashed border-border rounded-lg p-6 text-center">
              <Upload size={20} className="text-text-mute mx-auto mb-2" />
              <p className="text-sm text-text-mute">Drop tender documents here</p>
              <p className="text-xs text-text-mute mt-0.5">PDF, DOCX, XLSX supported</p>
            </div>
          ) : (
            <div className="space-y-2">
              {workspace.documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between py-2.5 px-3 bg-panel-2 rounded-lg border border-border">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-7 h-7 rounded-md bg-teal/10 flex items-center justify-center flex-shrink-0">
                      <FileText size={13} className="text-teal" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-text truncate">{doc.name}</p>
                      <p className="text-[11px] text-text-mute">
                        {(doc.size_bytes / 1_000_000).toFixed(1)} MB · {formatDate(doc.uploaded_at, { day: 'numeric', month: 'short' })}
                      </p>
                    </div>
                  </div>
                  <a href={doc.url} className="text-text-mute hover:text-teal transition-colors ml-3 flex-shrink-0">
                    <Download size={14} />
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right — readiness + team + stage */}
      <div className="space-y-5">

        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text mb-4">Readiness Score</h3>
          <div className="flex items-end gap-3 mb-4">
            <span className={`text-5xl font-bold leading-none ${text}`}>{workspace.readiness_score}</span>
            <span className="text-xl text-text-mute mb-1">/ 100</span>
          </div>
          <div className="w-full h-3 bg-canvas-deep rounded-full overflow-hidden mb-4">
            <div className={`h-full rounded-full ${bar}`} style={{ width: `${workspace.readiness_score}%` }} />
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-green-bg rounded-lg py-2">
              <p className="text-lg font-bold text-green">{workspace.requirements_met}</p>
              <p className="text-[11px] text-text-mute">Met</p>
            </div>
            <div className="bg-amber-bg rounded-lg py-2">
              <p className="text-lg font-bold text-amber">{workspace.requirements_partial}</p>
              <p className="text-[11px] text-text-mute">Partial</p>
            </div>
            <div className="bg-red-bg rounded-lg py-2">
              <p className="text-lg font-bold text-red">{workspace.requirements_gap}</p>
              <p className="text-[11px] text-text-mute">Gap</p>
            </div>
          </div>
        </div>

        <div className="bg-panel border border-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users size={15} className="text-teal" />
              <h3 className="text-sm font-semibold text-text">Team</h3>
            </div>
            <button className="text-xs text-teal hover:text-teal-soft font-medium">Add</button>
          </div>
          <div className="space-y-2">
            {workspace.team_members.map((member, i) => {
              const initials = member.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
              return (
                <div key={member} className="flex items-center gap-3">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${memberColours[i % memberColours.length]}`}>
                    {initials}
                  </div>
                  <span className="text-sm text-text-mid">{member}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text mb-3">Stage</h3>
          <StageBadge stage={workspace.stage} />
          <p className="text-xs text-text-mute mt-2 leading-relaxed">
            {workspace.stage === 'new' && 'Upload tender documents to begin AI analysis.'}
            {workspace.stage === 'analysing' && 'AI is extracting and categorising requirements.'}
            {workspace.stage === 'preparing' && 'Requirements mapped. Preparing bid response.'}
            {workspace.stage === 'submitted' && 'Bid submitted. Awaiting evaluation.'}
            {workspace.stage === 'awarded' && 'Bid was awarded.'}
            {workspace.stage === 'lost' && 'Bid was not awarded in this round.'}
            {workspace.stage === 'no_bid' && 'Decision taken not to bid on this tender.'}
          </p>
        </div>
      </div>
    </div>
  );
}
