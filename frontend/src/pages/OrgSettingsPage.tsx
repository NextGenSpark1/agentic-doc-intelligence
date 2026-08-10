import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Users, Mail, Building2, Shield, User, Clock } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchOrgMembers, inviteMember, removeMember, fetchPendingInvitations, cancelInvitation, resendInvitation } from '../api'
import type { OrgMember, PendingInvitation } from '../types'

const LABEL = 'text-[10px] font-semibold text-text-mute uppercase tracking-wider'
const INPUT = 'w-full border border-border-strong rounded-lg px-3 py-2 text-sm text-text bg-panel placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150'

const ROLE_LABELS: Record<string, string> = {
  org_admin: 'Org Admin', supervisor: 'Supervisor', member: 'Member',
}
const ROLE_COLORS: Record<string, string> = {
  org_admin: 'text-teal bg-teal/10 border-teal/30',
  supervisor: 'text-indigo-600 bg-indigo-50 border-indigo-200',
  member: 'text-text-mid bg-panel-2 border-border',
}
const PLAN_COLORS: Record<string, string> = {
  trial: 'text-amber-600 bg-amber-50 border-amber-200',
  pro: 'text-teal bg-teal/10 border-teal/30',
  enterprise: 'text-purple-600 bg-purple-50 border-purple-200',
}

// Per-role page config
const ROLE_CONFIG: Record<string, { title: string; subtitle: string; icon: React.ReactNode }> = {
  org_admin: {
    title: 'Org Settings',
    subtitle: 'Manage your organisation, team members, and invitations',
    icon: <Building2 size={20} className="text-teal" />,
  },
  supervisor: {
    title: 'Team',
    subtitle: 'View your team and invite new members',
    icon: <Users size={20} className="text-indigo-500" />,
  },
  member: {
    title: 'My Team',
    subtitle: 'See who else is in your organisation',
    icon: <User size={20} className="text-text-mid" />,
  },
}

function Card({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-panel rounded-xl border border-border p-5 flex flex-col gap-4">
      <div className="flex items-center gap-2">
        {icon}
        <p className={LABEL}>{title}</p>
      </div>
      {children}
    </div>
  )
}

export default function OrgSettingsPage() {
  const { user, orgCtx } = useAuth()
  const role = orgCtx?.role ?? 'member'
  const isOrgAdmin = role === 'org_admin'
  const canInvite = role === 'org_admin' || role === 'supervisor'

  const [members, setMembers] = useState<OrgMember[]>([])
  const [membersLoading, setMembersLoading] = useState(true)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const [pendingInvites, setPendingInvites] = useState<PendingInvitation[]>([])
  const [cancellingToken, setCancellingToken] = useState<string | null>(null)
  const [resendingToken, setResendingToken] = useState<string | null>(null)
  const [resendResult, setResendResult] = useState<Record<string, boolean>>({})

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('member')
  const [inviteName, setInviteName] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteLink, setInviteLink] = useState<string | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const config = ROLE_CONFIG[role] ?? ROLE_CONFIG.member

  useEffect(() => {
    if (!orgCtx?.org_id) return
    fetchOrgMembers(orgCtx.org_id)
      .then(d => setMembers(d.members))
      .catch(() => {})
      .finally(() => setMembersLoading(false))
    if (canInvite) {
      fetchPendingInvitations(orgCtx.org_id)
        .then(setPendingInvites)
        .catch(() => {})
    }
  }, [orgCtx?.org_id, canInvite])

  async function handleInvite() {
    if (!inviteEmail || !orgCtx?.org_id) return
    setInviting(true)
    setInviteError(null)
    setInviteLink(null)
    try {
      const res = await inviteMember(orgCtx.org_id, inviteEmail, inviteRole, inviteName || undefined)
      setInviteLink(res.invite_link)
      setInviteEmail('')
      setInviteName('')
      if (orgCtx?.org_id) fetchPendingInvitations(orgCtx.org_id).then(setPendingInvites).catch(() => {})
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to send invite'
      setInviteError(msg)
    } finally {
      setInviting(false)
    }
  }

  async function handleCancelInvite(token: string) {
    if (!orgCtx?.org_id || !window.confirm('Cancel this invitation?')) return
    setCancellingToken(token)
    try {
      await cancelInvitation(orgCtx.org_id, token)
      setPendingInvites(prev => prev.filter(i => i.token !== token))
    } catch { alert('Failed to cancel invitation') }
    finally { setCancellingToken(null) }
  }

  async function handleResendInvite(token: string) {
    if (!orgCtx?.org_id) return
    setResendingToken(token)
    try {
      await resendInvitation(orgCtx.org_id, token)
      setResendResult(prev => ({ ...prev, [token]: true }))
      setTimeout(() => setResendResult(prev => { const n = { ...prev }; delete n[token]; return n }), 3000)
    } catch { alert('Failed to resend invitation') }
    finally { setResendingToken(null) }
  }

  async function handleRemove(m: OrgMember) {
    if (!orgCtx?.org_id) return
    if (!window.confirm(`Remove ${m.full_name || m.email} from the organisation?`)) return
    setRemovingId(m.user_id)
    try {
      await removeMember(orgCtx.org_id, m.user_id)
      setMembers(prev => prev.filter(x => x.user_id !== m.user_id))
    } catch {
      alert('Failed to remove member')
    } finally {
      setRemovingId(null)
    }
  }

  if (!orgCtx?.org_id) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-8 text-sm text-text-mute">
        You are not a member of any organisation.
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 flex flex-col gap-4">
      {/* Header */}
      <div>
        <Link to="/cases" className="inline-flex items-center gap-1.5 text-xs text-text-mute hover:text-text transition-colors mb-3">
          <ArrowLeft size={13} /> Back to Cases
        </Link>
        <div className="flex items-center gap-3 mb-1">
          {config.icon}
          <h1 className="text-2xl font-bold text-text">{config.title}</h1>
        </div>
        <p className="text-sm text-text-mute">{config.subtitle}</p>
      </div>

      {/* Org Overview — org_admin only */}
      {isOrgAdmin && (
        <Card title="Organisation" icon={<Building2 size={13} className="text-text-mute" />}>
          <div className="flex items-start justify-between -mt-1">
            <div>
              <p className="text-base font-semibold text-text">{orgCtx.org_name}</p>
              <p className="text-xs text-text-mute font-mono mt-0.5">{orgCtx.org_id}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-bold border rounded-full px-2.5 py-0.5 uppercase tracking-wide ${PLAN_COLORS[orgCtx.org_plan ?? 'trial'] ?? ''}`}>
                {orgCtx.org_plan ?? 'trial'}
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* Members */}
      <Card title={`Team · ${members.length} member${members.length !== 1 ? 's' : ''}`} icon={<Users size={13} className="text-text-mute" />}>
        {membersLoading ? (
          <p className="text-xs text-text-mute -mt-2">Loading…</p>
        ) : (
          <div className="flex flex-col -mt-2">
            {members.map(m => {
              const isYou = m.user_id === user?.id
              return (
                <div key={m.user_id} className="flex items-center gap-3 py-3 border-b border-border last:border-0">
                  <div className="w-9 h-9 rounded-full bg-navy/10 flex items-center justify-center text-xs font-bold text-navy shrink-0 select-none">
                    {(m.full_name || m.email).slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">
                      {m.full_name || m.email}
                      {isYou && <span className="text-[10px] font-normal text-text-mute ml-1.5">(you)</span>}
                    </p>
                    {m.full_name && <p className="text-xs text-text-mute truncate">{m.email}</p>}
                  </div>
                  {/* Role badge */}
                  <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 shrink-0 ${ROLE_COLORS[m.role] ?? ''}`}>
                    {ROLE_LABELS[m.role] ?? m.role}
                  </span>
                  {/* Role icon hint for members */}
                  {m.role === 'org_admin' && <Shield size={12} className="text-teal shrink-0" />}
                  {/* Remove — org_admin only, not yourself */}
                  {isOrgAdmin && !isYou && (
                    <button
                      onClick={() => handleRemove(m)}
                      disabled={removingId === m.user_id}
                      className="text-xs text-red/60 hover:text-red border border-red/20 hover:border-red/40 rounded-lg px-2.5 py-1 transition-colors shrink-0 disabled:opacity-40"
                    >
                      {removingId === m.user_id ? '…' : 'Remove'}
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* Pending Invitations — org_admin + supervisor */}
      {canInvite && pendingInvites.length > 0 && (
        <Card title={`Pending Invitations · ${pendingInvites.length}`} icon={<Clock size={13} className="text-text-mute" />}>
          <div className="flex flex-col -mt-2">
            {pendingInvites.map(inv => (
              <div key={inv.token} className="flex items-center gap-3 py-2.5 border-b border-border last:border-0">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text truncate">{inv.email}</p>
                  <p className="text-xs text-text-mute">
                    {ROLE_LABELS[inv.role] ?? inv.role} · Expires {new Date(inv.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 shrink-0 ${ROLE_COLORS[inv.role] ?? ''}`}>
                  {ROLE_LABELS[inv.role] ?? inv.role}
                </span>
                <button
                  onClick={() => handleResendInvite(inv.token)}
                  disabled={resendingToken === inv.token}
                  className="text-xs font-medium text-teal border border-teal/30 rounded-lg px-2.5 py-1 hover:bg-teal/10 transition-colors shrink-0 disabled:opacity-40"
                >
                  {resendResult[inv.token] ? 'Sent!' : resendingToken === inv.token ? '…' : 'Resend'}
                </button>
                {isOrgAdmin && (
                  <button
                    onClick={() => handleCancelInvite(inv.token)}
                    disabled={cancellingToken === inv.token}
                    className="text-xs text-red/60 hover:text-red border border-red/20 hover:border-red/40 rounded-lg px-2.5 py-1 transition-colors shrink-0 disabled:opacity-40"
                  >
                    {cancellingToken === inv.token ? '…' : 'Cancel'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Invite — org_admin + supervisor */}
      {canInvite && (
        <Card title="Invite member" icon={<Mail size={13} className="text-text-mute" />}>
          <div className="flex flex-col gap-2.5 -mt-1">
            <div className="flex gap-2">
              <input
                type="email"
                value={inviteEmail}
                onChange={e => setInviteEmail(e.target.value)}
                placeholder="Email address"
                onKeyDown={e => e.key === 'Enter' && handleInvite()}
                className={INPUT + ' flex-1'}
              />
              <select
                value={inviteRole}
                onChange={e => setInviteRole(e.target.value)}
                className="border border-border-strong rounded-lg px-2.5 py-2 text-sm text-text bg-panel focus:outline-none focus:ring-2 focus:ring-teal/30 shrink-0"
              >
                {isOrgAdmin && <option value="org_admin">Org Admin</option>}
                {isOrgAdmin && <option value="supervisor">Supervisor</option>}
                <option value="member">Member</option>
              </select>
            </div>
            <input
              type="text"
              value={inviteName}
              onChange={e => setInviteName(e.target.value)}
              placeholder="Their name (optional — appears in the email)"
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
                    await navigator.clipboard.writeText(inviteLink)
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
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
                className="text-sm font-semibold text-white bg-teal hover:bg-teal-soft px-5 py-2 rounded-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
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
    </div>
  )
}
