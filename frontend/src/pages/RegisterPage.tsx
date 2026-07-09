import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Mail, Lock, Eye, EyeOff, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

export default function RegisterPage() {
  const { signUp, signInWithGoogle } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setLoading(true)
    try {
      await signUp(email, password)
      setDone(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogle() {
    setGoogleLoading(true)
    try {
      await signInWithGoogle()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Google sign-in failed.')
      setGoogleLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">

      {/* ── Left decorative panel ── */}
      <div className="hidden lg:flex lg:w-[45%] bg-navy-deep flex-col justify-between p-12 relative overflow-hidden select-none">
        <div className="absolute inset-0 opacity-[0.06] pointer-events-none">
          <svg width="100%" height="100%">
            <defs>
              <pattern id="auth-grid" x="0" y="0" width="48" height="48" patternUnits="userSpaceOnUse">
                <rect x="0" y="0" width="24" height="24" fill="#0E7C86" />
                <rect x="24" y="24" width="24" height="24" fill="#0E7C86" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#auth-grid)" />
          </svg>
        </div>

        <div className="relative z-10 flex items-center gap-3">
          <img src="/NG logo.jpeg" alt="NextGen Spark" className="w-9 h-9 rounded-lg object-contain bg-white p-0.5 shrink-0" />
          <span className="text-white font-semibold tracking-wide text-sm">NextGen Spark</span>
        </div>

        <div className="relative z-10">
          <div className="w-14 h-1 bg-teal rounded-full mb-8" />
          <h2 className="text-white text-3xl font-semibold leading-snug mb-4">
            Built for teams<br />
            that need <span className="text-teal">answers</span>,<br />
            not just data.
          </h2>
          <p className="text-white/50 text-sm leading-relaxed max-w-xs">
            Join forensic investigators using LLM-driven pipelines to surface signals across large document corpora.
          </p>
        </div>

        <p className="relative z-10 text-white/25 text-xs">
          &copy; {new Date().getFullYear()} NextGen Spark
        </p>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-canvas">
        <div className="w-full max-w-md">

          {/* Mobile brand */}
          <div className="lg:hidden flex justify-center mb-8">
            <img src="/NG logo with text.jpeg" alt="NextGen Spark" className="h-10 object-contain" />
          </div>

          {done ? (
            /* ── Verification notice ── */
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-teal/10 mb-5">
                <CheckCircle2 size={28} className="text-teal" />
              </div>
              <h1 className="text-2xl font-semibold text-text mb-2">Check your email</h1>
              <p className="text-sm text-text-mute mb-6 max-w-xs mx-auto leading-relaxed">
                We sent a verification link to <span className="text-text font-medium">{email}</span>.
                Click the link to activate your account, then sign in.
              </p>
              <button
                onClick={() => navigate('/login', { replace: true })}
                className="inline-flex items-center gap-2 bg-navy hover:bg-navy-soft text-white font-semibold py-2.5 px-6 rounded-lg text-sm transition-colors"
              >
                Go to sign in
              </button>
            </div>
          ) : (
            <>
              <div className="mb-8">
                <h1 className="text-2xl font-semibold text-text mb-1">Create an account</h1>
                <p className="text-sm text-text-mute">Get started with NextGen Spark</p>
              </div>

              {error && (
                <div className="mb-5 flex items-start gap-2.5 bg-red-bg border border-red/20 text-red text-sm px-4 py-3 rounded-lg">
                  <AlertCircle size={15} className="shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>

                {/* Email */}
                <div>
                  <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">
                    Email address
                  </label>
                  <div className="relative">
                    <Mail size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-mute pointer-events-none" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                      autoComplete="email"
                      className="w-full bg-panel border border-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-text placeholder:text-text-mute outline-none focus:border-teal focus:ring-2 focus:ring-teal/20 transition-colors"
                    />
                  </div>
                </div>

                {/* Password */}
                <div>
                  <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-mute pointer-events-none" />
                    <input
                      type={showPass ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="At least 8 characters"
                      required
                      autoComplete="new-password"
                      className="w-full bg-panel border border-border rounded-lg pl-10 pr-11 py-2.5 text-sm text-text placeholder:text-text-mute outline-none focus:border-teal focus:ring-2 focus:ring-teal/20 transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPass((p) => !p)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-mute hover:text-text-mid transition-colors"
                      aria-label={showPass ? 'Hide password' : 'Show password'}
                    >
                      {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                {/* Confirm password */}
                <div>
                  <label className="block text-xs font-semibold text-text-mute uppercase tracking-wider mb-1.5">
                    Confirm password
                  </label>
                  <div className="relative">
                    <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-mute pointer-events-none" />
                    <input
                      type={showConfirm ? 'text' : 'password'}
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      placeholder="Repeat your password"
                      required
                      autoComplete="new-password"
                      className="w-full bg-panel border border-border rounded-lg pl-10 pr-11 py-2.5 text-sm text-text placeholder:text-text-mute outline-none focus:border-teal focus:ring-2 focus:ring-teal/20 transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((p) => !p)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-mute hover:text-text-mid transition-colors"
                      aria-label={showConfirm ? 'Hide password' : 'Show password'}
                    >
                      {showConfirm ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                {/* Submit */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-navy hover:bg-navy-soft disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm mt-1"
                >
                  {loading && <Loader2 size={14} className="animate-spin" />}
                  {loading ? 'Creating account…' : 'Create Account'}
                </button>

                {/* Divider */}
                <div className="relative my-1">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-canvas px-3 text-xs text-text-mute uppercase tracking-wider">or</span>
                  </div>
                </div>

                {/* Google */}
                <button
                  type="button"
                  onClick={handleGoogle}
                  disabled={googleLoading}
                  className="w-full flex items-center justify-center gap-3 bg-panel border border-border hover:border-border-strong hover:bg-panel-2 text-text-mid font-medium py-2.5 rounded-lg text-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {googleLoading ? (
                    <Loader2 size={15} className="animate-spin text-text-mute" />
                  ) : (
                    <svg viewBox="0 0 24 24" className="w-4 h-4 shrink-0">
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                  )}
                  {googleLoading ? 'Redirecting…' : 'Continue with Google'}
                </button>

              </form>

              <p className="text-center text-sm text-text-mute mt-8">
                Already have an account?{' '}
                <Link to="/login" className="text-teal hover:text-teal-soft font-medium transition-colors">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
