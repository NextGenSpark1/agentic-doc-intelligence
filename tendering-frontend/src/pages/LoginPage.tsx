import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Loader2, LogIn } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const { session } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (session) return <Navigate to="/" replace />;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    const { error: err } = await supabase.auth.signInWithPassword({ email, password });
    if (err) setError(err.message);
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Logo + title */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center gap-3 mb-4">
            <img
              src="/NG logo.jpeg"
              alt="NextGen Spark"
              className="w-10 h-10 rounded-lg object-contain bg-white p-1"
            />
            <div>
              <p className="text-base font-bold text-text leading-none">Tendering Intelligence</p>
              <p className="text-xs text-text-mute mt-0.5">NextGen Spark</p>
            </div>
          </div>
          <h1 className="text-sm text-text-mute">Sign in to your account</h1>
        </div>

        {/* Card */}
        <div className="bg-panel border border-border rounded-xl shadow-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
                className="w-full px-3 py-2.5 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="w-full px-3 py-2.5 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
              />
            </div>

            {error && (
              <p className="text-xs text-red bg-red-bg border border-red/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-navy hover:bg-navy-soft disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {loading ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <LogIn size={15} />
              )}
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-text-mute mt-6">
          Contact your administrator to request access.
        </p>
      </div>
    </div>
  );
}
