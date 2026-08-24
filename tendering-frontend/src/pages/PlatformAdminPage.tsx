import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Copy, Check, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { getAllOrgs, createOrg, updateOrg, deleteOrg } from '../api/orgs';
import type { Organisation } from '../types';
import { useAuth } from '../context/AuthContext';
import { PLATFORM_ADMIN_EMAILS } from '../context/AuthContext';

const PLAN_BADGE: Record<string, string> = {
  trial: 'text-amber-700 bg-amber-50 border-amber-200',
  pro: 'text-teal bg-teal/10 border-teal/30',
  enterprise: 'text-purple-600 bg-purple-50 border-purple-200',
};

export function PlatformAdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState<Organisation[]>([]);
  const [loading, setLoading] = useState(true);

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', plan: 'trial', adminEmail: '', adminName: '' });
  const [creating, setCreating] = useState(false);
  const [lastInviteLink, setLastInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [expandedOrg, setExpandedOrg] = useState<string | null>(null);
  const [editingPlan, setEditingPlan] = useState<Record<string, string>>({});
  const [savingPlan, setSavingPlan] = useState<string | null>(null);
  const [togglingStatus, setTogglingStatus] = useState<string | null>(null);
  const [deletingOrg, setDeletingOrg] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !PLATFORM_ADMIN_EMAILS.includes(user.email ?? '')) {
      navigate('/');
      return;
    }
    getAllOrgs().then(setOrgs).finally(() => setLoading(false));
  }, [user, navigate]);

  async function handleCreate() {
    if (!form.name || !form.adminEmail) return;
    setCreating(true);
    try {
      const result = await createOrg(form.name, form.plan, form.adminEmail, form.adminName || undefined);
      setOrgs(previous => [{ ...result, member_count: 0, workspace_count: 0 }, ...previous]);
      if (result.invite_link) setLastInviteLink(result.invite_link);
      setShowCreate(false);
      setForm({ name: '', plan: 'trial', adminEmail: '', adminName: '' });
    } catch {
      alert('Failed to create organisation');
    } finally {
      setCreating(false);
    }
  }

  async function handlePlanSave(organisation: Organisation) {
    const newPlan = editingPlan[organisation.org_id];
    if (!newPlan || newPlan === organisation.plan) return;
    setSavingPlan(organisation.org_id);
    try {
      const updated = await updateOrg(organisation.org_id, { plan: newPlan });
      setOrgs(previous => previous.map(existingOrg =>
        existingOrg.org_id === organisation.org_id ? { ...existingOrg, plan: updated.plan ?? newPlan } : existingOrg
      ));
      setEditingPlan(previous => { const next = { ...previous }; delete next[organisation.org_id]; return next; });
    } catch {
      alert('Failed to update plan');
    } finally {
      setSavingPlan(null);
    }
  }

  async function handleToggleStatus(organisation: Organisation) {
    const newStatus = (organisation.status ?? 'active') === 'active' ? 'suspended' : 'active';
    const label = newStatus === 'suspended' ? 'Suspend' : 'Reactivate';
    if (!window.confirm(`${label} "${organisation.name}"?`)) return;
    setTogglingStatus(organisation.org_id);
    try {
      const updated = await updateOrg(organisation.org_id, { status: newStatus });
      setOrgs(previous => previous.map(existingOrg =>
        existingOrg.org_id === organisation.org_id ? { ...existingOrg, status: updated.status ?? newStatus } : existingOrg
      ));
    } catch {
      alert('Failed to update status');
    } finally {
      setTogglingStatus(null);
    }
  }

  async function handleDelete(organisation: Organisation) {
    if (!window.confirm(`Permanently delete "${organisation.name}"? This cannot be undone.`)) return;
    setDeletingOrg(organisation.org_id);
    try {
      await deleteOrg(organisation.org_id);
      setOrgs(previous => previous.filter(existingOrg => existingOrg.org_id !== organisation.org_id));
    } catch {
      alert('Failed to delete organisation');
    } finally {
      setDeletingOrg(null);
    }
  }

  const ROLE_COLORS: Record<string, string> = {
    org_admin: 'text-teal bg-teal/10 border-teal/30',
    supervisor: 'text-indigo-600 bg-indigo-50 border-indigo-200',
    member: 'text-text-mid bg-panel-2 border-border',
  };
  const ROLE_LABELS: Record<string, string> = {
    org_admin: 'Org Admin', supervisor: 'Supervisor', member: 'Member',
  };

  return (
    <div className="min-h-screen bg-canvas">
      {/* Header */}
      <div className="bg-navy-deep h-13 flex items-center px-6 justify-between">
        <div className="flex items-center gap-3">
          <img src="/NG logo.jpeg" alt="NextGen Spark" className="w-7 h-7 rounded-md object-contain bg-white p-0.5 shrink-0" />
          <span className="text-white font-semibold text-sm tracking-wide">NextGen Spark</span>
          <span className="text-white/30 text-sm">·</span>
          <span className="text-white/60 text-xs font-semibold uppercase tracking-widest">Platform Admin</span>
        </div>
        <button
          onClick={() => navigate('/')}
          className="text-white/60 hover:text-white text-xs transition-colors"
        >
          ← Back to app
        </button>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-7">
          <div>
            <h1 className="text-xl font-bold text-text">Organisations</h1>
            <p className="text-sm text-text-mute mt-0.5">
              {orgs.length} organisation{orgs.length !== 1 ? 's' : ''} on the platform
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 bg-navy hover:bg-navy-soft text-white text-sm font-semibold px-4 py-2.5 rounded-lg transition-colors"
          >
            <Plus size={15} /> New Organisation
          </button>
        </div>

        {lastInviteLink && (
          <div className="bg-teal/5 border border-teal/20 rounded-xl px-5 py-4 mb-6 flex items-start gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-teal mb-1 uppercase tracking-wide">Org admin invite link</p>
              <p className="text-xs text-text-mute font-mono break-all">{lastInviteLink}</p>
            </div>
            <button
              onClick={() => { navigator.clipboard.writeText(lastInviteLink); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
              className="flex items-center gap-1.5 text-xs font-semibold text-teal border border-teal/30 rounded-lg px-3 py-1.5 hover:bg-teal/10 transition-colors shrink-0"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16 gap-3 text-text-mute">
            <Loader2 size={16} className="animate-spin" />
            <span className="text-sm">Loading organisations…</span>
          </div>
        ) : orgs.length === 0 ? (
          <div className="text-center py-16 text-text-mute text-sm">No organisations yet.</div>
        ) : (
          <div className="flex flex-col gap-3">
            {orgs.map(organisation => {
              const suspended = (organisation.status ?? 'active') === 'suspended';
              const isExpanded = expandedOrg === organisation.org_id;
              const pendingPlan = editingPlan[organisation.org_id] ?? organisation.plan;

              return (
                <div
                  key={organisation.org_id}
                  className={`bg-panel rounded-xl border overflow-hidden transition-opacity ${
                    suspended ? 'border-red/20 opacity-80' : 'border-border'
                  }`}
                >
                  <div className="px-5 py-4 flex items-center gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-sm font-semibold text-text">{organisation.name}</p>
                        {suspended && (
                          <span className="text-[10px] font-bold uppercase tracking-wide text-red bg-red-bg border border-red/20 rounded-full px-2 py-0.5">
                            Suspended
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-text-mute font-mono">
                        {organisation.org_id} · Created {new Date(organisation.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </p>
                    </div>

                    <div className="flex gap-6 text-center shrink-0">
                      <div>
                        <p className="text-base font-bold text-text">{organisation.member_count ?? 0}</p>
                        <p className="text-[10px] text-text-mute">members</p>
                      </div>
                      <div>
                        <p className="text-base font-bold text-text">{organisation.workspace_count ?? 0}</p>
                        <p className="text-[10px] text-text-mute">workspaces</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <select
                        value={pendingPlan}
                        onChange={selectEvent => setEditingPlan(previous => ({ ...previous, [organisation.org_id]: selectEvent.target.value }))}
                        className={`text-[10px] font-bold border rounded-full px-2.5 py-0.5 uppercase tracking-wide cursor-pointer focus:outline-none ${PLAN_BADGE[pendingPlan] ?? 'text-text-mute bg-panel-2 border-border'}`}
                      >
                        <option value="trial">Trial</option>
                        <option value="pro">Pro</option>
                        <option value="enterprise">Enterprise</option>
                      </select>
                      {pendingPlan !== organisation.plan && (
                        <button
                          onClick={() => handlePlanSave(organisation)}
                          disabled={savingPlan === organisation.org_id}
                          className="text-[11px] font-semibold text-navy border border-navy/20 rounded-lg px-2.5 py-1 hover:bg-navy/5 transition-colors disabled:opacity-40"
                        >
                          {savingPlan === organisation.org_id ? '…' : 'Save'}
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => setExpandedOrg(isExpanded ? null : organisation.org_id)}
                        className="flex items-center gap-1 text-xs text-text-mute border border-border rounded-lg px-2.5 py-1.5 hover:border-border-strong hover:text-text transition-colors"
                      >
                        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        Members
                      </button>
                      <button
                        onClick={() => handleToggleStatus(organisation)}
                        disabled={togglingStatus === organisation.org_id}
                        className={`text-xs font-medium border rounded-lg px-2.5 py-1.5 transition-colors disabled:opacity-40 ${
                          suspended
                            ? 'text-green-700 border-green-200 hover:bg-green-50'
                            : 'text-amber-700 border-amber-200 hover:bg-amber-50'
                        }`}
                      >
                        {togglingStatus === organisation.org_id ? '…' : suspended ? 'Activate' : 'Suspend'}
                      </button>
                      <button
                        onClick={() => handleDelete(organisation)}
                        disabled={deletingOrg === organisation.org_id}
                        className="text-xs font-medium text-red/70 border border-red/20 rounded-lg px-2.5 py-1.5 hover:text-red hover:border-red/40 transition-colors disabled:opacity-40"
                      >
                        {deletingOrg === organisation.org_id ? '…' : 'Delete'}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-border bg-canvas px-5 py-4">
                      <p className="text-[10px] font-semibold text-text-mute uppercase tracking-widest mb-3">Members</p>
                      {!organisation.members || organisation.members.length === 0 ? (
                        <p className="text-sm text-text-mute">No members loaded. Expand from org member list.</p>
                      ) : (
                        <div className="flex flex-col gap-2">
                          {organisation.members.map(member => (
                            <div key={member.user_id} className="flex items-center gap-3">
                              <div className="w-7 h-7 rounded-full bg-navy/10 flex items-center justify-center text-[10px] font-bold text-navy shrink-0">
                                {(member.full_name || member.email).slice(0, 2).toUpperCase()}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-text truncate">{member.full_name || member.email}</p>
                                {member.full_name && <p className="text-xs text-text-mute">{member.email}</p>}
                              </div>
                              <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 shrink-0 ${ROLE_COLORS[member.role] ?? ''}`}>
                                {ROLE_LABELS[member.role] ?? member.role}
                              </span>
                              <p className="text-[11px] text-text-mute shrink-0">
                                {new Date(member.joined_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showCreate && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-6"
          onClick={() => setShowCreate(false)}
        >
          <div
            className="bg-panel rounded-2xl p-8 w-full max-w-md flex flex-col gap-5 shadow-xl"
            onClick={clickEvent => clickEvent.stopPropagation()}
          >
            <h2 className="text-lg font-bold text-text">New Organisation</h2>
            {[
              { label: 'Organisation name', key: 'name', placeholder: 'e.g. MACC Procurement Unit', type: 'text' },
              { label: 'Admin email', key: 'adminEmail', placeholder: 'admin@client.gov.my', type: 'email' },
              { label: 'Admin name (optional)', key: 'adminName', placeholder: 'e.g. Ahmad bin Hassan', type: 'text' },
            ].map(field => (
              <div key={field.key} className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-text-mute">{field.label}</label>
                <input
                  type={field.type}
                  value={form[field.key as keyof typeof form]}
                  onChange={inputEvent => setForm(previous => ({ ...previous, [field.key]: inputEvent.target.value }))}
                  placeholder={field.placeholder}
                  className="border border-border rounded-lg px-3 py-2.5 text-sm text-text bg-canvas outline-none focus:border-teal focus:ring-2 focus:ring-teal/20 transition-colors"
                />
              </div>
            ))}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-text-mute">Plan</label>
              <select
                value={form.plan}
                onChange={selectEvent => setForm(previous => ({ ...previous, plan: selectEvent.target.value }))}
                className="border border-border rounded-lg px-3 py-2.5 text-sm text-text bg-canvas outline-none focus:border-teal"
              >
                <option value="trial">Trial</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div className="flex gap-3 justify-end mt-1">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 border border-border rounded-lg text-sm text-text-mid hover:border-border-strong transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !form.name || !form.adminEmail}
                className="flex items-center gap-2 px-5 py-2 bg-navy hover:bg-navy-soft text-white font-semibold text-sm rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creating && <Loader2 size={14} className="animate-spin" />}
                {creating ? 'Creating…' : 'Create & send invite'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
