import { useState } from 'react';
import { ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { RequirementStatusBadge, RequirementCategoryBadge } from '../Badge';
import type { Requirement, RequirementStatus, RequirementCategory } from '../../types';

export function RequirementsTab({ requirements }: { requirements: Requirement[] }) {
  const [statusFilter, setStatusFilter] = useState<RequirementStatus | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<RequirementCategory | 'all'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = requirements.filter((r) => {
    const matchStatus = statusFilter === 'all' || r.status === statusFilter;
    const matchCat = categoryFilter === 'all' || r.category === categoryFilter;
    return matchStatus && matchCat;
  });

  const uniqueCategories = [...new Set(requirements.map((r) => r.category))];

  if (requirements.length === 0) {
    return (
      <div className="bg-panel border border-border rounded-xl p-10 text-center">
        <Sparkles size={28} className="text-text-mute mx-auto mb-3" />
        <p className="text-sm font-medium text-text mb-1">No requirements extracted yet</p>
        <p className="text-xs text-text-mute">Upload tender documents and the AI will extract all requirements automatically.</p>
      </div>
    );
  }

  const counts = {
    met: requirements.filter((r) => r.status === 'met').length,
    partial: requirements.filter((r) => r.status === 'partial').length,
    gap: requirements.filter((r) => r.status === 'gap').length,
    unchecked: requirements.filter((r) => r.status === 'unchecked').length,
  };

  return (
    <div>
      {/* Summary strip — clickable filter cards */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        {(
          [
            { status: 'met' as RequirementStatus, colour: 'bg-green-bg text-green border-green/20' },
            { status: 'partial' as RequirementStatus, colour: 'bg-amber-bg text-amber border-amber/20' },
            { status: 'gap' as RequirementStatus, colour: 'bg-red-bg text-red border-red/20' },
            { status: 'unchecked' as RequirementStatus, colour: 'bg-panel-3 text-text-mute border-border' },
          ] as const
        ).map(({ status, colour }) => (
          <button
            key={status}
            onClick={() => setStatusFilter(statusFilter === status ? 'all' : status)}
            className={`border rounded-xl p-3 text-center transition-all hover:opacity-80 ${colour} ${
              statusFilter === status ? 'ring-2 ring-offset-1 ring-current/30' : ''
            }`}
          >
            <p className="text-2xl font-bold leading-none">{counts[status]}</p>
            <p className="text-xs mt-1 capitalize">{status}</p>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-2 mb-5">
        <div className="flex gap-1.5 flex-wrap">
          {(['all', 'met', 'partial', 'gap', 'unchecked'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setStatusFilter(v)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize ${
                statusFilter === v ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {v === 'all' ? 'All Status' : v}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5 flex-wrap">
          <button
            onClick={() => setCategoryFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              categoryFilter === 'all' ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
            }`}
          >
            All Categories
          </button>
          {uniqueCategories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                categoryFilter === cat ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Requirements list */}
      <div className="space-y-2">
        {filtered.map((req, idx) => (
          <div key={req.req_id} className="bg-panel border border-border rounded-xl overflow-hidden">
            <div
              className="flex items-start gap-4 px-4 py-3.5 cursor-pointer hover:bg-panel-2 transition-colors"
              onClick={() => setExpanded(expanded === req.req_id ? null : req.req_id)}
            >
              <span className="text-xs text-text-mute font-mono mt-0.5 w-5 flex-shrink-0">{idx + 1}</span>

              <div className="flex-1 min-w-0">
                <div className="flex items-start gap-2 flex-wrap mb-1.5">
                  <RequirementStatusBadge status={req.status} />
                  <RequirementCategoryBadge category={req.category} />
                  {req.mandatory && (
                    <span className="px-1.5 py-0.5 rounded text-[11px] font-medium bg-red-bg text-red">Mandatory</span>
                  )}
                </div>
                <p className="text-sm text-text leading-snug">{req.description}</p>
              </div>

              <div className="flex items-center gap-3 flex-shrink-0">
                <div className="text-right hidden sm:block">
                  <p className="text-xs text-text-mute">AI confidence</p>
                  <p className="text-xs font-semibold text-text-mid">{req.confidence}%</p>
                </div>
                {expanded === req.req_id ? (
                  <ChevronUp size={14} className="text-text-mute" />
                ) : (
                  <ChevronDown size={14} className="text-text-mute" />
                )}
              </div>
            </div>

            {expanded === req.req_id && (
              <div className="px-4 pb-4 pt-1 bg-panel-2 border-t border-border">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                  <div>
                    <p className="text-[11px] text-text-mute mb-0.5">Source Document</p>
                    <p className="text-xs text-text font-medium">{req.source_doc ?? '—'}</p>
                  </div>
                  <div>
                    <p className="text-[11px] text-text-mute mb-0.5">Page</p>
                    <p className="text-xs text-text font-medium">{req.page ?? '—'}</p>
                  </div>
                  <div>
                    <p className="text-[11px] text-text-mute mb-0.5">Clause</p>
                    <p className="text-xs text-text font-mono">{req.clause ?? '—'}</p>
                  </div>
                  <div>
                    <p className="text-[11px] text-text-mute mb-0.5">Owner</p>
                    <p className="text-xs text-text font-medium">{req.owner ?? '—'}</p>
                  </div>
                </div>
                {req.notes && (
                  <div
                    className={`text-xs px-3 py-2.5 rounded-lg border leading-relaxed ${
                      req.status === 'met' ? 'bg-green-bg border-green/20 text-green' :
                      req.status === 'gap' ? 'bg-red-bg border-red/20 text-red' :
                      req.status === 'partial' ? 'bg-amber-bg border-amber/30 text-amber' :
                      'bg-panel-3 border-border text-text-mute'
                    }`}
                  >
                    {req.notes}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
