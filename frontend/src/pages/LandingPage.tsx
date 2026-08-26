import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { FileText, Network, Clock, Search, MessageSquare, Shield, ArrowRight, X, Loader2, CheckCircle2 } from 'lucide-react'

const FEATURES = [
  {
    icon: FileText,
    title: 'Intelligent Extraction',
    description: 'AI reads contracts, bank statements, emails, and scanned documents — extracting entities, amounts, dates, and relationships with full source citations.',
  },
  {
    icon: Network,
    title: 'Entity Resolution',
    description: 'Surfaces connections across documents: shared accounts, company networks, recurring individuals, and cross-document references your team would never spot manually.',
  },
  {
    icon: Clock,
    title: 'Timeline Reconstruction',
    description: 'Events from across your case files assembled into a chronological timeline, each entry traced to its source document and page number.',
  },
  {
    icon: Search,
    title: 'Anomaly Detection',
    description: 'Identifies potential anomalies across documents, transactions and records for investigator review.',
  },
  {
    icon: MessageSquare,
    title: 'Evidence-Grounded Assistant',
    description: 'Ask questions in plain language. Responses are grounded in case documents and linked to specific source pages for verification.',
  },
  {
    icon: Shield,
    title: 'Full Audit Trail',
    description: 'Every extraction, inference, and AI decision is logged. Complete audit trail from source document to extracted evidence and investigator finding.',
  },
]

const STEPS = [
  {
    number: '01',
    title: 'Upload your case files',
    description: 'Drop in any document type — PDFs, scanned images, spreadsheets, or email exports. The platform handles the rest.',
  },
  {
    number: '02',
    title: 'AI extracts and connects',
    description: 'The pipeline resolves entities, reconstructs timelines, detects anomalies, and surfaces findings across your entire document set.',
  },
  {
    number: '03',
    title: 'Investigate with intelligence',
    description: 'Query your case, explore the entity graph, review findings, and export a traceable report — all from one workspace.',
  },
]

const DOC_TYPES = ['Contracts', 'Bank Statements', 'Emails', 'Invoices', 'Scanned PDFs', 'Spreadsheets', 'Court Filings']

export default function LandingPage() {
  const { user } = useAuth()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [name, setName] = useState('')
  const [organisation, setOrganisation] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')

  async function handleSubmit(submitEvent: React.FormEvent) {
    submitEvent.preventDefault()
    setSubmitting(true)
    try {
      await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/request-access`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, organisation, email, message, platform: 'adi' }),
      })
      setSubmitted(true)
    } finally {
      setSubmitting(false)
    }
  }

  function closeModal() {
    setIsModalOpen(false)
    setSubmitted(false)
    setName('')
    setOrganisation('')
    setEmail('')
    setMessage('')
  }

  return (
    <div className="min-h-screen">

      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-navy-deep/95 backdrop-blur-sm border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img
              src="/NG logo.jpeg"
              alt="NextGen Spark"
              className="w-8 h-8 rounded-md object-contain bg-white p-0.5 shrink-0"
            />
            <span className="text-white font-semibold text-sm tracking-wide">NextGen Spark</span>
            <span className="hidden sm:block text-white/20 mx-1 text-lg font-thin">|</span>
            <span className="hidden sm:block text-white/45 text-sm">Investigation Intelligence</span>
          </div>
          {user ? (
            <Link
              to="/cases"
              className="inline-flex items-center gap-2 bg-teal hover:bg-teal-soft text-white font-semibold text-sm px-5 py-2 rounded-lg transition-colors"
            >
              Go to Cases <ArrowRight size={14} />
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
      <section className="relative pt-14 min-h-screen flex items-center bg-navy-deep overflow-hidden">
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

        {/* Soft glow behind headline */}
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
                Investigation Document Intelligence
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-5xl sm:text-6xl lg:text-[4.5rem] font-semibold text-white leading-[1.07] tracking-tight mb-7">
              Turn case files<br />
              into{' '}
              <span className="text-teal">traceable</span>
              <br />
              intelligence.
            </h1>

            {/* Subheadline */}
            <p className="text-lg sm:text-xl text-white/55 leading-relaxed mb-10 max-w-2xl">
              Analyse complex case documents to extract entities, reconstruct timelines,
              identify anomalies and surface findings — with every insight traceable to its original source.
            </p>

            {/* CTAs */}
            <div className="flex items-center gap-4 flex-wrap">
              {user ? (
                <Link
                  to="/cases"
                  className="inline-flex items-center gap-2 bg-teal hover:bg-teal-soft text-white font-semibold px-8 py-3.5 rounded-xl text-sm transition-colors"
                  style={{ boxShadow: '0 8px 32px rgba(21,88,212,0.30)' }}
                >
                  Go to your cases <ArrowRight size={16} />
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
              Every tool your investigation needs
            </h2>
            <p className="text-text-mute text-base leading-relaxed max-w-lg">
              Built for forensic investigators who need answers they can defend — not just answers.
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
              From documents to decisions
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
              Designed for controlled investigation environments
            </h2>
          </div>
          <div className="flex flex-wrap justify-center gap-4">
            {[
              'Role-based access',
              'Source-level traceability',
              'Audit logging',
              'Human review of findings',
              'Secure document processing',
            ].map((item) => (
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
            Ready to investigate smarter?
          </h2>
          <p className="text-white/45 text-lg mb-10 max-w-md mx-auto leading-relaxed">
            Sign in to your workspace and start turning documents into intelligence.
          </p>
          <Link
            to={user ? '/cases' : '/login'}
            className="inline-flex items-center gap-2 bg-teal hover:bg-teal-soft text-white font-semibold px-10 py-4 rounded-xl text-sm transition-colors"
            style={{ boxShadow: '0 12px 40px rgba(21,88,212,0.35)' }}
          >
            {user ? 'Go to Cases' : 'Sign in to your workspace'} <ArrowRight size={16} />
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
          <span className="text-white/20 text-xs">Investigation Intelligence</span>
        </div>
      </footer>

      {/* ── Request access modal ───────────────────────────────────────────── */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={closeModal}>
          <div
            className="relative w-full max-w-md bg-[#1E293B] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
            onClick={modalEvent => modalEvent.stopPropagation()}
          >
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
                      className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 transition-colors"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-white/50 text-[11px] font-semibold uppercase tracking-wider">Organisation</label>
                    <input
                      required
                      value={organisation}
                      onChange={changeEvent => setOrganisation(changeEvent.target.value)}
                      placeholder="Acme Forensics"
                      className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 transition-colors"
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
                    className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 transition-colors"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-white/50 text-[11px] font-semibold uppercase tracking-wider">Message <span className="normal-case font-normal text-white/30">(optional)</span></label>
                  <textarea
                    rows={3}
                    value={message}
                    onChange={changeEvent => setMessage(changeEvent.target.value)}
                    placeholder="Tell us about your use case…"
                    className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 transition-colors resize-none"
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
  )
}
