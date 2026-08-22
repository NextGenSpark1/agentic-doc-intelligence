import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, Eye, EyeOff, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { supabase } from '../lib/supabase';

type PageState = 'waiting' | 'ready' | 'success' | 'invalid';

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [pageState, setPageState] = useState<PageState>('waiting');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') setPageState('ready');
    });
    const timeout = setTimeout(() => {
      setPageState(previous => previous === 'waiting' ? 'invalid' : previous);
    }, 3000);
    return () => { subscription.unsubscribe(); clearTimeout(timeout); };
  }, []);

  async function handleSubmit(formEvent: React.FormEvent) {
    formEvent.preventDefault();
    setError('');
    if (newPass.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (newPass !== confirmPass) { setError('Passwords do not match.'); return; }
    setSaving(true);
    try {
      const { error: updateError } = await supabase.auth.updateUser({ password: newPass });
      if (updateError) throw updateError;
      setPageState('success');
      setTimeout(() => navigate('/', { replace: true }), 2500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update password.');
    } finally {
      setSaving(false);
    }
  }

  const leftPanel = (
    <div className="hidden lg:flex lg:w-[45%] bg-navy-deep flex-col justify-between p-12 relative overflow-hidden select-none">
      <div className="absolute inset-0 opacity-[0.06] pointer-events-none">
        <svg width="100%" height="100%">
          <defs>
            <pattern id="rp-grid" x="0" y="0" width="48" height="48" patternUnits="userSpaceOnUse">
              <rect x="0" y="0" width="24" height="24" fill="#1558D4" />
              <rect x="24" y="24" width="24" height="24" fill="#1558D4" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#rp-grid)" />
        </svg>
      </div>
      <div className="relative z-10 flex items-center gap-3">
        <img src="/NG logo.jpeg" alt="NextGen Spark" className="w-9 h-9 rounded-lg object-contain bg-white p-0.5 shrink-0" />
        <span className="text-white font-semibold tracking-wide text-sm">NextGen Spark</span>
      </div>
      <div className="relative z-10">
        <div className="w-14 h-1 bg-teal rounded-full mb-8" />
        <h2 className="text-white text-3xl font-semibold leading-snug mb-4">
          Bid smarter.<br />
          <span className="text-teal">Win with confidence.</span>
        </h2>
        <p className="text-white/50 text-sm leading-relaxed max-w-xs">
          AI-extracted requirements, compliance tracking, and evidence-backed decisions in one place.
        </p>
      </div>
      <p className="relative z-10 text-white/25 text-xs">&copy; {new Date().getFullYear()} NextGen Spark</p>
    </div>
  );

  function rightContent() {
    if (pageState === 'waiting') {
      return (
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="w-5 h-5 border-2 border-teal border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-mute">Verifying reset link…</p>
        </div>
      );
    }

    if (pageState === 'invalid') {
      return (
        <div className="w-full max-w-md flex flex-col items-center text-center gap-5">
          <div className="w-14 h-14 bg-red-bg border border-red/20 rounded-2xl flex items-center justify-center">
            <AlertCircle size={28} className="text-red" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-text mb-2">Link expired</h1>
            <p className="text-sm text-text-mute leading-relaxed">
              This password reset link is invalid or has expired.<br />
              Please request a new one.
            </p>
          </div>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="text-sm font-semibold text-white bg-navy hover:bg-navy-soft px-5 py-2.5 rounded-lg transition-colors"
          >
            Back to sign in
          </button>
        </div>
      );
    }

    if (pageState === 'success') {
      return (
        <div className="w-full max-w-md flex flex-col items-center text-center gap-5">
          <div className="w-14 h-14 bg-teal/10 border border-teal/20 rounded-2xl flex items-center justify-center">
            <CheckCircle2 size={28} className="text-teal" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-text mb-2">Password updated</h1>
            <p className="text-sm text-text-mute">Redirecting you to the app…</p>
          </div>
        </div>
      );
    }

    return (
      <div className="w-full max-w-md">
        <div className="lg:hidden flex justify-center mb-8">
          <img src="/NG logo with text.jpeg" alt="NextGen Spark" className="h-10 object-contain" />
        </div>
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-text mb-1">Set new password</h1>
          <p className="text-sm text-text-mute">Choose a strong password for your account.</p>
        </div>
        {error && (
          <div className="mb-5 flex items-start gap-2.5 bg-red-bg border border-red/20 text-red text-sm px-4 py-3 rounded-lg">
            <AlertCircle size={15} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">
              New Password
            </label>
            <div className="relative">
              <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-mute pointer-events-none" />
              <input
                type={showNew ? 'text' : 'password'}
                value={newPass}
                onChange={inputEvent => setNewPass(inputEvent.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                className="w-full bg-panel border border-border rounded-lg pl-10 pr-11 py-2.5 text-sm text-text placeholder:text-text-mute outline-none focus:border-teal focus:ring-2 focus:ring-teal/20 transition-colors"
              />
              <button type="button" onClick={() => setShowNew(previous => !previous)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-mute hover:text-text-mid transition-colors"
                aria-label={showNew ? 'Hide' : 'Show'}>
                {showNew ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">
              Confirm New Password
            </label>
            <div className="relative">
              <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-mute pointer-events-none" />
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirmPass}
                onChange={inputEvent => setConfirmPass(inputEvent.target.value)}
                placeholder="Repeat new password"
                autoComplete="new-password"
                className="w-full bg-panel border border-border rounded-lg pl-10 pr-11 py-2.5 text-sm text-text placeholder:text-text-mute outline-none focus:border-teal focus:ring-2 focus:ring-teal/20 transition-colors"
              />
              <button type="button" onClick={() => setShowConfirm(previous => !previous)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-mute hover:text-text-mid transition-colors"
                aria-label={showConfirm ? 'Hide' : 'Show'}>
                {showConfirm ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <button
            type="submit"
            disabled={saving || !newPass || !confirmPass}
            className="w-full bg-navy hover:bg-navy-soft disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm mt-1"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saving ? 'Updating…' : 'Update Password'}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {leftPanel}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-canvas">
        {rightContent()}
      </div>
    </div>
  );
}
