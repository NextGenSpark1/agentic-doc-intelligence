import { useState } from 'react';
import { X, Loader2, CheckCircle2 } from 'lucide-react';

interface RequestAccessModalProps {
  onClose: () => void;
}

export function RequestAccessModal({ onClose }: RequestAccessModalProps) {
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

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md bg-[#1E293B] border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
        onClick={modalEvent => modalEvent.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/10">
          <div>
            <h2 className="text-white font-semibold text-base">Request access</h2>
            <p className="text-white/45 text-xs mt-0.5">We'll be in touch within 1–2 business days.</p>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white/70 transition-colors">
            <X size={18} />
          </button>
        </div>

        {submitted ? (
          <div className="px-6 py-10 flex flex-col items-center text-center gap-3">
            <CheckCircle2 size={36} className="text-teal" />
            <p className="text-white font-semibold text-base">Request sent</p>
            <p className="text-white/50 text-sm leading-relaxed max-w-xs">
              We've received your request and will reach out to{' '}
              <span className="text-white/70">{email}</span> shortly.
            </p>
            <button onClick={onClose} className="mt-4 text-sm text-white/50 hover:text-white transition-colors">
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
                  placeholder="Acme Ltd"
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
              <label className="text-white/50 text-[11px] font-semibold uppercase tracking-wider">
                Message{' '}
                <span className="normal-case font-normal text-white/30">(optional)</span>
              </label>
              <textarea
                rows={3}
                value={message}
                onChange={changeEvent => setMessage(changeEvent.target.value)}
                placeholder="Tell us about your tendering use case…"
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal/50 transition-colors resize-none"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center justify-center gap-2 bg-teal hover:bg-teal-soft disabled:opacity-60 text-white font-semibold text-sm py-3 rounded-xl transition-colors mt-1"
            >
              {submitting ? (
                <><Loader2 size={14} className="animate-spin" /> Sending…</>
              ) : (
                'Send request'
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
