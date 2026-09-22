import { useState, type ReactElement } from 'react';
import { CheckCircle2, XCircle, AlertCircle, Circle, BarChart3, Check, X } from 'lucide-react';
import { RequirementCategoryBadge } from '../Badge';
import type { Requirement, RequirementStatus, LibraryDocument, EvidenceLink } from '../../types';

const STATUS_CONFIG: Record<RequirementStatus, { icon: ReactElement; label: string; bar: string }> = {
  met: {
    icon: <CheckCircle2 size={14} className="text-green" />,
    label: 'Met',
    bar: 'bg-green',
  },
  partial: {
    icon: <AlertCircle size={14} className="text-amber" />,
    label: 'Partial',
    bar: 'bg-amber',
  },
  gap: {
    icon: <XCircle size={14} className="text-red" />,
    label: 'Gap',
    bar: 'bg-red',
  },
  unchecked: {
    icon: <Circle size={14} className="text-text-mute" />,
    label: 'Unchecked',
    bar: 'bg-border',
  },
};

const SUMMARY_CARDS: {
  key: RequirementStatus;
  label: string;
  colour: string;
  icon: ReactElement;
  countKey: 'met' | 'partial' | 'gap' | 'unchecked';
}[] = [
  {
    key: 'met',
    label: 'Met',
    colour: 'bg-green-bg border-green/20 text-green',
    icon: <CheckCircle2 size={17} />,
    countKey: 'met',
  },
  {
    key: 'partial',
    label: 'Partial',
    colour: 'bg-amber-bg border-amber/30 text-amber',
    icon: <AlertCircle size={17} />,
    countKey: 'partial',
  },
  {
    key: 'gap',
    label: 'Critical Gaps',
    colour: 'bg-red-bg border-red/20 text-red',
    icon: <XCircle size={17} />,
    countKey: 'gap',
  },
  {
    key: 'unchecked',
    label: 'Unchecked',
    colour: 'bg-panel-3 border-border text-text-mute',
    icon: <Circle size={17} />,
    countKey: 'unchecked',
  },
];

export function ComplianceMatrixTab({
  requirements,
  libraryDocs = [],
  evidenceLinks = [],
  onReviewLink,
}: {
  requirements: Requirement[];
  libraryDocs?: LibraryDocument[];
  evidenceLinks?: EvidenceLink[];
  onReviewLink?: (linkId: string, status: 'confirmed' | 'dismissed') => Promise<void>;
}) {
  const libraryDocMap = Object.fromEntries(libraryDocs.map((doc) => [doc.doc_id, doc.title]));
  const [statusFilter, setStatusFilter] = useState<RequirementStatus | 'all'>('all');
  const [reviewing, setReviewing] = useState<string | null>(null);

  // Group evidence links by req_id
  const evidenceByReq: Record<string, EvidenceLink[]> = {};
  for (const link of evidenceLinks) {
    if (!evidenceByReq[link.req_id]) evidenceByReq[link.req_id] = [];
    evidenceByReq[link.req_id].push(link);
  }

  const counts = {
    met: requirements.filter((requirement) => requirement.status === 'met').length,
    partial: requirements.filter((requirement) => requirement.status === 'partial').length,
    gap: requirements.filter((requirement) => requirement.status === 'gap' && requirement.mandatory).length,
    unchecked: requirements.filter((requirement) => requirement.status === 'unchecked').length,
  };

  const filtered =
    statusFilter === 'all' ? requirements : requirements.filter((requirement) => requirement.status === statusFilter);

  async function handleReview(linkId: string, status: 'confirmed' | 'dismissed') {
    if (!onReviewLink) return;
    setReviewing(linkId);
    try {
      await onReviewLink(linkId, status);
    } finally {
      setReviewing(null);
    }
  }

  if (requirements.length === 0) {
    return (
      <div className="bg-panel border border-border rounded-xl p-10 text-center">
        <BarChart3 size={28} className="text-text-mute mx-auto mb-3" />
        <p className="text-sm font-medium text-text mb-1">No requirements to analyse</p>
        <p className="text-xs text-text-mute">Extract requirements first from the Requirements tab.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">

      {/* Summary filter cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {SUMMARY_CARDS.map(({ key, label, colour, icon, countKey }) => (
          <button
            key={key}
            onClick={() => setStatusFilter(statusFilter === key ? 'all' : key)}
            className={`border rounded-xl p-4 flex items-center gap-3 transition-all hover:opacity-80 ${colour} ${
              statusFilter === key ? 'ring-2 ring-offset-1 ring-current/30' : ''
            }`}
          >
            {icon}
            <div className="text-left min-w-0">
              <p className="text-2xl font-bold leading-none">{counts[countKey]}</p>
              <p className="text-[11px] mt-0.5 opacity-80 leading-tight">{label}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Filter pills */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setStatusFilter('all')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            statusFilter === 'all'
              ? 'bg-teal text-white'
              : 'bg-panel-3 border border-border text-text-mute hover:text-text'
          }`}
        >
          All ({requirements.length})
        </button>
        {SUMMARY_CARDS.map(({ key, label, countKey }) => (
          <button
            key={key}
            onClick={() => setStatusFilter(statusFilter === key ? 'all' : key)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              statusFilter === key
                ? key === 'met' ? 'bg-green text-white'
                  : key === 'partial' ? 'bg-amber text-white'
                  : key === 'gap' ? 'bg-red text-white'
                  : 'bg-panel-3 border border-border text-text'
                : 'bg-panel-3 border border-border text-text-mute hover:text-text'
            }`}
          >
            {label} ({counts[countKey]})
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-panel border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-panel-2 border-b border-border">
                <th className="text-left text-[11px] font-semibold text-text-mute uppercase tracking-wide py-3 pl-5 pr-3 w-8">#</th>
                <th className="text-left text-[11px] font-semibold text-text-mute uppercase tracking-wide py-3 px-3">Requirement</th>
                <th className="text-left text-[11px] font-semibold text-text-mute uppercase tracking-wide py-3 px-3 w-32">Category</th>
                <th className="text-left text-[11px] font-semibold text-text-mute uppercase tracking-wide py-3 px-3 w-24">Mandatory</th>
                <th className="text-left text-[11px] font-semibold text-text-mute uppercase tracking-wide py-3 px-3 w-28">Status</th>
                <th className="text-left text-[11px] font-semibold text-text-mute uppercase tracking-wide py-3 pl-3 pr-5">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map((req, index) => {
                const { icon, label } = STATUS_CONFIG[req.status];
                const barColour = STATUS_CONFIG[req.status].bar;
                const reqLinks = evidenceByReq[req.req_id] ?? [];
                const confirmedLinks = reqLinks.filter((link) => link.human_review_status === 'confirmed');
                const pendingLinks = reqLinks.filter((link) => link.human_review_status === 'pending');

                return (
                  <tr key={req.req_id} className="group hover:bg-panel-2 transition-colors align-top">
                    {/* Left accent bar */}
                    <td className={`pl-5 pr-3 py-4 border-l-2 ${
                      req.status === 'met' ? 'border-l-green' :
                      req.status === 'partial' ? 'border-l-amber' :
                      req.status === 'gap' ? 'border-l-red' :
                      'border-l-transparent'
                    }`}>
                      <span className="text-xs text-text-mute font-mono">{index + 1}</span>
                    </td>

                    {/* Requirement description */}
                    <td className="px-3 py-4">
                      <p className="text-xs text-text leading-relaxed">{req.description}</p>
                      {req.notes && (
                        <p className="text-[11px] text-text-mute mt-1 leading-relaxed italic">{req.notes}</p>
                      )}
                    </td>

                    {/* Category */}
                    <td className="px-3 py-4">
                      <RequirementCategoryBadge category={req.category} />
                    </td>

                    {/* Mandatory */}
                    <td className="px-3 py-4">
                      {req.mandatory ? (
                        <span className="text-[11px] px-2 py-0.5 bg-red-bg text-red rounded font-medium">Required</span>
                      ) : (
                        <span className="text-[11px] text-text-mute">Optional</span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-3 py-4">
                      <div className="flex items-center gap-1.5">
                        {icon}
                        <span className="text-[11px] text-text-mid font-medium">{label}</span>
                      </div>
                      <div className="mt-1.5 w-16 h-1 bg-canvas-deep rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${barColour} ${
                            req.status === 'met' ? 'w-full' :
                            req.status === 'partial' ? 'w-1/2' : 'w-0'
                          }`}
                        />
                      </div>
                    </td>

                    {/* Evidence column */}
                    <td className="pl-3 pr-5 py-4">
                      <div className="space-y-2">
                        {/* Confirmed links */}
                        {confirmedLinks.map((link) => (
                          <div key={link.id} className="flex items-center gap-1.5">
                            <CheckCircle2 size={11} className="text-green flex-shrink-0" />
                            <span className="text-[11px] text-green font-medium truncate max-w-[160px]">
                              {libraryDocMap[link.doc_id] ?? 'Vault document'}
                            </span>
                            <button
                              onClick={() => handleReview(link.id, 'dismissed')}
                              disabled={reviewing === link.id}
                              className="ml-auto text-[10px] text-text-mute hover:text-red transition-colors flex-shrink-0"
                              title="Dismiss"
                            >
                              <X size={10} />
                            </button>
                          </div>
                        ))}

                        {/* Pending proposals */}
                        {pendingLinks.map((link) => (
                          <div key={link.id} className="bg-amber-bg border border-amber/20 rounded-lg px-2 py-1.5">
                            <p className="text-[11px] font-medium text-amber-700 truncate max-w-[180px] mb-1">
                              {libraryDocMap[link.doc_id] ?? 'Vault document'}
                            </p>
                            {link.rationale && (
                              <p className="text-[10px] text-text-mute leading-snug mb-1.5 line-clamp-2">
                                {link.rationale}
                              </p>
                            )}
                            <div className="flex gap-1.5">
                              <button
                                onClick={() => handleReview(link.id, 'confirmed')}
                                disabled={reviewing === link.id}
                                className="flex items-center gap-1 px-2 py-0.5 bg-green text-white text-[10px] font-semibold rounded disabled:opacity-50 hover:opacity-90 transition-opacity"
                              >
                                <Check size={9} /> Confirm
                              </button>
                              <button
                                onClick={() => handleReview(link.id, 'dismissed')}
                                disabled={reviewing === link.id}
                                className="flex items-center gap-1 px-2 py-0.5 bg-panel-3 border border-border text-text-mute text-[10px] font-medium rounded disabled:opacity-50 hover:bg-panel transition-colors"
                              >
                                <X size={9} /> Dismiss
                              </button>
                            </div>
                          </div>
                        ))}

                        {/* No evidence */}
                        {reqLinks.length === 0 && (
                          <span className="text-[11px] text-text-mute">—</span>
                        )}
                        {reqLinks.length > 0 && confirmedLinks.length === 0 && pendingLinks.length === 0 && (
                          <span className="text-[11px] text-text-mute italic">All proposals dismissed</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Critical gaps callout */}
      {counts.gap > 0 && statusFilter !== 'met' && (
        <div className="bg-red-bg border border-red/20 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <XCircle size={15} className="text-red" />
            <span className="text-sm font-semibold text-red">
              {counts.gap} Critical Gap{counts.gap !== 1 ? 's' : ''} — Action Required
            </span>
          </div>
          <ul className="space-y-1.5">
            {requirements
              .filter((requirement) => requirement.status === 'gap' && requirement.mandatory)
              .map((gapRequirement) => (
                <li key={gapRequirement.req_id} className="text-xs text-red flex items-start gap-2">
                  <span className="mt-0.5 flex-shrink-0">•</span>
                  {gapRequirement.description}
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
