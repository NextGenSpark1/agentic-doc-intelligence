import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { getInvitation, acceptInvitation } from '../api/orgs';
import type { InvitationPreview } from '../types';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../lib/supabase';

const ROLE_LABELS: Record<string, string> = {
  org_admin: 'Organisation Admin',
  supervisor: 'Supervisor',
  member: 'Team Member',
};

export function InviteAcceptPage() {
  const { token } = useParams<{ token: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const autoAccept = searchParams.get('auto') === '1';
  const [invite, setInvite] = useState<InvitationPreview | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'accepting' | 'accepted' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!token) return;
    getInvitation(token)
      .then(data => { setInvite(data); setStatus('ready'); })
      .catch(error => {
        const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setErrorMsg(detail ?? 'Invalid or expired invitation.');
        setStatus('error');
      });
  }, [token]);

  useEffect(() => {
    if (!autoAccept || status !== 'ready' || !user || !invite) return;
    if (user.email?.toLowerCase() !== invite.email?.toLowerCase()) return;
    handleAccept();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoAccept, status, user, invite]);

  async function handleAccept() {
    if (!token) return;
    setStatus('accepting');
    try {
      await acceptInvitation(token);
      setStatus('accepted');
      setTimeout(() => navigate('/', { replace: true }), 2000);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErrorMsg(detail ?? 'Failed to accept invitation.');
      setStatus('error');
    }
  }

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center p-6">
      <div className="bg-panel border border-border rounded-2xl shadow-lg p-10 max-w-md w-full">
        <div className="flex items-center gap-3 mb-8">
          <img src="/NG logo.jpeg" alt="NextGen Spark" className="w-8 h-8 rounded-lg object-contain bg-white border border-border p-0.5 shrink-0" />
          <span className="font-semibold text-sm text-text tracking-wide">Tendering Intelligence</span>
        </div>

        {status === 'loading' && (
          <div className="text-center py-6">
            <div className="w-5 h-5 border-2 border-teal border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-text-mute">Loading invitation…</p>
          </div>
        )}

        {status === 'error' && (
          <div className="text-center">
            <p className="text-lg font-semibold text-text mb-2">Invitation unavailable</p>
            <p className="text-sm text-text-mute mb-6">{errorMsg}</p>
            <Link to="/" className="text-sm text-teal hover:text-teal-soft font-medium transition-colors">
              Go to homepage
            </Link>
          </div>
        )}

        {status === 'accepted' && (
          <div className="text-center">
            <div className="w-12 h-12 bg-teal/10 border border-teal/20 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
              ✓
            </div>
            <p className="text-lg font-semibold text-text mb-2">You're in!</p>
            <p className="text-sm text-text-mute">Redirecting to your workspace…</p>
          </div>
        )}

        {(status === 'ready' || status === 'accepting') && invite && (
          <>
            <p className="text-sm text-text-mute mb-1.5">You've been invited to join</p>
            <p className="text-2xl font-bold text-text mb-2">{invite.org_name}</p>
            <span className="inline-block text-[11px] font-bold uppercase tracking-wide bg-teal/10 text-teal border border-teal/20 rounded-full px-3 py-0.5 mb-7">
              {ROLE_LABELS[invite.role] ?? invite.role}
            </span>

            {user ? (
              user.email?.toLowerCase() === invite.email?.toLowerCase() ? (
                <div className="flex flex-col gap-3">
                  <p className="text-sm text-text-mute">
                    Accepting as <span className="font-medium text-text">{user.email}</span>
                  </p>
                  <button
                    onClick={handleAccept}
                    disabled={status === 'accepting'}
                    className="w-full py-3 rounded-xl bg-navy hover:bg-navy-soft text-white font-semibold text-sm transition-colors disabled:opacity-60"
                  >
                    {status === 'accepting' ? 'Accepting…' : 'Accept invitation'}
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                    <p className="text-sm font-semibold text-amber-700 mb-1">Wrong account</p>
                    <p className="text-sm text-amber-600">
                      This invite was sent to <strong>{invite.email}</strong>.<br />
                      You're signed in as <strong>{user.email}</strong>.
                    </p>
                  </div>
                  <p className="text-xs text-text-mute text-center">
                    Sign out and sign in with the invited email to continue.
                  </p>
                  <Link
                    to={`/login?invite=${token}`}
                    onClick={() => supabase.auth.signOut()}
                    className="block text-center py-3 rounded-xl bg-navy hover:bg-navy-soft text-white font-semibold text-sm transition-colors"
                  >
                    Sign out &amp; switch account
                  </Link>
                </div>
              )
            ) : (
              <div className="flex flex-col gap-2.5">
                <p className="text-sm text-text-mute mb-1">Sign in or create an account to accept.</p>
                <Link
                  to={`/login?invite=${token}`}
                  className="block text-center py-3 rounded-xl bg-navy hover:bg-navy-soft text-white font-semibold text-sm transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  to={`/register?invite=${token}`}
                  className="block text-center py-3 rounded-xl border border-border hover:border-border-strong text-text font-medium text-sm transition-colors"
                >
                  Create account
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
