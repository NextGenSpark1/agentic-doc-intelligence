import { useState } from 'react';
import { ChevronDown, ChevronUp, Sparkles, Pencil, Check, X } from 'lucide-react';
import { RequirementStatusBadge, RequirementCategoryBadge } from '../Badge';
import { updateRequirement } from '../../api/tenders';
import toast from 'react-hot-toast';
import type { Requirement, RequirementStatus, RequirementCategory } from '../../types';

const STATUS_OPTIONS: RequirementStatus[] = ['met', 'partial', 'gap', 'unchecked'];

interface EditState {
  status: RequirementStatus;
  owner: string;
  notes: string;
}

export function RequirementsTab({ requirements: initialRequirements }: { requirements: Requirement[] }) {
  const [requirements, setRequirements] = useState(initialRequirements);
  const [statusFilter, setStatusFilter] = useState<RequirementStatus | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<RequirementCategory | 'all'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editState, setEditState] = useState<EditState>({ status: 'unchecked', owner: '', notes: '' });
  const [saving, setSaving] = useState(false);

  const filtered = requirements.filter((requirement) => {
    const matchStatus = statusFilter === 'all' || requirement.status === statusFilter;
    const matchCat = categoryFilter === 'all' || requirement.category === categoryFilter;
    return matchStatus && matchCat;
  });

  const uniqueCategories = [...new Set(requirements.map((requirement) => requirement.category))];

  function startEdit(req: Requirement, e: React.MouseEvent) {
    e.stopPropagation();
    setExpanded(req.req_id);
    setEditing(req.req_id);
    setEditState({ status: req.status, owner: req.owner ?? '', notes: req.notes ?? '' });
  }

  function cancelEdit(e: React.MouseEvent) {
    e.stopPropagation();
    setEditing(null);
  }

  async function saveEdit(req: Requirement, e: React.MouseEvent) {
    e.stopPropagation();
    setSaving(true);
    try {
      await updateRequirement(req.req_id, {
        status: editState.status,
        owner: editState.owner,
        notes: editState.notes,
      });
      setRequirements((previous) =>
        previous.map((requirement) =>
          requirement.req_id === req.req_id
            ? { ...requirement, status: editState.status, owner: editState.owner, notes: editState.notes }
            : requirement,
        ),
      );
      setEditing(null);
      toast.success('Requirement updated');
    } catch {
      toast.error('Failed to update requirement');
    } finally {
      setSaving(false);
    }
  }

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
    met: requirements.filter((requirement) => requirement.status === 'met').length,
    partial: requirements.filter((requirement) => requirement.status === 'partial').length,
    gap: requirements.filter((requirement) => requirement.status === 'gap').length,
    unchecked: requirements.filter((requirement) => requirement.status === 'unchecked').length,
  };

  const statusColour = (s: RequirementStatus) =>
    s === 'met' ? 'bg-green-bg text-green border-green/20' :
    s === 'partial' ? 'bg-amber-bg text-amber border-amber/20' :
    s === 'gap' ? 'bg-red-bg text-red border-red/20' :
    'bg-panel-3 text-text-mute border-border';

  const notesColour = (s: RequirementStatus) =>
    s === 'met' ? 'bg-green-bg border-green/20 text-green' :
    s === 'gap' ? 'bg-red-bg border-red/20 text-red' :
    s === 'partial' ? 'bg-amber-bg border-amber/30 text-amber' :
    'bg-panel-3 border-border text-text-mute';

  return (
    <div>
      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        {((['met', 'partial', 'gap', 'unchecked'] as const)).map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(statusFilter === status ? 'all' : status)}
            className={`border rounded-xl p-3 text-center transition-all hover:opacity-80 ${statusColour(status)} ${
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
          {(['all', 'met', 'partial', 'gap', 'unchecked'] as const).map((statusValue) => (
            <button
              key={statusValue}
              onClick={() => setStatusFilter(statusValue)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize ${
                statusFilter === statusValue ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {statusValue === 'all' ? 'All Status' : statusValue}
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
          {uniqueCategories.map((category) => (
            <button
              key={category}
              onClick={() => setCategoryFilter(category)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                categoryFilter === category ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {category}
            </button>
          ))}
        </div>
      </div>

      {/* Requirements list */}
      <div className="space-y-2">
        {filtered.map((req, index) => {
          const isExpanded = expanded === req.req_id;
          const isEditing = editing === req.req_id;

          return (
            <div key={req.req_id} className="bg-panel border border-border rounded-xl overflow-hidden">
              {/* Row header */}
              <div
                className="flex items-start gap-4 px-4 py-3.5 cursor-pointer hover:bg-panel-2 transition-colors"
                onClick={() => !isEditing && setExpanded(isExpanded ? null : req.req_id)}
              >
                <span className="text-xs text-text-mute font-mono mt-0.5 w-5 flex-shrink-0">{index + 1}</span>

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
                  {!isEditing && (
                    <button
                      onClick={(e) => startEdit(req, e)}
                      className="p-1.5 rounded-lg hover:bg-panel-3 text-text-mute hover:text-teal transition-colors"
                      title="Edit"
                    >
                      <Pencil size={13} />
                    </button>
                  )}
                  {isExpanded ? (
                    <ChevronUp size={14} className="text-text-mute" />
                  ) : (
                    <ChevronDown size={14} className="text-text-mute" />
                  )}
                </div>
              </div>

              {/* Expanded panel */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-3 bg-panel-2 border-t border-border">
                  {isEditing ? (
                    <div className="space-y-3">
                      {/* Status */}
                      <div>
                        <label className="block text-[11px] font-semibold text-text-mute uppercase tracking-wide mb-1.5">Status</label>
                        <div className="flex gap-2 flex-wrap">
                          {STATUS_OPTIONS.map((statusOption) => (
                            <button
                              key={statusOption}
                              onClick={(clickEvent) => { clickEvent.stopPropagation(); setEditState((previous) => ({ ...previous, status: statusOption })); }}
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition-colors ${
                                editState.status === statusOption
                                  ? statusColour(statusOption) + ' ring-2 ring-current/30'
                                  : 'bg-canvas border-border text-text-mute hover:bg-panel'
                              }`}
                            >
                              {statusOption}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Owner */}
                      <div>
                        <label className="block text-[11px] font-semibold text-text-mute uppercase tracking-wide mb-1.5">Owner</label>
                        <input
                          value={editState.owner}
                          onClick={(clickEvent) => clickEvent.stopPropagation()}
                          onChange={(inputEvent) => setEditState((previous) => ({ ...previous, owner: inputEvent.target.value }))}
                          placeholder="e.g. Legal Team"
                          className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
                        />
                      </div>

                      {/* Notes */}
                      <div>
                        <label className="block text-[11px] font-semibold text-text-mute uppercase tracking-wide mb-1.5">Notes</label>
                        <textarea
                          value={editState.notes}
                          onClick={(clickEvent) => clickEvent.stopPropagation()}
                          onChange={(inputEvent) => setEditState((previous) => ({ ...previous, notes: inputEvent.target.value }))}
                          placeholder="How is this requirement being addressed?"
                          rows={3}
                          className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors resize-none"
                        />
                      </div>

                      {/* Actions */}
                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button
                          onClick={cancelEdit}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-mid hover:text-text transition-colors"
                        >
                          <X size={12} /> Cancel
                        </button>
                        <button
                          onClick={(e) => saveEdit(req, e)}
                          disabled={saving}
                          className="flex items-center gap-1.5 px-4 py-1.5 bg-navy hover:bg-navy-soft disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-colors"
                        >
                          <Check size={12} />
                          {saving ? 'Saving…' : 'Save'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
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
                        <div className={`text-xs px-3 py-2.5 rounded-lg border leading-relaxed ${notesColour(req.status)}`}>
                          {req.notes}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
