import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import { fetchInvitation, acceptInvitation } from '../api'
import type { InvitationPreview } from '../types'
import { useAuth } from '../context/AuthContext'

const ROLE_LABELS: Record<string, string> = {
  org_admin: 'Organisation Admin',
  supervisor: 'Supervisor',
  member: 'Team Member',
}

export default function InviteAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const autoAccept = searchParams.get('auto') === '1'
  const [invite, setInvite] = useState<InvitationPreview | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'accepting' | 'accepted' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!token) return
    fetchInvitation(token)
      .then(data => { setInvite(data); setStatus('ready') })
      .catch(err => {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Invalid or expired invitation.'
        setErrorMsg(msg)
        setStatus('error')
      })
  }, [token])

  // Auto-accept when coming back from login redirect (?auto=1) and email matches
  useEffect(() => {
    if (!autoAccept || status !== 'ready' || !user || !invite) return
    if (user.email?.toLowerCase() !== invite.email?.toLowerCase()) return
    handleAccept()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoAccept, status, user, invite])

  async function handleAccept() {
    if (!token) return
    setStatus('accepting')
    try {
      await acceptInvitation(token)
      setStatus('accepted')
      setTimeout(() => navigate('/'), 2000)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to accept invitation.'
      setErrorMsg(msg)
      setStatus('error')
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#F8FAFC', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{ background: '#fff', borderRadius: 16, boxShadow: '0 4px 24px rgba(0,0,0,0.10)', padding: '40px 48px', maxWidth: 440, width: '100%' }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div style={{ width: 32, height: 32, background: '#0F172A', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: '#fff', fontWeight: 800, fontSize: 14 }}>N</span>
          </div>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#0F172A' }}>NextGen Spark</span>
        </div>

        {status === 'loading' && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ width: 20, height: 20, border: '2px solid #E2E8F0', borderTop: '2px solid #0E7C86', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
            <p style={{ color: '#64748B', fontSize: 14 }}>Loading invitation…</p>
          </div>
        )}

        {status === 'error' && (
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', marginBottom: 8 }}>Invitation unavailable</p>
            <p style={{ fontSize: 14, color: '#64748B', marginBottom: 24 }}>{errorMsg}</p>
            <Link to="/" style={{ fontSize: 14, color: '#0E7C86', fontWeight: 600 }}>Go to homepage</Link>
          </div>
        )}

        {status === 'accepted' && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: 48, height: 48, background: '#F0FDFA', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontSize: 24 }}>✓</div>
            <p style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', marginBottom: 8 }}>You're in!</p>
            <p style={{ fontSize: 14, color: '#64748B' }}>Redirecting to your workspace…</p>
          </div>
        )}

        {(status === 'ready' || status === 'accepting') && invite && (
          <>
            <p style={{ fontSize: 13, color: '#64748B', marginBottom: 6 }}>You've been invited to join</p>
            <p style={{ fontSize: 24, fontWeight: 800, color: '#0F172A', marginBottom: 8 }}>{invite.org_name}</p>
            <span style={{
              display: 'inline-block', fontSize: 11, fontWeight: 700,
              background: '#F0FDFA', color: '#0E7C86', border: '1px solid #5EEAD4',
              borderRadius: 20, padding: '3px 10px', marginBottom: 28,
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              {ROLE_LABELS[invite.role] ?? invite.role}
            </span>

            {user ? (
              user.email?.toLowerCase() === invite.email?.toLowerCase() ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <p style={{ fontSize: 13, color: '#64748B' }}>
                    Accepting as <strong style={{ color: '#0F172A' }}>{user.email}</strong>
                  </p>
                  <button
                    onClick={handleAccept}
                    disabled={status === 'accepting'}
                    style={{
                      width: '100%', padding: '12px', borderRadius: 10,
                      background: '#0F172A', color: '#fff', fontWeight: 700,
                      fontSize: 14, border: 'none', cursor: 'pointer',
                      opacity: status === 'accepting' ? 0.7 : 1,
                    }}
                  >
                    {status === 'accepting' ? 'Accepting…' : 'Accept invitation'}
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ background: '#FFF7ED', border: '1px solid #FED7AA', borderRadius: 10, padding: '14px 16px' }}>
                    <p style={{ fontSize: 13, fontWeight: 700, color: '#C2410C', margin: '0 0 4px' }}>Wrong account</p>
                    <p style={{ fontSize: 13, color: '#78350F', margin: 0 }}>
                      This invite was sent to <strong>{invite.email}</strong>.<br />
                      You're signed in as <strong>{user.email}</strong>.
                    </p>
                  </div>
                  <p style={{ fontSize: 12, color: '#94A3B8', margin: 0, textAlign: 'center' }}>Sign out and sign in with the invited email to continue.</p>
                  <Link
                    to={`/login?invite=${token}`}
                    onClick={async () => { const { supabase } = await import('../lib/supabaseClient'); await supabase.auth.signOut() }}
                    style={{
                      display: 'block', textAlign: 'center', padding: '12px',
                      borderRadius: 10, background: '#0F172A', color: '#fff',
                      fontWeight: 700, fontSize: 14, textDecoration: 'none',
                    }}
                  >
                    Sign out & switch account
                  </Link>
                </div>
              )
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <p style={{ fontSize: 13, color: '#64748B', marginBottom: 4 }}>Sign in or create an account to accept.</p>
                <Link
                  to={`/login?invite=${token}`}
                  style={{
                    display: 'block', textAlign: 'center', padding: '12px',
                    borderRadius: 10, background: '#0F172A', color: '#fff',
                    fontWeight: 700, fontSize: 14, textDecoration: 'none',
                  }}
                >
                  Sign in
                </Link>
                <Link
                  to={`/register?invite=${token}`}
                  style={{
                    display: 'block', textAlign: 'center', padding: '12px',
                    borderRadius: 10, border: '1.5px solid #E2E8F0', color: '#0F172A',
                    fontWeight: 600, fontSize: 14, textDecoration: 'none',
                  }}
                >
                  Create account
                </Link>
              </div>
            )}
          </>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
