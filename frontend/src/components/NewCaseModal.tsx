import { useState, useEffect, useCallback } from 'react'
import { createCase } from '../api'
import type { CreateCasePayload } from '../types'

interface NewCaseModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

const CASE_TYPES = [
  { value: 'procurement_fraud', label: 'Procurement Fraud' },
  { value: 'payment_tracing', label: 'Payment Tracing' },
  { value: 'conflict_of_interest', label: 'Conflict of Interest' },
  { value: 'audit', label: 'Audit' },
]

interface FormErrors {
  title?: string
  lead_investigator?: string
  case_type?: string
  allegation_summary?: string
}

export default function NewCaseModal({ open, onClose, onSuccess }: NewCaseModalProps) {
  const [form, setForm] = useState<CreateCasePayload>({
    title: '',
    lead_investigator: '',
    case_type: '',
    allegation_summary: '',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [loading, setLoading] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const handleClose = useCallback(() => {
    setForm({ title: '', lead_investigator: '', case_type: '', allegation_summary: '' })
    setErrors({})
    setSubmitError(null)
    setLoading(false)
    onClose()
  }, [onClose])

  // ESC key closes modal
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, handleClose])

  function validate(): boolean {
    const newErrors: FormErrors = {}
    if (!form.title.trim()) newErrors.title = 'Case title is required.'
    if (!form.lead_investigator.trim()) newErrors.lead_investigator = 'Lead investigator is required.'
    if (!form.case_type) newErrors.case_type = 'Case type is required.'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    setSubmitError(null)
    try {
      await createCase(form)
      handleClose()
      onSuccess()
    } catch {
      setSubmitError('Failed to create case. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={handleClose}
    >
      {/* Modal panel */}
      <div
        className="
          bg-panel rounded-xl shadow-xl border border-border w-full max-w-lg mx-4
          animate-slide-in
        "
        style={{ animation: 'slideIn 0.2s ease-out' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-base font-semibold text-text">New Case</h2>
          <button
            onClick={handleClose}
            className="text-text-mute hover:text-text transition-colors duration-150 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 flex flex-col gap-4">
          {submitError && (
            <div className="bg-red-bg text-red text-sm px-3 py-2 rounded border border-red/20">
              {submitError}
            </div>
          )}

          {/* Case Title */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-text-mid">
              Case Title <span className="text-red">*</span>
            </label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g. Supplier Payment Irregularities Q3"
              className={`
                w-full border rounded-md px-3 py-2 text-sm text-text bg-panel
                focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal
                transition-colors duration-150 placeholder:text-text-mute
                ${errors.title ? 'border-red' : 'border-border-strong'}
              `}
            />
            {errors.title && <span className="text-xs text-red">{errors.title}</span>}
          </div>

          {/* Lead Investigator */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-text-mid">
              Lead Investigator <span className="text-red">*</span>
            </label>
            <input
              type="text"
              value={form.lead_investigator}
              onChange={(e) => setForm({ ...form, lead_investigator: e.target.value })}
              placeholder="e.g. Sarah Chen"
              className={`
                w-full border rounded-md px-3 py-2 text-sm text-text bg-panel
                focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal
                transition-colors duration-150 placeholder:text-text-mute
                ${errors.lead_investigator ? 'border-red' : 'border-border-strong'}
              `}
            />
            {errors.lead_investigator && (
              <span className="text-xs text-red">{errors.lead_investigator}</span>
            )}
          </div>

          {/* Case Type */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-text-mid">Case Type</label>
            <select
              value={form.case_type}
              onChange={(e) => setForm({ ...form, case_type: e.target.value })}
              className={`
                w-full border rounded-md px-3 py-2 text-sm text-text bg-panel
                focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal
                transition-colors duration-150
                ${errors.case_type ? 'border-red' : 'border-border-strong'}
              `}
            >
              <option value="">Select type...</option>
              {CASE_TYPES.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            {errors.case_type && <span className="text-xs text-red">{errors.case_type}</span>}
          </div>

          {/* Allegation Summary */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-text-mid">Allegation Summary</label>
            <textarea
              value={form.allegation_summary}
              onChange={(e) => setForm({ ...form, allegation_summary: e.target.value })}
              rows={3}
              placeholder="Brief description of the allegation or investigation scope..."
              className={`
                w-full border rounded-md px-3 py-2 text-sm text-text bg-panel resize-none
                focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal
                transition-colors duration-150 placeholder:text-text-mute
                ${errors.allegation_summary ? 'border-red' : 'border-border-strong'}
              `}
            />
            {errors.allegation_summary && (
              <span className="text-xs text-red">{errors.allegation_summary}</span>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-text-mid border border-border rounded-lg hover:border-border-strong hover:text-text transition-colors duration-150"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="
                px-4 py-2 text-sm font-medium text-white bg-navy rounded-lg
                hover:bg-navy-soft disabled:opacity-60 disabled:cursor-not-allowed
                transition-colors duration-150 flex items-center gap-2
              "
            >
              {loading && (
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              {loading ? 'Creating...' : 'Create Case'}
            </button>
          </div>
        </form>
      </div>

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-12px) scale(0.98); }
          to   { opacity: 1; transform: translateY(0)   scale(1); }
        }
      `}</style>
    </div>
  )
}
