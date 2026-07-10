import { useState, useEffect, useCallback } from 'react'
import { createCase } from '../api'
import type { CreateCasePayload, SchemaField } from '../types'
import { CASE_TYPE_OPTIONS, PRESET_SCHEMAS } from '../lib/schemaPresets'

interface NewCaseModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

interface FormErrors {
  title?: string
  lead_investigator?: string
  case_type?: string
}

interface DraftField {
  name: string
  description: string
  is_array: boolean
}

export default function NewCaseModal({ open, onClose, onSuccess }: NewCaseModalProps) {
  const [step, setStep] = useState<1 | 2>(1)
  const [form, setForm] = useState<Omit<CreateCasePayload, 'schema_fields'>>({
    title: '',
    lead_investigator: '',
    case_type: '',
    allegation_summary: '',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [loading, setLoading] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Schema step state
  const [fromScratch, setFromScratch] = useState(false)
  const [customFields, setCustomFields] = useState<SchemaField[]>([])
  const [draft, setDraft] = useState<DraftField>({ name: '', description: '', is_array: false })
  const [draftError, setDraftError] = useState<string | null>(null)

  const handleClose = useCallback(() => {
    setStep(1)
    setForm({ title: '', lead_investigator: '', case_type: '', allegation_summary: '' })
    setErrors({})
    setSubmitError(null)
    setLoading(false)
    setFromScratch(false)
    setCustomFields([])
    setDraft({ name: '', description: '', is_array: false })
    setDraftError(null)
    onClose()
  }, [onClose])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, handleClose])

  // Reset custom fields when case type changes
  useEffect(() => {
    setCustomFields([])
    setDraft({ name: '', description: '', is_array: false })
    setDraftError(null)
  }, [form.case_type])

  function validateStep1(): boolean {
    const newErrors: FormErrors = {}
    if (!form.title.trim()) newErrors.title = 'Case title is required.'
    if (!form.lead_investigator.trim()) newErrors.lead_investigator = 'Lead investigator is required.'
    if (!form.case_type) newErrors.case_type = 'Case type is required.'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  function handleNext() {
    if (!validateStep1()) return
    setStep(2)
  }

  function presetFields(): SchemaField[] {
    return PRESET_SCHEMAS[form.case_type]?.fields ?? []
  }

  function computedSchemaFields(): SchemaField[] {
    if (fromScratch) return customFields
    return [...presetFields(), ...customFields]
  }

  function addCustomField() {
    const name = draft.name.trim()
    const description = draft.description.trim()
    if (!name) { setDraftError('Field name is required.'); return }
    if (!description) { setDraftError('Description is required.'); return }
    const allNames = [...presetFields().map(f => f.name), ...customFields.map(f => f.name)]
    if (allNames.includes(name)) { setDraftError('A field with that name already exists.'); return }
    setCustomFields(prev => [...prev, { name, description, is_array: draft.is_array, custom: true }])
    setDraft({ name: '', description: '', is_array: false })
    setDraftError(null)
  }

  function removeCustomField(name: string) {
    setCustomFields(prev => prev.filter(f => f.name !== name))
  }

  async function handleSubmit() {
    setLoading(true)
    setSubmitError(null)
    try {
      await createCase({ ...form, schema_fields: computedSchemaFields() })
      handleClose()
      onSuccess()
    } catch {
      setSubmitError('Failed to create case. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  const preset = presetFields()
  const isWide = step === 2

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={handleClose}
    >
      <div
        className="bg-panel rounded-xl shadow-xl border border-border w-full mx-4"
        style={{
          maxWidth: isWide ? '640px' : '512px',
          transition: 'max-width 0.2s ease',
          animation: 'slideIn 0.2s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="text-base font-semibold text-text">New Case</h2>
            <p className="text-xs text-text-mute mt-0.5">Step {step} of 2 — {step === 1 ? 'Case Details' : 'Extraction Schema'}</p>
          </div>
          <button
            onClick={handleClose}
            className="text-text-mute hover:text-text transition-colors duration-150 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Step 1: Case Details */}
        {step === 1 && (
          <div className="px-6 py-5 flex flex-col gap-4">
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
                className={`w-full border rounded-md px-3 py-2 text-sm text-text bg-panel focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150 placeholder:text-text-mute ${errors.title ? 'border-red' : 'border-border-strong'}`}
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
                className={`w-full border rounded-md px-3 py-2 text-sm text-text bg-panel focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150 placeholder:text-text-mute ${errors.lead_investigator ? 'border-red' : 'border-border-strong'}`}
              />
              {errors.lead_investigator && (
                <span className="text-xs text-red">{errors.lead_investigator}</span>
              )}
            </div>

            {/* Case Type */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-text-mid">
                Case Type <span className="text-red">*</span>
              </label>
              <select
                value={form.case_type}
                onChange={(e) => setForm({ ...form, case_type: e.target.value })}
                className={`w-full border rounded-md px-3 py-2 text-sm text-text bg-panel focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150 ${errors.case_type ? 'border-red' : 'border-border-strong'}`}
              >
                <option value="">Select type...</option>
                {CASE_TYPE_OPTIONS.map(({ value, label }) => (
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
                className="w-full border border-border-strong rounded-md px-3 py-2 text-sm text-text bg-panel resize-none focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal transition-colors duration-150 placeholder:text-text-mute"
              />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 pt-1">
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-text-mid border border-border rounded-lg hover:border-border-strong hover:text-text transition-colors duration-150"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleNext}
                className="px-4 py-2 text-sm font-medium text-white bg-navy rounded-lg hover:bg-navy-soft transition-colors duration-150"
              >
                Next →
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Extraction Schema */}
        {step === 2 && (
          <div className="px-6 py-5 flex flex-col gap-4">
            {submitError && (
              <div className="bg-red-bg text-red text-sm px-3 py-2 rounded border border-red/20">
                {submitError}
              </div>
            )}

            {/* From-scratch toggle */}
            <div className="flex items-center justify-between">
              <p className="text-sm text-text-mute">
                {fromScratch
                  ? 'Define your own extraction fields.'
                  : `Using the ${PRESET_SCHEMAS[form.case_type]?.label ?? 'default'} preset.`}
              </p>
              <button
                type="button"
                onClick={() => { setFromScratch(v => !v); setCustomFields([]); setDraftError(null) }}
                className="text-xs text-teal hover:underline whitespace-nowrap ml-3"
              >
                {fromScratch ? '← Use preset' : 'Build from scratch'}
              </button>
            </div>

            {/* Preset fields (read-only, hidden in from-scratch mode) */}
            {!fromScratch && preset.length > 0 && (
              <div className="border border-border rounded-lg overflow-hidden">
                <div className="px-3 py-2 bg-bg-subtle border-b border-border">
                  <span className="text-xs font-medium text-text-mute uppercase tracking-wide">Preset Fields</span>
                </div>
                <div className="divide-y divide-border max-h-44 overflow-y-auto">
                  {preset.map(f => (
                    <div key={f.name} className="px-3 py-2 flex items-start gap-2">
                      <span className="text-xs font-mono font-semibold text-text mt-0.5 min-w-[110px]">{f.name}</span>
                      <span className="text-xs text-text-mid flex-1">{f.description}</span>
                      {f.is_array && (
                        <span className="text-[10px] text-text-mute bg-bg-subtle border border-border rounded px-1 shrink-0">list</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Custom fields added so far */}
            {customFields.length > 0 && (
              <div className="border border-border rounded-lg overflow-hidden">
                <div className="px-3 py-2 bg-bg-subtle border-b border-border">
                  <span className="text-xs font-medium text-text-mute uppercase tracking-wide">
                    Custom Fields ({customFields.length})
                  </span>
                </div>
                <div className="divide-y divide-border max-h-32 overflow-y-auto">
                  {customFields.map(f => (
                    <div key={f.name} className="px-3 py-2 flex items-start gap-2">
                      <span className="text-xs font-mono font-semibold text-text mt-0.5 min-w-[110px]">{f.name}</span>
                      <span className="text-xs text-text-mid flex-1">{f.description}</span>
                      {f.is_array && (
                        <span className="text-[10px] text-text-mute bg-bg-subtle border border-border rounded px-1 shrink-0">list</span>
                      )}
                      <button
                        type="button"
                        onClick={() => removeCustomField(f.name)}
                        className="text-text-mute hover:text-red text-sm leading-none shrink-0 ml-1"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Add custom field form */}
            <div className="border border-border-strong rounded-lg p-3 flex flex-col gap-2">
                <span className="text-xs font-medium text-text-mute uppercase tracking-wide">Add Field</span>
                {draftError && <p className="text-xs text-red">{draftError}</p>}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={draft.name}
                    onChange={(e) => setDraft(d => ({ ...d, name: e.target.value.toLowerCase().replace(/\s+/g, '_') }))}
                    placeholder="field_name"
                    className="flex-1 border border-border-strong rounded px-2 py-1.5 text-xs font-mono text-text bg-panel focus:outline-none focus:ring-1 focus:ring-teal/40 placeholder:text-text-mute"
                  />
                  <label className="flex items-center gap-1 text-xs text-text-mid whitespace-nowrap cursor-pointer">
                    <input
                      type="checkbox"
                      checked={draft.is_array}
                      onChange={(e) => setDraft(d => ({ ...d, is_array: e.target.checked }))}
                      className="accent-teal"
                    />
                    list
                  </label>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={draft.description}
                    onChange={(e) => setDraft(d => ({ ...d, description: e.target.value }))}
                    placeholder="What should the AI extract for this field?"
                    className="flex-1 border border-border-strong rounded px-2 py-1.5 text-xs text-text bg-panel focus:outline-none focus:ring-1 focus:ring-teal/40 placeholder:text-text-mute"
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomField() } }}
                  />
                  <button
                    type="button"
                    onClick={addCustomField}
                    className="px-3 py-1.5 text-xs font-medium text-white bg-teal rounded hover:bg-teal/90 transition-colors duration-150 shrink-0"
                  >
                    Add
                  </button>
                </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 pt-1">
              <button
                type="button"
                onClick={() => { setStep(1); setSubmitError(null) }}
                className="px-4 py-2 text-sm font-medium text-text-mid border border-border rounded-lg hover:border-border-strong hover:text-text transition-colors duration-150"
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading || (fromScratch && customFields.length === 0)}
                className="px-4 py-2 text-sm font-medium text-white bg-navy rounded-lg hover:bg-navy-soft disabled:opacity-60 disabled:cursor-not-allowed transition-colors duration-150 flex items-center gap-2"
              >
                {loading && (
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                )}
                {loading ? 'Creating...' : 'Create Case'}
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-12px) scale(0.98); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  )
}
