import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Users, Mail, Building2, Shield, User, Clock } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getOrgMembers, inviteMember, removeMember, changeMemberRole, leaveOrg,
  getPendingInvitations, cancelInvitation, resendInvitation,
} from '../api/orgs';
import type { OrgMember, PendingInvitation, OrgRole } from '../types';

const LABEL = 'text-[10px] font-semibold text-text-mute uppercase tracking-wider';
const INPUT = 'w-full border border-border rounded-lg px-3 py-2 text-sm text-text bg-panel placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors';

const ROLE_LABELS: Record<string, string> = {
  org_admin: 'Org Admin', supervisor: 'Supervisor', member: 'Member',
};
const ROLE_COLORS: Record<string, string> = {
  org_admin: 'text-teal bg-teal/10 border-teal/30',
  supervisor: 'text-indigo-600 bg-indigo-50 border-indigo-200',
  member: 'text-text-mid bg-panel-2 border-border',
};
const PLAN_COLORS: Record<string, string> = {
  trial: 'text-amber-600 bg-amber-50 border-amber-200',
  pro: 'text-teal bg-teal/10 border-teal/30',
  enterprise: 'text-purple-600 bg-purple-50 border-purple-200',
};

function Card({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-panel rounded-xl border border-border p-5 flex flex-col gap-4">
      <div className="flex items-center gap-2">
        {icon}
        <p className={LABEL}>{title}</p>
      </div>
      {children}
    </div>
  );
}

export function OrgSettingsPage() {
  const { user, orgCtx } = useAuth();
  const role = orgCtx?.role ?? 'member';
  const isOrgAdmin = role === 'org_admin';
  const canInvite = role === 'org_admin' || role === 'supervisor';

  const [members, setMembers] = useState<OrgMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState<Record<string, string>>({});
  const [savingRole, setSavingRole] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);

  const [pendingInvites, setPendingInvites] = useState<PendingInvitation[]>([]);
  const [cancellingToken, setCancellingToken] = useState<string | null>(null);
  const [resendingToken, setResendingToken] = useState<string | null>(null);
  const [resendResult, setResendResult] = useState<Record<string, boolean>>({});

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviteName, setInviteName] = useState('');
  const [inviting, setInviting] = useState(false);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const pageTitle = isOrgAdmin ? 'Org Settings' : role === 'supervisor' ? 'Team' : 'My Team';
  const pageSubtitle = isOrgAdmin
    ? 'Manage your organisation, team members, and invitations'
    : role === 'supervisor'
    ? 'View your team and invite new members'
    : 'See who else is in your organisation';

  useEffect(() => {
    if (!orgCtx?.org_id) return;
    getOrgMembers(orgCtx.org_id)
      .then(setMembers)
      .catch(() => {})
      .finally(() => setMembersLoading(false));
    if (canInvite) {
      getPendingInvitations(orgCtx.org_id).then(setPendingInvites).catch(() => {});
    }
  }, [orgCtx?.org_id, canInvite]);

  async function handleInvite() {
    if (!inviteEmail || !orgCtx?.org_id) return;
    setInviting(true);
    setInviteError(null);
    setInviteLink(null);
    try {
      const result = await inviteMember(orgCtx.org_id, inviteEmail, inviteRole as OrgRole, inviteName || undefined);
      setInviteLink(result.invite_link);
      setInviteEmail('');
      setInviteName('');
      getPendingInvitations(orgCtx.org_id).then(setPendingInvites).catch(() => {});
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setInviteError(detail ?? 'Failed to send invite');
    } finally {
      setInviting(false);
    }
  }

  async function handleLeaveOrg() {
    if (!orgCtx?.org_id) return;
    if (!window.confirm(`Leave ${orgCtx.org_name}? You will lose access immediately.`)) return;
    setLeaving(true);
    try {
      await leaveOrg(orgCtx.org_id);
      window.location.href = '/';
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(detail ?? 'Failed to leave organisation');
      setLeaving(false);
    }
  }

  async function handleRoleSave(member: OrgMember) {
    const newRole = editingRole[member.user_id];
    if (!newRole || !orgCtx?.org_id) return;
    setSavingRole(member.user_id);
    try {
      await changeMemberRole(orgCtx.org_id, member.user_id, newRole as OrgRole);
      setMembers(previous => previous.map(existingMember =>
        existingMember.user_id === member.user_id
          ? { ...existingMember, role: newRole as OrgRole }
          : existingMember
      ));
      setEditingRole(previous => { const next = { ...previous }; delete next[member.user_id]; return next; });
    } catch { alert('Failed to update role'); }
    finally { setSavingRole(null); }
  }

  async function handleCancelInvite(inviteToken: string) {
    if (!orgCtx?.org_id || !window.confirm('Cancel this invitation?')) return;
    setCancellingToken(inviteToken);
    try {
      await cancelInvitation(orgCtx.org_id, inviteToken);
      setPendingInvites(previous => previous.filter(invite => invite.token !== inviteToken));
    } catch { alert('Failed to cancel invitation'); }
    finally { setCancellingToken(null); }
  }

  async function handleResendInvite(inviteToken: string) {
    if (!orgCtx?.org_id) return;
    setResendingToken(inviteToken);
    try {
      await resendInvitation(orgCtx.org_id, inviteToken);
      setResendResult(previous => ({ ...previous, [inviteToken]: true }));
      setTimeout(() => setResendResult(previous => { const next = { ...previous }; delete next[inviteToken]; return next; }), 3000);
    } catch { alert('Failed to resend invitation'); }
    finally { setResendingToken(null); }
  }

  async function handleRemove(member: OrgMember) {
    if (!orgCtx?.org_id) return;
    if (!window.confirm(`Remove ${member.full_name || member.email} from the organisation?`)) return;
    setRemovingId(member.user_id);
    try {
      await removeMember(orgCtx.org_id, member.user_id);
      setMembers(previous => previous.filter(existingMember => existingMember.user_id !== member.user_id));
    } catch { alert('Failed to remove member'); }
    finally { setRemovingId(null); }
  }

  if (!orgCtx?.org_id) {
    return (
      <div className="pt-[6.5rem] max-w-2xl mx-auto px-6 py-8 text-sm text-text-mute">
        You are not a member of any organisation.
      </div>
    );
  }

  return (
    <div className="pt-[6.5rem] max-w-2xl mx-auto px-6 pb-12 flex flex-col gap-4">
      {orgCtx.org_status === 'suspended' && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-700 text-sm px-4 py-3 rounded-lg flex items-center gap-2">
          <span className="font-semibold">Organisation suspended.</span>
          <span>Your data is read-only. Contact your platform administrator to restore access.</span>
        </div>
      )}

      <div>
        <Link to="/" className="inline-flex items-center gap-1.5 text-xs text-text-mute hover:text-text transition-colors mb-3">
          <ArrowLeft size={13} /> Back to Dashboard
        </Link>
        <div className="flex items-center gap-3 mb-1">
          {isOrgAdmin
            ? <Building2 size={20} className="text-teal" />
            : role === 'supervisor'
            ? <Users size={20} className="text-indigo-500" />
            : <User size={20} className="text-text-mid" />
          }
          <h1 className="text-2xl font-bold text-text">{pageTitle}</h1>
        </div>
        <p className="text-sm text-text-mute">{pageSubtitle}</p>
      </div>

      {isOrgAdmin && (
        <Card title="Organisation" icon={<Building2 size={13} className="text-text-mute" />}>
          <div className="flex items-start justify-between -mt-1">
            <div>
              <p className="text-base font-semibold text-text">{orgCtx.org_name}</p>
              <p className="text-xs text-text-mute font-mono mt-0.5">{orgCtx.org_id}</p>
            </div>
            <span className={`text-[10px] font-bold border rounded-full px-2.5 py-0.5 uppercase tracking-wide ${PLAN_COLORS[orgCtx.org_plan ?? 'trial'] ?? ''}`}>
              {orgCtx.org_plan ?? 'trial'}
            </span>
          </div>
        </Card>
      )}

      <Card
        title={`Team · ${members.length} member${members.length !== 1 ? 's' : ''}`}
        icon={<Users size={13} className="text-text-mute" />}
      >
        {membersLoading ? (
          <p className="text-xs text-text-mute -mt-2">Loading…</p>
        ) : (
          <div className="flex flex-col -mt-2">
            {members.map(member => {
              const isYou = member.user_id === user?.id;
              return (
                <div key={member.user_id} className="flex items-center gap-3 py-3 border-b border-border last:border-0">
                  <div className="w-9 h-9 rounded-full bg-navy/10 flex items-center justify-center text-xs font-bold text-navy shrink-0 select-none">
                    {(member.full_name || member.email).slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">
                      {member.full_name || member.email}
                      {isYou && <span className="text-[10px] font-normal text-text-mute ml-1.5">(you)</span>}
                    </p>
                    {member.full_name && <p className="text-xs text-text-mute truncate">{member.email}</p>}
                  </div>
                  {isOrgAdmin && !isYou ? (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <select
                        value={editingRole[member.user_id] ?? member.role}
                        onChange={selectEvent => setEditingRole(previous => ({ ...previous, [member.user_id]: selectEvent.target.value }))}
                        className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 cursor-pointer focus:outline-none ${ROLE_COLORS[editingRole[member.user_id] ?? member.role] ?? ''}`}
                      >
                        <option value="org_admin">Org Admin</option>
                        <option value="supervisor">Supervisor</option>
                        <option value="member">Member</option>
                      </select>
                      {editingRole[member.user_id] && editingRole[member.user_id] !== member.role && (
                        <button
                          onClick={() => handleRoleSave(member)}
                          disabled={savingRole === member.user_id}
                          className="text-[10px] font-semibold text-teal border border-teal/30 rounded px-1.5 py-0.5 hover:bg-teal/10 transition-colors disabled:opacity-40"
                        >
                          {savingRole === member.user_id ? '…' : 'Save'}
                        </button>
                      )}
                    </div>
                  ) : (
                    <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 shrink-0 ${ROLE_COLORS[member.role] ?? ''}`}>
                      {ROLE_LABELS[member.role] ?? member.role}
                    </span>
                  )}
                  {member.role === 'org_admin' && isYou && <Shield size={12} className="text-teal shrink-0" />}
                  {isOrgAdmin && !isYou && (
                    <button
                      onClick={() => handleRemove(member)}
                      disabled={removingId === member.user_id}
                      className="text-xs text-red/60 hover:text-red border border-red/20 hover:border-red/40 rounded-lg px-2.5 py-1 transition-colors shrink-0 disabled:opacity-40"
                    >
                      {removingId === member.user_id ? '…' : 'Remove'}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {canInvite && pendingInvites.length > 0 && (
        <Card
          title={`Pending Invitations · ${pendingInvites.length}`}
          icon={<Clock size={13} className="text-text-mute" />}
        >
          <div className="flex flex-col -mt-2">
            {pendingInvites.map(invite => (
              <div key={invite.token} className="flex items-center gap-3 py-2.5 border-b border-border last:border-0">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text truncate">{invite.email}</p>
                  <p className="text-xs text-text-mute">
                    {ROLE_LABELS[invite.role] ?? invite.role} · Expires{' '}
                    {new Date(invite.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 shrink-0 ${ROLE_COLORS[invite.role] ?? ''}`}>
                  {ROLE_LABELS[invite.role] ?? invite.role}
                </span>
                <button
                  onClick={() => handleResendInvite(invite.token)}
                  disabled={resendingToken === invite.token}
                  className="text-xs font-medium text-teal border border-teal/30 rounded-lg px-2.5 py-1 hover:bg-teal/10 transition-colors shrink-0 disabled:opacity-40"
                >
                  {resendResult[invite.token] ? 'Sent!' : resendingToken === invite.token ? '…' : 'Resend'}
                </button>
                {isOrgAdmin && (
                  <button
                    onClick={() => handleCancelInvite(invite.token)}
                    disabled={cancellingToken === invite.token}
                    className="text-xs text-red/60 hover:text-red border border-red/20 hover:border-red/40 rounded-lg px-2.5 py-1 transition-colors shrink-0 disabled:opacity-40"
                  >
                    {cancellingToken === invite.token ? '…' : 'Cancel'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {canInvite && (
        <Card title="Invite member" icon={<Mail size={13} className="text-text-mute" />}>
          <div className="flex flex-col gap-2.5 -mt-1">
            <div className="flex gap-2">
              <input
                type="email"
                value={inviteEmail}
                onChange={inputEvent => setInviteEmail(inputEvent.target.value)}
                placeholder="Email address"
                onKeyDown={keyEvent => keyEvent.key === 'Enter' && handleInvite()}
                className={INPUT + ' flex-1'}
              />
              <select
                value={inviteRole}
                onChange={selectEvent => setInviteRole(selectEvent.target.value)}
                className="border border-border rounded-lg px-2.5 py-2 text-sm text-text bg-panel focus:outline-none focus:ring-2 focus:ring-teal/30 shrink-0"
              >
                {isOrgAdmin && <option value="org_admin">Org Admin</option>}
                {isOrgAdmin && <option value="supervisor">Supervisor</option>}
                <option value="member">Member</option>
              </select>
            </div>
            <input
              type="text"
              value={inviteName}
              onChange={inputEvent => setInviteName(inputEvent.target.value)}
              placeholder="Their name (optional — appears in the invite email)"
              className={INPUT}
            />

            {inviteError && (
              <p className="text-xs text-red bg-red-bg border border-red/20 rounded-lg px-3 py-2">{inviteError}</p>
            )}

            {inviteLink && (
              <div className="bg-teal/5 border border-teal/20 rounded-lg p-3 flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-teal mb-1">Invite sent — copy link as backup</p>
                  <p className="text-[11px] text-text-mute break-all font-mono leading-relaxed">{inviteLink}</p>
                </div>
                <button
                  onClick={async () => {
                    await navigator.clipboard.writeText(inviteLink);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="text-xs font-semibold text-teal border border-teal/30 rounded-lg px-2.5 py-1 hover:bg-teal/10 transition-colors shrink-0"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            )}

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={handleInvite}
                disabled={inviting || !inviteEmail}
                className="text-sm font-semibold text-white bg-teal hover:bg-teal-soft px-5 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {inviting ? 'Sending…' : 'Send invite'}
              </button>
              {!isOrgAdmin && (
                <p className="text-xs text-text-mute">Supervisors can invite members only.</p>
              )}
            </div>
          </div>
        </Card>
      )}

      <div className="bg-panel rounded-xl border border-red/20 p-5 flex flex-col gap-2">
        <p className={`${LABEL} text-red/60`}>Leave Organisation</p>
        <p className="text-xs text-text-mute">
          {isOrgAdmin
            ? `You are an Org Admin. Promote another member to Org Admin before leaving.`
            : `You will immediately lose access to ${orgCtx.org_name} and all its workspaces.`}
        </p>
        <button
          onClick={handleLeaveOrg}
          disabled={leaving || isOrgAdmin}
          className="w-fit text-sm font-semibold text-red border border-red/30 hover:bg-red/5 px-4 py-2 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed mt-1"
        >
          {leaving ? 'Leaving…' : 'Leave organisation'}
        </button>
      </div>
    </div>
  );
}
