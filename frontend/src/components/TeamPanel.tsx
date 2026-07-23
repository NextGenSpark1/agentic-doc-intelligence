import { useState, useEffect } from 'react'
import { fetchOrgMembers, inviteMember, removeMember } from '../api'
import type { OrgMember } from '../types'
import { useAuth } from '../context/AuthContext'

const ROLE_LABELS: Record<string, string> = {
  org_admin: 'Admin',
  supervisor: 'Supervisor',
  member: 'Member',
}

const ROLE_COLORS: Record<string, { color: string; bg: string }> = {
  org_admin: { color: '#7C3AED', bg: '#F5F3FF' },
  supervisor: { color: '#0D9488', bg: '#F0FDFA' },
  member: { color: '#64748B', bg: '#F8FAFC' },
}

export default function TeamPanel() {
  const { user, orgCtx } = useAuth()
  const [members, setMembers] = useState<OrgMember[]>([])
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'supervisor' | 'member'>('member')
  const [inviting, setInviting] = useState(false)
  const [lastInviteLink, setLastInviteLink] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const orgId = orgCtx?.org_id
  const myRole = orgCtx?.role
  const canInvite = myRole === 'org_admin' || myRole === 'supervisor'
  const canRemove = myRole === 'org_admin'

  useEffect(() => {
    if (!orgId) return
    fetchOrgMembers(orgId)
      .then(d => setMembers(d.members))
      .finally(() => setLoading(false))
  }, [orgId])

  const invitableRoles = myRole === 'org_admin'
    ? [{ value: 'supervisor', label: 'Supervisor' }, { value: 'member', label: 'Member' }]
    : [{ value: 'member', label: 'Member' }]

  async function handleInvite() {
    if (!orgId || !inviteEmail) return
    setInviting(true)
    setError(null)
    try {
      const result = await inviteMember(orgId, inviteEmail, inviteRole)
      setLastInviteLink(window.location.origin + '/invite/' + result.invite_token)
      setInviteEmail('')
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to send invitation.')
    } finally {
      setInviting(false)
    }
  }

  async function handleRemove(userId: string) {
    if (!orgId || !confirm('Remove this member from the organisation?')) return
    try {
      await removeMember(orgId, userId)
      setMembers(prev => prev.filter(m => m.user_id !== userId))
    } catch {
      alert('Failed to remove member.')
    }
  }

  function copyLink() {
    if (lastInviteLink) {
      navigator.clipboard.writeText(lastInviteLink)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (!orgId) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm text-text-mute">No organisation assigned yet.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* Org header */}
      <div className="bg-panel border border-border rounded-xl px-5 py-4">
        <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider mb-1">Organisation</p>
        <p className="text-sm font-bold text-text">{orgCtx?.org_name ?? 'Your Organisation'}</p>
        <span className="text-[10px] font-semibold text-text-mute capitalize">{orgCtx?.org_plan ?? 'trial'} plan</span>
      </div>

      {/* Invite section */}
      {canInvite && (
        <div className="bg-panel border border-border rounded-xl px-5 py-4 flex flex-col gap-3">
          <p className="text-xs font-semibold text-text-mid uppercase tracking-wider">Invite team member</p>
          <div className="flex gap-2">
            <input
              type="email"
              value={inviteEmail}
              onChange={e => setInviteEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleInvite()}
              placeholder="colleague@example.com"
              className="flex-1 text-sm bg-canvas-deep border border-border rounded-lg px-3 py-2 placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30"
            />
            <select
              value={inviteRole}
              onChange={e => setInviteRole(e.target.value as 'supervisor' | 'member')}
              className="text-sm bg-canvas-deep border border-border rounded-lg px-3 py-2 focus:outline-none"
            >
              {invitableRoles.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
            <button
              onClick={handleInvite}
              disabled={inviting || !inviteEmail}
              className="px-4 py-2 text-sm font-semibold text-white bg-navy rounded-lg hover:bg-navy-soft transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {inviting ? 'Sending…' : 'Invite'}
            </button>
          </div>
          {error && <p className="text-xs text-red-500">{error}</p>}
          {lastInviteLink && (
            <div className="flex items-center gap-2 bg-teal/5 border border-teal/20 rounded-lg px-3 py-2">
              <p className="text-xs text-text-mid flex-1 font-mono truncate">{lastInviteLink}</p>
              <button onClick={copyLink} className="text-xs font-semibold text-teal hover:text-teal-soft whitespace-nowrap">
                {copied ? 'Copied!' : 'Copy link'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Members list */}
      <div className="bg-panel border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <p className="text-xs font-semibold text-text-mid uppercase tracking-wider">
            Team members {members.length > 0 && <span className="font-normal normal-case tracking-normal text-text-mute">({members.length})</span>}
          </p>
        </div>
        {loading ? (
          <div className="px-5 py-8 text-center text-xs text-text-mute">Loading…</div>
        ) : members.length === 0 ? (
          <div className="px-5 py-8 text-center text-xs text-text-mute">No members yet.</div>
        ) : (
          <div className="divide-y divide-border">
            {members.map(m => {
              const rc = ROLE_COLORS[m.role] ?? ROLE_COLORS.member
              const isMe = m.user_id === user?.id
              return (
                <div key={m.member_id} className="px-5 py-3 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-navy/10 flex items-center justify-center shrink-0">
                    <span className="text-xs font-bold text-navy">{(m.full_name ?? m.email)[0].toUpperCase()}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-text truncate">{m.full_name ?? m.email}</p>
                    {m.full_name && <p className="text-xs text-text-mute truncate">{m.email}</p>}
                  </div>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{ color: rc.color, background: rc.bg }}
                  >
                    {ROLE_LABELS[m.role] ?? m.role}
                  </span>
                  {isMe && <span className="text-[10px] text-text-mute">you</span>}
                  {canRemove && !isMe && (
                    <button
                      onClick={() => handleRemove(m.user_id)}
                      className="text-text-mute hover:text-red-500 transition-colors text-xs"
                      title="Remove member"
                    >
                      ✕
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
