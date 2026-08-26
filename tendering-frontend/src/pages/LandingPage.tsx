import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth, PLATFORM_ADMIN_EMAILS } from '../context/AuthContext';
import { FileText, CheckSquare, ThumbsUp, Library, MessageSquare, Users, ArrowRight, X, Loader2, CheckCircle2 } from 'lucide-react';

const FEATURES = [
  {
    icon: FileText,
    title: 'Requirements Extraction',
    description: 'Upload any RFP or tender document. AI reads every page and extracts all requirements — mandatory, technical, financial — each linked to its source clause.',
  },
  {
    icon: CheckSquare,
    title: 'Compliance Matrix',
    description: 'Instantly see which requirements you meet, partially meet, or gap. Assign owners, attach evidence, and track readiness at a glance across the whole bid.',
  },
  {
    icon: ThumbsUp,
    title: 'Bid Decision Engine',
    description: 'AI-powered go/no-go recommendation backed by your document library. Understand your strengths, risks, and gaps before committing your team.',
  },
  {
    icon: Library,
    title: 'Document Library',
    description: 'Centralised repository for certificates, registrations, financial statements, and technical docs — always ready to attach as evidence on any tender.',
  },
  {
    icon: MessageSquare,
    title: 'Evidence-Grounded Assistant',
    description: 'Ask questions about the tender in plain language. Responses are grounded in your uploaded documents and linked to specific source pages for verification.',
  },
  {
    icon: Users,
    title: 'Team Collaboration',
    description: 'Role-based access for org admins, supervisors, and team members. Everyone sees what they need — no more emailing documents back and forth.',
  },
];

const STEPS = [
  {
    number: '01',
    title: 'Upload the tender document',
    description: 'Drop in the RFP or invitation to tender. AI extracts every requirement automatically — no manual reading required.',
  },
  {
    number: '02',
    title: 'Build your bid',
    description: 'Track compliance against each requirement, assign owners, attach evidence from your document library, and close every gap.',
  },
  {
    number: '03',
    title: 'Decide with confidence',
    description: 'Review the AI bid recommendation, see your readiness score, and submit knowing exactly where you stand.',
  },
];

const DOC_TYPES = ['RFPs', 'ITTs', 'EOIs', 'Certificates', 'Financial Statements', 'Technical Proposals', 'Contracts'];

const CONTROLLED_ENV_ITEMS = [
  'Role-based access control',
  'Source-level traceability',
  'Audit logging',
  'Human review of bid decisions',
  'Secure document processing',
];

export function LandingPage() {
  const { user } = useAuth();
  const isPlatformAdmin = PLATFORM_ADMIN_EMAILS.includes(user?.email ?? '');
  const isAuthenticated = !!user;
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [name, setName] = useState('');
  const [organisation, setOrganisation] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');

  async function handleSubmit(submitEvent: React.FormEvent) {
    submitEvent.preventDefault();
    setSubmitting(true);
    try {
      await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/request-access`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, organisation, email, message, platform: 'tendering' }),
      });
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  }

  function closeModal() {
    setIsModalOpen(false);
    setSubmitted(false);
    setName('');
    setOrganisation('');
    setEmail('');
    setMessage('');
  }

  return (
    <div className="min-h-screen">

      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-navy-deep/95 backdrop-blur-sm border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 h-13 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img
              src="/NG logo.jpeg"
              alt="NextGen Spark"
              className="w-7 h-7 rounded-md object-contain bg-white p-0.5 shrink-0"
            />
            <span className="text-white font-semibold text-sm tracking-wide">Tendering Intelligence</span>
          </div>
          {isAuthenticated ? (
            <Link
              to={isPlatformAdmin ? '/admin' : '/dashboard'}
              className="inline-flex items-center gap-2 bg-teal hover:bg-teal-soft text-white font-semibold text-sm px-5 py-2 rounded-lg transition-colors"
            >
              Go to Dashboard <ArrowRight size={14} />
            </Link>
          ) : (
            <Link
              to="/login"
              className="inline-flex items-center gap-2 border border-white/25 hover:border-white/45 hover:bg-white/5 text-white font-semibold text-sm px-5 py-2 rounded-lg transition-colors"
            >
              Sign in
            </Link>
          )}
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────────────── */}
      <section className="relative pt-13 min-h-screen flex items-center bg-navy-deep overflow-hidden">
        {/* Line grid pattern */}
        <div className="absolute inset-0 opacity-[0.055] pointer-events-none select-none">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="hero-grid" x="0" y="0" width="72" height="72" patternUnits="userSpaceOnUse">
                <path d="M 72 0 L 0 0 0 72" fill="none" stroke="#1558D4" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#hero-grid)" />
          </svg>
        </div>

        {/* Soft glow */}
        <div
          className="absolute pointer-events-none"
          style={{
            top: '30%',
            left: '20%',
            width: '700px',
            height: '400px',
            background: 'radial-gradient(ellipse at center, rgba(21,88,212,0.13) 0%, transparent 70%)',
            transform: 'translate(-30%, -50%)',
          }}
        />

        <div className="relative max-w-7xl mx-auto px-6 py-28 w-full">
          <div className="max-w-3xl">
            {/* Badge */}
            <div className="inline-flex items-center gap-2.5 border border-teal/30 bg-teal/10 rounded-full px-4 py-1.5 mb-10">
              <div className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse" />
              <span className="text-teal text-[11px] font-bold uppercase tracking-widest">
                AI-Powered Bid Management
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-5xl sm:text-6xl lg:text-[4.5rem] font-semibold text-white leading-[1.07] tracking-tight mb-7">
              Bid smarter.<br />
              Win with{' '}
              <span className="text-teal">confidence.</span>
            </h1>

            {/* Subheadline */}
            <p className="text-lg sm:text-xl text-white/55 leading-relaxed mb-10 max-w-2xl">
              AI-extracted requirements, compliance tracking, and evidence-backed bid decisions —
              everything your team needs to win tenders in one place.
            </p>

            {/* CTAs */}
            <div className="flex items-center gap-4 flex-wrap">
              {isAuthenticated ? (
                <Link
                  to={isPlatformAdmin ? '/admin' : '/dashboard'}
                  className="inline-flex items-center gap-2 bg-teal hover:bg-teal-soft text-white font-semibold px-8 py-3.5 rounded-xl text-sm transition-colors"
                  style={{ boxShadow: '0 8px 32px rgba(21,88,212,0.30)' }}
                >
                  Go to Dashboard <ArrowRight size={16} />
                </Link>
              ) : (
                <>
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-2 bg-teal hover:bg-teal-soft text-white font-semibold px-8 py-3.5 rounded-xl text-sm transition-colors"
                    style={{ boxShadow: '0 8px 32px rgba(21,88,212,0.30)' }}
                  >
                    Sign in <ArrowRight size={16} />
                  </Link>
                  <button
                    onClick={() => setIsModalOpen(true)}
                    className="inline-flex items-center gap-2 border border-white/25 hover:border-white/45 hover:bg-white/5 text-white/80 hover:text-white font-medium px-8 py-3.5 rounded-xl text-sm transition-colors"
                  >
                    Request access
                  </button>
                </>
              )}
            </div>

            {/* Document types strip */}
            <div className="mt-16 pt-8 border-t border-white/10 flex flex-wrap items-center gap-x-5 gap-y-2">
              <span className="text-white/30 text-[10px] font-bold uppercase tracking-widest shrink-0">
                Supports
              </span>
              {DOC_TYPES.map((type, index) => (
                <span key={type} className="flex items-center gap-5">
                  <span className="text-white/45 text-sm">{type}</span>
                  {index < DOC_TYPES.length - 1 && (
                    <span className="text-white/15 text-xs">·</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ───────────────────────────────────────────────────────── */}
      <section className="bg-canvas py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-14">
            <p className="text-[11px] font-bold uppercase tracking-widest text-teal mb-3">
              Capabilities
            </p>
            <h2 className="text-3xl sm:text-4xl font-semibold text-text leading-snug mb-4">
              Every tool your bid team needs
            </h2>
            <p className="text-text-mute text-base leading-relaxed max-w-lg">
              Built for procurement teams who need to move fast and bid with evidence — not guesswork.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <div
                key={title}
                className="bg-panel border border-border rounded-2xl p-6 hover:border-border-strong hover:shadow-md transition-all group"
              >
                <div className="w-10 h-10 bg-teal/10 border border-teal/15 rounded-xl flex items-center justify-center mb-5 group-hover:bg-teal/15 transition-colors">
                  <Icon size={18} className="text-teal" />
                </div>
                <h3 className="text-text font-semibold mb-2 text-[15px]">{title}</h3>
                <p className="text-sm text-text-mute leading-relaxed">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ───────────────────────────────────────────────────── */}
      <section className="bg-canvas-deep border-t border-border py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-14">
            <p className="text-[11px] font-bold uppercase tracking-widest text-teal mb-3">
              How it works
            </p>
            <h2 className="text-3xl sm:text-4xl font-semibold text-text leading-snug">
              From tender to submission
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
            {STEPS.map(({ number, title, description }, index) => (
              <div key={number} className="flex gap-5">
                <div className="shrink-0 flex flex-col items-center">
                  <span className="font-mono text-4xl font-bold text-teal/20 leading-none">
                    {number}
                  </span>
                  {index < STEPS.length - 1 && (
                    <div className="hidden md:block w-px flex-1 mt-3 bg-gradient-to-b from-border to-transparent" />
                  )}
                </div>
                <div className="pt-1">
                  <h3 className="text-text font-semibold mb-2">{title}</h3>
                  <p className="text-sm text-text-mute leading-relaxed">{description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Controlled environments ────────────────────────────────────────── */}
      <section className="bg-canvas border-t border-border py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="max-w-3xl mx-auto text-center mb-12">
            <p className="text-[11px] font-bold uppercase tracking-widest text-teal mb-3">
              Built for institutions
            </p>
            <h2 className="text-3xl sm:text-4xl font-semibold text-text leading-snug">
              Designed for controlled bid environments
            </h2>
          </div>
          <div className="flex flex-wrap justify-center gap-4">
            {CONTROLLED_ENV_ITEMS.map((item) => (
              <div
                key={item}
                className="flex items-center gap-3 bg-panel border border-border rounded-xl px-5 py-3.5"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-teal shrink-0" />
                <span className="text-text-mid text-sm font-medium">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ──────────────────────────────────────────────────────── */}
      <section className="bg-navy-deep py-28 relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.04] pointer-events-none select-none">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="cta-grid" x="0" y="0" width="48" height="48" patternUnits="userSpaceOnUse">
                <rect x="0" y="0" width="24" height="24" fill="#1558D4" />
                <rect x="24" y="24" width="24" height="24" fill="#1558D4" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#cta-grid)" />
          </svg>
        </div>
        <div className="relative max-w-7xl mx-auto px-6 text-center">
          <div className="w-14 h-1 bg-teal rounded-full mx-auto mb-8" />
          <h2 className="text-4xl sm:text-5xl font-semibold text-white mb-5 leading-snug">
            Ready to win more tenders?
          </h2>
          <p className="text-white/45 text-lg mb-10 max-w-md mx-auto leading-relaxed">
            Sign in to your workspace and start turning tender documents into winning bids.
          </p>
          <Link
            to={isAuthenticated ? (isPlatformAdmin ? '/admin' : '/dashboard') : '/login'}
            className="inline-flex items-center gap-2 bg-teal hover:bg-teal-soft text-white font-semibold px-10 py-4 rounded-xl text-sm transition-colors"
            style={{ boxShadow: '0 12px 40px rgba(21,88,212,0.35)' }}
          >
            {isAuthenticated ? 'Go to Dashboard' : 'Sign in to your workspace'} <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="bg-navy-deep border-t border-white/10 py-7">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <img
              src="/NG logo.jpeg"
              alt="NextGen Spark"
              className="w-6 h-6 rounded object-contain bg-white p-0.5 shrink-0"
            />
            <span className="text-white/35 text-xs">
              &copy; {new Date().getFullYear()} NextGen Spark. All rights reserved.
            </span>
          </div>
          <span className="text-white/20 text-xs">Tendering Intelligence</span>
        </div>
      </footer>

      {/* ── Request access modal ───────────────────────────────────────────── */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={closeModal}>
          <div
            className="relative w-full max-w-md bg-[#1E293B] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
            onClick={modalEvent => modalEvent.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-white/10">
              <div>
                <h2 className="text-white font-semibold text-base">Request access</h2>
                <p className="text-white/45 text-xs mt-0.5">We'll be in touch within 1–2 business days.</p>
              </div>
              <button onClick={closeModal} className="text-white/40 hover:text-white/70 transition-colors">
                <X size={18} />
              </button>
            </div>

            {submitted ? (
              <div className="px-6 py-10 flex flex-col items-center text-center gap-3">
                <CheckCircle2 size={36} className="text-teal" />
                <p className="text-white font-semibold text-base">Request sent</p>
                <p className="text-white/50 text-sm leading-relaxed max-w-xs">
                  We've received your request and will reach out to <span className="text-white/70">{email}</span> shortly.
                </p>
                <button onClick={closeModal} className="mt-4 text-sm text-white/50 hover:text-white transition-colors">
                  Close
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="px-6 py-5 flex flex-col gap-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-white/50 text-[11px] font-semibold uppercase tracking-wider">Full name</label>
                    <input
                      required
                      value={name}
                      onChange={changeEvent => setName(changeEvent.target.value)}
                      placeholder="Jane Smith"
                      className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 focus:bg-white/8 transition-colors"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-white/50 text-[11px] font-semibold uppercase tracking-wider">Organisation</label>
                    <input
                      required
                      value={organisation}
                      onChange={changeEvent => setOrganisation(changeEvent.target.value)}
                      placeholder="Acme Ltd"
                      className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 focus:bg-white/8 transition-colors"
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-white/50 text-[11px] font-semibold uppercase tracking-wider">Work email</label>
                  <input
                    required
                    type="email"
                    value={email}
                    onChange={changeEvent => setEmail(changeEvent.target.value)}
                    placeholder="jane@example.com"
                    className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 focus:bg-white/8 transition-colors"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-white/50 text-[11px] font-semibold uppercase tracking-wider">Message <span className="normal-case font-normal text-white/30">(optional)</span></label>
                  <textarea
                    rows={3}
                    value={message}
                    onChange={changeEvent => setMessage(changeEvent.target.value)}
                    placeholder="Tell us about your tendering use case…"
                    className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 focus:bg-white/8 transition-colors resize-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center justify-center gap-2 bg-teal hover:bg-teal-soft disabled:opacity-60 text-white font-semibold text-sm py-3 rounded-xl transition-colors mt-1"
                >
                  {submitting ? <><Loader2 size={14} className="animate-spin" /> Sending…</> : 'Send request'}
                </button>
              </form>
            )}
          </div>
        </div>
      )}

    </div>
  );
}
