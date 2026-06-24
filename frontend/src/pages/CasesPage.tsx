import { useState, useEffect, useMemo } from 'react'
import type { Case, CasesListResponse } from '../types'
import { fetchCases } from '../api'
import StatCard from '../components/StatCard'
import FilterPills from '../components/FilterPills'
import CaseTable from '../components/CaseTable'
import NewCaseModal from '../components/NewCaseModal'

export default function CasesPage() {
  const [data, setData] = useState<CasesListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [modalOpen, setModalOpen] = useState(false)

  async function loadCases() {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchCases()
      setData(result)
    } catch {
      setError('Failed to load cases. Is the backend running on localhost:8000?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCases()
  }, [])

  // Auto-dismiss success banner
  useEffect(() => {
    if (!successMsg) return
    const timer = setTimeout(() => setSuccessMsg(null), 3000)
    return () => clearTimeout(timer)
  }, [successMsg])

  const cases: Case[] = data?.cases ?? []

  // Client-side filtering
  const filteredCases = useMemo(() => {
    let result = cases
    // Filter by status pill
    if (activeFilter !== 'all') {
      result = result.filter((c) => c.status.toLowerCase() === activeFilter)
    }
    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (c) =>
          c.case_id.toLowerCase().includes(q) ||
          c.title.toLowerCase().includes(q) ||
          c.lead_investigator.toLowerCase().includes(q),
      )
    }
    return result
  }, [cases, activeFilter, searchQuery])

  // Derive counts from the full cases list
  const counts = useMemo(() => ({
    all: cases.length,
    active: cases.filter((c) => c.status.toLowerCase() === 'active').length,
    pendingReview: cases.filter((c) => c.status.toLowerCase() === 'pending review').length,
    archived: cases.filter((c) => c.status.toLowerCase() === 'archived').length,
  }), [cases])

  const openCases = data?.stats.open_cases ?? cases.filter((c) => c.status.toLowerCase() === 'active').length
  const pendingReview = data?.stats.findings_pending_review ?? counts.pendingReview

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-8 flex flex-col gap-6">
      {/* Banners */}
      {error && (
        <div className="bg-red-bg border border-red/20 text-red text-sm px-4 py-3 rounded-lg">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="bg-green-bg border border-green/20 text-green text-sm px-4 py-3 rounded-lg transition-opacity duration-300">
          {successMsg}
        </div>
      )}

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text">Cases</h1>
          <p className="text-sm text-text-mute mt-0.5">Manage and track all active investigations</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="bg-navy text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-navy-soft transition-colors duration-150 flex items-center gap-2"
        >
          <span className="text-base leading-none">+</span> New Case
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total Cases" value={cases.length} note="All time" accent="default" />
        <StatCard label="Open Cases" value={openCases} note="Currently active" accent="teal" />
        <StatCard label="Pending Review" value={pendingReview} note="Findings awaiting action" accent="red" />
        <StatCard label="Archived" value={counts.archived} note="Closed investigations" accent="default" />
      </div>

      {/* Filters + search row */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <FilterPills counts={counts} active={activeFilter} onSelect={setActiveFilter} />
        <div className="ml-auto">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search cases..."
            className="
              border border-border-strong rounded-lg px-3 py-1.5 text-sm text-text bg-panel
              placeholder:text-text-mute w-52
              focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal
              transition-colors duration-150
            "
          />
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-3 border-teal/30 border-t-teal rounded-full animate-spin" style={{ borderWidth: '3px' }} />
        </div>
      ) : (
        <CaseTable cases={filteredCases} />
      )}

      {/* New Case Modal */}
      <NewCaseModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => {
          setSuccessMsg('Case created successfully.')
          loadCases()
        }}
      />
    </div>
  )
}
