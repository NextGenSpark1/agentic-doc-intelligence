import { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FolderOpen, Activity, Clock, Archive, Plus } from 'lucide-react'
import type { Case, CasesListResponse } from '../types'
import { fetchCases } from '../api'
import StatCard from '../components/StatCard'
import FilterPills from '../components/FilterPills'
import CaseTable from '../components/CaseTable'
import NewCaseModal from '../components/NewCaseModal'

const CASE_TABLE_COLS = 'grid-cols-[160px_1fr_140px_160px_90px_120px_130px]'

function CasesTableSkeleton() {
  return (
    <div className="bg-panel border border-border rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className={`grid ${CASE_TABLE_COLS} gap-x-4 bg-panel-3 border-b-2 border-border px-5 py-3`}>
        {['Case ID', 'Title', 'Type', 'Status', 'Docs', 'Risk', 'Last Activity'].map((col) => (
          <span key={col} className="text-[11px] font-semibold text-text-mid uppercase tracking-widest">
            {col}
          </span>
        ))}
      </div>
      {/* Skeleton rows */}
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className={`grid ${CASE_TABLE_COLS} gap-x-4 items-center px-5 py-3.5 ${i < 3 ? 'border-b border-border' : ''}`}
        >
          <div className="h-4 bg-panel-3 rounded animate-pulse w-24" />
          <div className="flex flex-col gap-1.5 min-w-0">
            <div className="h-4 bg-panel-3 rounded animate-pulse w-3/4" />
            <div className="h-3 bg-panel-3 rounded animate-pulse w-1/2" />
          </div>
          <div className="h-4 bg-panel-3 rounded animate-pulse w-24" />
          <div className="h-5 bg-panel-3 rounded animate-pulse w-20" />
          <div className="h-4 bg-panel-3 rounded animate-pulse w-6" />
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-panel-3 rounded-full animate-pulse" />
            <div className="h-3 bg-panel-3 rounded animate-pulse w-6" />
          </div>
          <div className="h-3 bg-panel-3 rounded animate-pulse w-20" />
        </div>
      ))}
    </div>
  )
}

export default function CasesPage() {
  const [data, setData] = useState<CasesListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState('all')
  const [searchParams] = useSearchParams()
  const urlQuery = searchParams.get('q') ?? ''
  const [searchQuery, setSearchQuery] = useState(urlQuery)
  const [modalOpen, setModalOpen] = useState(false)

  // Sync searchQuery whenever the URL param changes (navbar drives this).
  useEffect(() => {
    setSearchQuery(urlQuery)
  }, [urlQuery])

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
          <h1 className="text-2xl font-bold text-text">Cases</h1>
          <p className="text-sm text-text-mute mt-0.5">Manage and track all active investigations</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="bg-teal hover:bg-teal-soft text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition-all duration-150 flex items-center gap-2 shadow-sm hover:shadow-md hover:-translate-y-0.5"
        >
          <Plus size={15} strokeWidth={2.5} /> New Case
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total Cases"    value={cases.length}  note="All time"               accent="default" icon={FolderOpen} />
        <StatCard label="Open Cases"     value={openCases}     note="Currently active"       accent="teal"    icon={Activity} />
        <StatCard label="Pending Review" value={pendingReview} note="Findings awaiting action" accent="red"   icon={Clock} />
        <StatCard label="Archived"       value={counts.archived} note="Closed investigations" accent="default" icon={Archive} />
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

      {/* Table / empty state */}
      {loading ? (
        <CasesTableSkeleton />
      ) : cases.length === 0 ? (
        <div className="bg-panel border border-border rounded-xl shadow-sm px-6 py-20 flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-panel-3 rounded-2xl flex items-center justify-center mb-5">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#878E99" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="13" x2="15" y2="13" />
              <line x1="9" y1="17" x2="15" y2="17" />
            </svg>
          </div>
          <p className="text-base font-semibold text-text">No cases yet</p>
          <p className="text-sm text-text-mute mt-1.5 max-w-sm">
            Create your first case to start an investigation.
          </p>
          <button
            onClick={() => setModalOpen(true)}
            className="mt-6 bg-teal hover:bg-teal-soft text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition-all duration-150 flex items-center gap-2 shadow-sm hover:shadow-md hover:-translate-y-0.5"
          >
            <Plus size={15} strokeWidth={2.5} /> New Case
          </button>
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
