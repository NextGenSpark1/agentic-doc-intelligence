import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { platformListOrgs, platformCreateOrg, platformDeleteOrg } from '../api'
import type { Organisation } from '../types'
import { useAuth } from '../context/AuthContext'

const PLATFORM_ADMIN_EMAILS = ['nextgenspark2025@gmail.com', 'hello@nextgenspark.solutions']

export default function PlatformAdminPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [orgs, setOrgs] = useState<Organisation[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', plan: 'trial', adminEmail: '', adminName: '' })
  const [creating, setCreating] = useState(false)
  const [lastInviteLink, setLastInviteLink] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
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
      setLastInviteLink(window.location.origin + result.invite_link)
      setShowCreate(false)
      setForm({ name: '', plan: 'trial', adminEmail: '', adminName: '' })
    } catch {
      alert('Failed to create org')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(org: Organisation) {
    if (!window.confirm(`Delete "${org.name}"? This is permanent and cannot be undone.`)) return
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

  function copyLink() {
    if (lastInviteLink) {
      navigator.clipboard.writeText(lastInviteLink)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const PLAN_COLORS: Record<string, string> = { trial: '#F59E0B', pro: '#0D9488', enterprise: '#7C3AED' }

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

      <div style={{ maxWidth: 900, margin: '0 auto', padding: '40px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
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

        {/* Invite link banner */}
        {lastInviteLink && (
          <div style={{ background: '#F0FDFA', border: '1px solid #5EEAD4', borderRadius: 12, padding: '16px 20px', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: '#0E7C86', margin: '0 0 4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Org admin invite link</p>
              <p style={{ fontSize: 12, color: '#0F172A', margin: 0, wordBreak: 'break-all', fontFamily: 'monospace' }}>{lastInviteLink}</p>
            </div>
            <button
              onClick={copyLink}
              style={{ background: '#0E7C86', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', fontWeight: 700, fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}
            >
              {copied ? 'Copied!' : 'Copy link'}
            </button>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#94A3B8', fontSize: 14 }}>Loading…</div>
        ) : orgs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#94A3B8', fontSize: 14 }}>No organisations yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {orgs.map(org => (
              <div key={org.org_id} style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 24 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                    <p style={{ fontSize: 15, fontWeight: 700, color: '#0F172A', margin: 0 }}>{org.name}</p>
                    <span style={{
                      fontSize: 10, fontWeight: 700,
                      color: PLAN_COLORS[org.plan] ?? '#64748B',
                      background: `${PLAN_COLORS[org.plan] ?? '#64748B'}15`,
                      border: `1px solid ${PLAN_COLORS[org.plan] ?? '#64748B'}40`,
                      borderRadius: 20, padding: '2px 8px',
                      textTransform: 'uppercase', letterSpacing: '0.06em',
                    }}>{org.plan}</span>
                  </div>
                  <p style={{ fontSize: 12, color: '#94A3B8', margin: 0 }}>
                    Created {new Date(org.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 32, textAlign: 'center', alignItems: 'center' }}>
                  <div>
                    <p style={{ fontSize: 20, fontWeight: 800, color: '#0F172A', margin: 0 }}>{org.member_count ?? 0}</p>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>members</p>
                  </div>
                  <div>
                    <p style={{ fontSize: 20, fontWeight: 800, color: '#0F172A', margin: 0 }}>{org.case_count ?? 0}</p>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: 0 }}>cases</p>
                  </div>
                  <button
                    onClick={() => handleDelete(org)}
                    disabled={deletingOrg === org.org_id}
                    style={{ background: 'none', border: '1px solid #FCA5A5', borderRadius: 8, padding: '7px 14px', color: '#DC2626', fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: deletingOrg === org.org_id ? 0.5 : 1, whiteSpace: 'nowrap' }}
                  >
                    {deletingOrg === org.org_id ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </div>
            ))}
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
