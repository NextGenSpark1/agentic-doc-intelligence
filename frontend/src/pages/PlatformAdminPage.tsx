import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { platformListOrgs, platformCreateOrg, platformDeleteOrg, platformUpdateOrg } from '../api'
import type { Organisation } from '../types'
import { useAuth } from '../context/AuthContext'

const PLATFORM_ADMIN_EMAILS = ['nextgenspark2025@gmail.com', 'hello@nextgenspark.solutions']

const PLAN_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  trial:      { text: '#B45309', bg: '#FFFBEB', border: '#FDE68A' },
  pro:        { text: '#0D9488', bg: '#F0FDFA', border: '#99F6E4' },
  enterprise: { text: '#7C3AED', bg: '#F5F3FF', border: '#DDD6FE' },
}

function planStyle(plan: string) {
  const c = PLAN_COLORS[plan] ?? { text: '#64748B', bg: '#F8FAFC', border: '#E2E8F0' }
  return { color: c.text, background: c.bg, border: `1px solid ${c.border}` }
}

export default function PlatformAdminPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [orgs, setOrgs] = useState<Organisation[]>([])
  const [loading, setLoading] = useState(true)

  // create
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', plan: 'trial', adminEmail: '', adminName: '' })
  const [creating, setCreating] = useState(false)
  const [lastInviteLink, setLastInviteLink] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  // per-org actions
  const [expandedOrg, setExpandedOrg] = useState<string | null>(null)
  const [editingPlan, setEditingPlan] = useState<Record<string, string>>({})
  const [savingPlan, setSavingPlan] = useState<string | null>(null)
  const [togglingStatus, setTogglingStatus] = useState<string | null>(null)
  const [deletingOrg, setDeletingOrg] = useState<string | null>(null)

  useEffect(() => {
    if (!user || !PLATFORM_ADMIN_EMAILS.includes(user.email ?? '')) {
      navigate('/')
      return
    }
    platformListOrgs().then(d => setOrgs(d.orgs)).finally(() => setLoading(false))
  }, [user, navigate])

  async function handleCreate() {
    if (!form.name || !form.adminEmail) return
    setCreating(true)
    try {
      const result = await platformCreateOrg(form.name, form.plan, form.adminEmail, form.adminName || undefined)
      setOrgs(prev => [{ ...result.org, member_count: 0, case_count: 0 }, ...prev])
      setLastInviteLink(result.invite_link)
      setShowCreate(false)
      setForm({ name: '', plan: 'trial', adminEmail: '', adminName: '' })
    } catch {
      alert('Failed to create org')
    } finally {
      setCreating(false)
    }
  }

  async function handlePlanSave(org: Organisation) {
    const newPlan = editingPlan[org.org_id]
    if (!newPlan || newPlan === org.plan) return
    setSavingPlan(org.org_id)
    try {
      const updated = await platformUpdateOrg(org.org_id, { plan: newPlan })
      setOrgs(prev => prev.map(o => o.org_id === org.org_id ? { ...o, plan: updated.plan ?? newPlan } : o))
      setEditingPlan(prev => { const n = { ...prev }; delete n[org.org_id]; return n })
    } catch {
      alert('Failed to update plan')
    } finally {
      setSavingPlan(null)
    }
  }

  async function handleToggleStatus(org: Organisation) {
    const newStatus = (org.status ?? 'active') === 'active' ? 'suspended' : 'active'
    const label = newStatus === 'suspended' ? 'Suspend' : 'Reactivate'
    if (!window.confirm(`${label} "${org.name}"?`)) return
    setTogglingStatus(org.org_id)
    try {
      const updated = await platformUpdateOrg(org.org_id, { status: newStatus })
      setOrgs(prev => prev.map(o => o.org_id === org.org_id ? { ...o, status: updated.status ?? newStatus } : o))
    } catch {
      alert('Failed to update status')
    } finally {
      setTogglingStatus(null)
    }
  }

  async function handleDelete(org: Organisation) {
    if (!window.confirm(`Permanently delete "${org.name}"? This cannot be undone.`)) return
    setDeletingOrg(org.org_id)
    try {
      await platformDeleteOrg(org.org_id)
      setOrgs(prev => prev.filter(o => o.org_id !== org.org_id))
    } catch {
      alert('Failed to delete organisation')
    } finally {
      setDeletingOrg(null)
    }
  }

  const isSuspended = (org: Organisation) => (org.status ?? 'active') === 'suspended'

  return (
    <div style={{ minHeight: '100vh', background: '#F8FAFC' }}>
      {/* Header */}
      <div style={{ background: '#0F172A', padding: '0 32px', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#fff', fontWeight: 800, fontSize: 15 }}>NextGen Spark</span>
          <span style={{ color: '#64748B', fontSize: 12 }}>·</span>
          <span style={{ color: '#94A3B8', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Platform Admin</span>
        </div>
        <button onClick={() => navigate('/')} style={{ color: '#94A3B8', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}>
          ← Back to app
        </button>
      </div>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '40px 24px' }}>
        {/* Page title row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: '#0F172A', margin: 0 }}>Organisations</h1>
            <p style={{ fontSize: 13, color: '#64748B', margin: '4px 0 0' }}>{orgs.length} organisation{orgs.length !== 1 ? 's' : ''} on the platform</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            style={{ background: '#0F172A', color: '#fff', border: 'none', borderRadius: 10, padding: '10px 20px', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}
          >
            + New Organisation
          </button>
        </div>

        {/* New org invite link banner */}
        {lastInviteLink && (
          <div style={{ background: '#F0FDFA', border: '1px solid #5EEAD4', borderRadius: 12, padding: '14px 20px', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: '#0E7C86', margin: '0 0 3px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Org admin invite link</p>
              <p style={{ fontSize: 12, color: '#0F172A', margin: 0, wordBreak: 'break-all', fontFamily: 'monospace' }}>{lastInviteLink}</p>
            </div>
            <button
              onClick={() => { navigator.clipboard.writeText(lastInviteLink); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
              style={{ background: '#0E7C86', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', fontWeight: 700, fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}
            >
              {copied ? 'Copied!' : 'Copy link'}
            </button>
          </div>
        )}

        {/* Org list */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#94A3B8', fontSize: 14 }}>Loading…</div>
        ) : orgs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#94A3B8', fontSize: 14 }}>No organisations yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {orgs.map(org => {
              const suspended = isSuspended(org)
              const isExpanded = expandedOrg === org.org_id
              const pendingPlan = editingPlan[org.org_id] ?? org.plan

              return (
                <div
                  key={org.org_id}
                  style={{
                    background: '#fff',
                    border: suspended ? '1px solid #FCA5A5' : '1px solid #E2E8F0',
                    borderRadius: 14,
                    overflow: 'hidden',
                    opacity: suspended ? 0.85 : 1,
                  }}
                >
                  {/* Main row */}
                  <div style={{ padding: '18px 24px', display: 'flex', alignItems: 'center', gap: 20 }}>
                    {/* Org info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                        <p style={{ fontSize: 15, fontWeight: 700, color: '#0F172A', margin: 0 }}>{org.name}</p>
                        {suspended && (
                          <span style={{ fontSize: 10, fontWeight: 700, color: '#DC2626', background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: 20, padding: '1px 8px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                            Suspended
                          </span>
                        )}
                      </div>
                      <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>
                        {org.org_id} · Created {new Date(org.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </p>
                    </div>

                    {/* Stats */}
                    <div style={{ display: 'flex', gap: 28, textAlign: 'center' }}>
                      <div>
                        <p style={{ fontSize: 18, fontWeight: 800, color: '#0F172A', margin: 0 }}>{org.member_count ?? 0}</p>
                        <p style={{ fontSize: 10, color: '#94A3B8', margin: 0 }}>members</p>
                      </div>
                      <div>
                        <p style={{ fontSize: 18, fontWeight: 800, color: '#0F172A', margin: 0 }}>{org.case_count ?? 0}</p>
                        <p style={{ fontSize: 10, color: '#94A3B8', margin: 0 }}>cases</p>
                      </div>
                    </div>

                    {/* Plan selector */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <select
                        value={pendingPlan}
                        onChange={e => setEditingPlan(prev => ({ ...prev, [org.org_id]: e.target.value }))}
                        style={{ ...planStyle(pendingPlan), borderRadius: 20, padding: '3px 10px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', cursor: 'pointer', outline: 'none' }}
                      >
                        <option value="trial">Trial</option>
                        <option value="pro">Pro</option>
                        <option value="enterprise">Enterprise</option>
                      </select>
                      {pendingPlan !== org.plan && (
                        <button
                          onClick={() => handlePlanSave(org)}
                          disabled={savingPlan === org.org_id}
                          style={{ background: '#0F172A', color: '#fff', border: 'none', borderRadius: 8, padding: '4px 10px', fontSize: 11, fontWeight: 700, cursor: 'pointer', opacity: savingPlan === org.org_id ? 0.5 : 1 }}
                        >
                          {savingPlan === org.org_id ? '…' : 'Save'}
                        </button>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div style={{ display: 'flex', gap: 6 }}>
                      {/* Expand members */}
                      <button
                        onClick={() => setExpandedOrg(isExpanded ? null : org.org_id)}
                        style={{ background: 'none', border: '1px solid #E2E8F0', borderRadius: 8, padding: '6px 12px', color: '#64748B', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                      >
                        {isExpanded ? 'Hide' : 'Members'}
                      </button>
                      {/* Suspend / Activate */}
                      <button
                        onClick={() => handleToggleStatus(org)}
                        disabled={togglingStatus === org.org_id}
                        style={{
                          background: 'none',
                          border: suspended ? '1px solid #86EFAC' : '1px solid #FCD34D',
                          borderRadius: 8, padding: '6px 12px',
                          color: suspended ? '#16A34A' : '#B45309',
                          fontSize: 12, fontWeight: 600, cursor: 'pointer',
                          opacity: togglingStatus === org.org_id ? 0.5 : 1,
                        }}
                      >
                        {togglingStatus === org.org_id ? '…' : suspended ? 'Activate' : 'Suspend'}
                      </button>
                      {/* Delete */}
                      <button
                        onClick={() => handleDelete(org)}
                        disabled={deletingOrg === org.org_id}
                        style={{ background: 'none', border: '1px solid #FCA5A5', borderRadius: 8, padding: '6px 12px', color: '#DC2626', fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: deletingOrg === org.org_id ? 0.5 : 1 }}
                      >
                        {deletingOrg === org.org_id ? '…' : 'Delete'}
                      </button>
                    </div>
                  </div>

                  {/* Expanded members panel */}
                  {isExpanded && (
                    <div style={{ borderTop: '1px solid #F1F5F9', background: '#F8FAFC', padding: '16px 24px' }}>
                      <p style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 12px' }}>Members</p>
                      {!org.members || org.members.length === 0 ? (
                        <p style={{ fontSize: 13, color: '#94A3B8' }}>No members yet.</p>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {org.members.map(m => (
                            <div key={m.user_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: '#475569', flexShrink: 0 }}>
                                {(m.full_name || m.email).slice(0, 2).toUpperCase()}
                              </div>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.full_name || m.email}</p>
                                {m.full_name && <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>{m.email}</p>}
                              </div>
                              <span style={{ fontSize: 10, fontWeight: 700, borderRadius: 20, padding: '2px 8px', border: '1px solid', ...({ org_admin: { color: '#0D9488', background: '#F0FDFA', borderColor: '#99F6E4' }, supervisor: { color: '#4F46E5', background: '#EEF2FF', borderColor: '#C7D2FE' }, member: { color: '#64748B', background: '#F8FAFC', borderColor: '#E2E8F0' } }[m.role] ?? {}) }}>
                                {m.role === 'org_admin' ? 'Org Admin' : m.role === 'supervisor' ? 'Supervisor' : 'Member'}
                              </span>
                              <p style={{ fontSize: 11, color: '#94A3B8', margin: 0, flexShrink: 0 }}>
                                Joined {new Date(m.joined_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Create org modal */}
      {showCreate && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}
          onClick={() => setShowCreate(false)}
        >
          <div
            style={{ background: '#fff', borderRadius: 16, padding: '32px', width: 420, display: 'flex', flexDirection: 'column', gap: 16 }}
            onClick={e => e.stopPropagation()}
          >
            <h2 style={{ fontSize: 17, fontWeight: 800, color: '#0F172A', margin: 0 }}>New Organisation</h2>
            {[
              { label: 'Organisation name', key: 'name', placeholder: 'e.g. MACC Investigation Unit' },
              { label: 'Admin email', key: 'adminEmail', placeholder: 'admin@client.gov.my' },
              { label: 'Admin name (optional)', key: 'adminName', placeholder: 'e.g. Ahmad bin Hassan' },
            ].map(f => (
              <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>{f.label}</label>
                <input
                  value={form[f.key as keyof typeof form]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  style={{ border: '1.5px solid #E2E8F0', borderRadius: 8, padding: '9px 12px', fontSize: 13, outline: 'none' }}
                />
              </div>
            ))}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Plan</label>
              <select
                value={form.plan}
                onChange={e => setForm(p => ({ ...p, plan: e.target.value }))}
                style={{ border: '1.5px solid #E2E8F0', borderRadius: 8, padding: '9px 12px', fontSize: 13 }}
              >
                <option value="trial">Trial</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
              <button
                onClick={() => setShowCreate(false)}
                style={{ padding: '9px 18px', borderRadius: 8, border: '1px solid #E2E8F0', background: 'transparent', color: '#64748B', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !form.name || !form.adminEmail}
                style={{ padding: '9px 18px', borderRadius: 8, background: '#0F172A', color: '#fff', fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer', opacity: (creating || !form.name || !form.adminEmail) ? 0.6 : 1 }}
              >
                {creating ? 'Creating…' : 'Create & send invite'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
