import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, ArrowLeft } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabaseClient'
import { fetchOrgMembers, inviteMember, removeMember } from '../api'
import type { OrgMember } from '../types'
import type { User } from '@supabase/supabase-js'

// ── shared style tokens ──────────────────────────────────────────────────────
const LABEL = 'text-[10px] font-semibold text-text-mute uppercase tracking-wider'
const INPUT = 'w-full border border-border-strong rounded-lg px-3 py-2 text-sm text-text bg-panel placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150'
const INPUT_RO = 'w-full border border-border rounded-lg px-3 py-2 text-sm text-text-mid bg-panel-2 select-all cursor-default'

// ── helpers ──────────────────────────────────────────────────────────────────
export function getInitialsFromUser(user: User | null): string {
  const fullName: string = user?.user_metadata?.full_name ?? ''
  if (fullName.trim()) {
    const parts = fullName.trim().split(/\s+/)
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
    return fullName.slice(0, 2).toUpperCase()
  }
  const email = user?.email ?? ''
  const local = email.split('@')[0]
  const parts = local.split(/[._-]/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return local.slice(0, 2).toUpperCase()
}

function formatDateTime(iso: string | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatDate(iso: string | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

// ── sub-components ────────────────────────────────────────────────────────────
function Card({ title, danger, children }: { title: string; danger?: boolean; children: React.ReactNode }) {
  return (
    <div className={`bg-panel rounded-xl p-5 flex flex-col gap-4 border ${danger ? 'border-red/30' : 'border-border'}`}>
      <p className={`${LABEL} ${danger ? 'text-red/70' : ''}`}>{title}</p>
      {children}
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-border last:border-0">
      <span className="text-xs text-text-mute shrink-0">{label}</span>
      <span className="text-xs text-text text-right font-medium">{value}</span>
    </div>
  )
}

function PasswordField({
  label, value, onChange, show, onToggle, placeholder, autoComplete,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  show: boolean
  onToggle: () => void
  placeholder: string
  autoComplete: string
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className={LABEL}>{label}</label>
      <div className="relative">
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className={`${INPUT} pr-10`}
        />
        <button
          type="button"
          onClick={onToggle}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-text-mute hover:text-text-mid transition-colors"
          aria-label={show ? 'Hide password' : 'Show password'}
        >
          {show ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </div>
  )
}

const ROLE_LABELS: Record<string, string> = { org_admin: 'Org Admin', supervisor: 'Supervisor', member: 'Member' }
const ROLE_COLORS: Record<string, string> = { org_admin: 'text-teal bg-teal/10 border-teal/30', supervisor: 'text-navy bg-navy/10 border-navy/30', member: 'text-text-mid bg-panel-2 border-border' }

// ── page ─────────────────────────────────────────────────────────────────────
export default function AccountPage() {
  const { user, orgCtx } = useAuth()
  const navigate = useNavigate()

  // org members
  const [members, setMembers] = useState<OrgMember[]>([])
  const [membersLoading, setMembersLoading] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('member')
  const [inviteName, setInviteName] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteResult, setInviteResult] = useState<{ link: string } | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const canManageOrg = orgCtx?.role === 'org_admin' || orgCtx?.role === 'supervisor'
  const isOrgAdmin = orgCtx?.role === 'org_admin'

  useEffect(() => {
    if (orgCtx?.org_id && canManageOrg) {
      setMembersLoading(true)
      fetchOrgMembers(orgCtx.org_id)
        .then(d => setMembers(d.members))
        .catch(() => {})
        .finally(() => setMembersLoading(false))
    }
  }, [orgCtx?.org_id, canManageOrg])

  async function handleInvite() {
    if (!inviteEmail || !orgCtx?.org_id) return
    setInviting(true)
    setInviteError(null)
    setInviteResult(null)
    try {
      const res = await inviteMember(orgCtx.org_id, inviteEmail, inviteRole, inviteName || undefined)
      setInviteResult({ link: res.invite_link })
      setInviteEmail(''); setInviteName('')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to send invite'
      setInviteError(msg)
    } finally {
      setInviting(false)
    }
  }

  async function handleRemove(member: OrgMember) {
    if (!orgCtx?.org_id) return
    if (!window.confirm(`Remove ${member.full_name || member.email} from the organisation?`)) return
    setRemovingId(member.user_id)
    try {
      await removeMember(orgCtx.org_id, member.user_id)
      setMembers(prev => prev.filter(m => m.user_id !== member.user_id))
    } catch {
      alert('Failed to remove member')
    } finally {
      setRemovingId(null)
    }
  }

  // profile
  const [displayName, setDisplayName] = useState<string>(user?.user_metadata?.full_name ?? '')
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileStatus, setProfileStatus] = useState<'idle' | 'success' | 'error'>('idle')

  // password
  const [currentPass, setCurrentPass] = useState('')
  const [newPass, setNewPass] = useState('')
  const [confirmPass, setConfirmPass] = useState('')
  const [showCurrentPass, setShowCurrentPass] = useState(false)
  const [showNewPass, setShowNewPass] = useState(false)
  const [showConfirmPass, setShowConfirmPass] = useState(false)
  const [passError, setPassError] = useState<string | null>(null)
  const [passSaving, setPassSaving] = useState(false)
  const [passStatus, setPassStatus] = useState<'idle' | 'success' | 'error'>('idle')

  // danger zone
  const [confirmSignOutAll, setConfirmSignOutAll] = useState(false)
  const [signingOutAll, setSigningOutAll] = useState(false)

  const isEmailProvider = user?.app_metadata?.provider === 'email'
  const initials = getInitialsFromUser({ ...user, user_metadata: { ...user?.user_metadata, full_name: displayName } } as User)
  const provider = user?.app_metadata?.provider === 'google' ? 'Google' : 'Email / Password'

  // ── handlers ────────────────────────────────────────────────────────────────
  async function handleProfileSave() {
    setProfileSaving(true)
    setProfileStatus('idle')
    try {
      const { error } = await supabase.auth.updateUser({ data: { full_name: displayName.trim() } })
      if (error) throw error
      setProfileStatus('success')
    } catch {
      setProfileStatus('error')
    } finally {
      setProfileSaving(false)
      setTimeout(() => setProfileStatus('idle'), 3000)
    }
  }

  async function handlePasswordChange() {
    setPassError(null)
    if (newPass.length < 8) { setPassError('New password must be at least 8 characters.'); return }
    if (newPass !== confirmPass) { setPassError('New password and confirmation do not match.'); return }
    if (newPass === currentPass) { setPassError('New password must be different from the current password.'); return }

    setPassSaving(true)
    setPassStatus('idle')
    try {
      const { error: reAuthError } = await supabase.auth.signInWithPassword({
        email: user!.email!,
        password: currentPass,
      })
      if (reAuthError) {
        setPassError('Current password is incorrect.')
        setPassSaving(false)
        return
      }
      const { error } = await supabase.auth.updateUser({ password: newPass })
      if (error) throw error
      setPassStatus('success')
      setCurrentPass(''); setNewPass(''); setConfirmPass('')
    } catch {
      setPassStatus('error')
    } finally {
      setPassSaving(false)
      setTimeout(() => setPassStatus('idle'), 3000)
    }
  }

  async function handleSignOutAll() {
    setSigningOutAll(true)
    try {
      await supabase.auth.signOut({ scope: 'global' })
      navigate('/login', { replace: true })
    } catch {
      setSigningOutAll(false)
      setConfirmSignOutAll(false)
    }
  }

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto px-6 py-8 flex flex-col gap-4">
      <div>
        <Link to="/cases" className="inline-flex items-center gap-1.5 text-xs text-text-mute hover:text-text transition-colors mb-3">
          <ArrowLeft size={13} /> Back to Cases
        </Link>
        <h1 className="text-2xl font-bold text-text">Account</h1>
        <p className="text-sm text-text-mute mt-0.5">Manage your profile and security settings</p>
      </div>

      {/* ── Section 1: Profile ─────────────────────────────────────────────── */}
      <Card title="Profile">
        {/* Live avatar preview */}
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-teal rounded-full flex items-center justify-center text-white font-bold text-sm shrink-0 select-none">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text truncate">
              {displayName.trim() || (user?.email ?? '—')}
            </p>
            <p className="text-xs text-text-mute truncate">{user?.email}</p>
          </div>
        </div>

        {/* Display name */}
        <div className="flex flex-col gap-1.5">
          <label className={LABEL}>Display Name</label>
          <input
            type="text"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            placeholder="Your full name"
            className={INPUT}
          />
        </div>

        {/* Email — read-only */}
        <div className="flex flex-col gap-1.5">
          <label className={LABEL}>Email</label>
          <input type="email" value={user?.email ?? ''} readOnly className={INPUT_RO} />
          <p className="text-xs text-text-mute">Email cannot be changed.</p>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleProfileSave}
            disabled={profileSaving}
            className="text-sm font-semibold text-white bg-teal hover:bg-teal-soft px-5 py-2 rounded-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {profileSaving ? 'Saving…' : 'Save Changes'}
          </button>
          {profileStatus === 'success' && <span className="text-xs text-green">Saved</span>}
          {profileStatus === 'error' && <span className="text-xs text-red">Failed — try again</span>}
        </div>
      </Card>

      {/* ── Section 2: Change Password (email users only) ───────────────────── */}
      {isEmailProvider && (
        <Card title="Change Password">
          {passError && (
            <p className="text-xs text-red bg-red-bg border border-red/20 rounded-lg px-3 py-2">{passError}</p>
          )}

          <PasswordField
            label="Current Password"
            value={currentPass}
            onChange={setCurrentPass}
            show={showCurrentPass}
            onToggle={() => setShowCurrentPass(p => !p)}
            placeholder="Enter current password"
            autoComplete="off"
          />
          <PasswordField
            label="New Password"
            value={newPass}
            onChange={setNewPass}
            show={showNewPass}
            onToggle={() => setShowNewPass(p => !p)}
            placeholder="At least 8 characters"
            autoComplete="new-password"
          />
          <PasswordField
            label="Confirm New Password"
            value={confirmPass}
            onChange={setConfirmPass}
            show={showConfirmPass}
            onToggle={() => setShowConfirmPass(p => !p)}
            placeholder="Repeat new password"
            autoComplete="new-password"
          />

          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={handlePasswordChange}
              disabled={passSaving || !currentPass || !newPass || !confirmPass}
              className="text-sm font-semibold text-white bg-teal hover:bg-teal-soft px-5 py-2 rounded-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {passSaving ? 'Updating…' : 'Update Password'}
            </button>
            {passStatus === 'success' && <span className="text-xs text-green">Password updated</span>}
            {passStatus === 'error' && <span className="text-xs text-red">Failed — try again</span>}
          </div>
        </Card>
      )}

      {/* ── Section 3: Session Info ─────────────────────────────────────────── */}
      <Card title="Session">
        <div className="-mt-2">
          <InfoRow label="Signed in as" value={user?.email ?? '—'} />
          <InfoRow label="Provider" value={provider} />
          <InfoRow label="Last sign in" value={formatDateTime(user?.last_sign_in_at)} />
          <InfoRow label="Account created" value={formatDate(user?.created_at)} />
        </div>
      </Card>

      {/* ── Section 4: Organisation (org_admin / supervisor only) ──────────── */}
      {canManageOrg && orgCtx?.org_id && (
        <Card title={`Organisation · ${orgCtx.org_name ?? orgCtx.org_id}`}>
          {/* Org meta */}
          <div className="-mt-2">
            <InfoRow label="Plan" value={(orgCtx.org_plan ?? 'trial').toUpperCase()} />
            <InfoRow label="Your role" value={ROLE_LABELS[orgCtx.role ?? ''] ?? orgCtx.role ?? '—'} />
          </div>

          {/* Members list */}
          <div>
            <p className={LABEL + ' mb-2'}>Members</p>
            {membersLoading ? (
              <p className="text-xs text-text-mute">Loading…</p>
            ) : members.length === 0 ? (
              <p className="text-xs text-text-mute">No members yet.</p>
            ) : (
              <div className="flex flex-col gap-1.5">
                {members.map(m => (
                  <div key={m.user_id} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                    <div className="w-7 h-7 rounded-full bg-navy/10 flex items-center justify-center text-[10px] font-bold text-navy shrink-0 select-none">
                      {(m.full_name || m.email).slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-text truncate">{m.full_name || m.email}</p>
                      {m.full_name && <p className="text-[11px] text-text-mute truncate">{m.email}</p>}
                    </div>
                    <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 shrink-0 ${ROLE_COLORS[m.role] ?? ''}`}>
                      {ROLE_LABELS[m.role] ?? m.role}
                    </span>
                    {isOrgAdmin && m.user_id !== user?.id && (
                      <button
                        onClick={() => handleRemove(m)}
                        disabled={removingId === m.user_id}
                        className="text-[11px] text-red/70 hover:text-red border border-red/20 hover:border-red/40 rounded px-2 py-0.5 transition-colors shrink-0 disabled:opacity-40"
                      >
                        {removingId === m.user_id ? '…' : 'Remove'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Invite form */}
          <div className="pt-1">
            <p className={LABEL + ' mb-3'}>Invite member</p>
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={e => setInviteEmail(e.target.value)}
                  placeholder="Email address"
                  className={INPUT + ' flex-1'}
                />
                <select
                  value={inviteRole}
                  onChange={e => setInviteRole(e.target.value)}
                  className="border border-border-strong rounded-lg px-2 py-2 text-sm text-text bg-panel focus:outline-none focus:ring-2 focus:ring-teal/30"
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
                placeholder="Name (optional)"
                className={INPUT}
              />
              {inviteError && <p className="text-xs text-red">{inviteError}</p>}
              {inviteResult && (
                <div className="bg-panel-2 border border-border rounded-lg p-3 flex flex-col gap-1">
                  <p className="text-xs font-semibold text-teal">Invite sent</p>
                  <p className="text-[11px] text-text-mute break-all font-mono">{inviteResult.link}</p>
                </div>
              )}
              <button
                onClick={handleInvite}
                disabled={inviting || !inviteEmail}
                className="w-fit text-sm font-semibold text-white bg-teal hover:bg-teal-soft px-5 py-2 rounded-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {inviting ? 'Sending…' : 'Send invite'}
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* ── Section 5: Danger Zone ──────────────────────────────────────────── */}
      <Card title="Danger Zone" danger>
        {confirmSignOutAll ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-text">
              This will sign you out on <span className="font-semibold">all devices</span>. Continue?
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSignOutAll}
                disabled={signingOutAll}
                className="text-sm font-semibold text-white bg-red hover:bg-red/90 px-4 py-2 rounded-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {signingOutAll ? 'Signing out…' : 'Confirm'}
              </button>
              <button
                onClick={() => setConfirmSignOutAll(false)}
                className="text-sm text-text-mute hover:text-text transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            <p className="text-xs text-text-mute">
              Invalidates all active sessions across every device.
            </p>
            <button
              onClick={() => setConfirmSignOutAll(true)}
              className="w-fit text-sm font-semibold text-red border border-red/30 hover:bg-red-bg px-4 py-2 rounded-lg transition-colors duration-150 mt-1"
            >
              Sign out everywhere
            </button>
          </div>
        )}
      </Card>
    </div>
  )
}
