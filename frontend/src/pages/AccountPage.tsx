import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { supabase } from '../lib/supabaseClient'
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

// ── page ─────────────────────────────────────────────────────────────────────
export default function AccountPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

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

      {/* ── Section 4: Danger Zone ──────────────────────────────────────────── */}
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
