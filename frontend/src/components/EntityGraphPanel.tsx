import '@xyflow/react/dist/style.css'
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  type NodeProps,
  type ReactFlowInstance,
  type Node,
  type Edge,
} from '@xyflow/react'
import type { Entity, Relationship } from '../types'
import { fetchEntities } from '../api'

// ── Type colour system ─────────────────────────────────────────────────────

interface TypeConfig { color: string; bg: string; border: string; label: string }

const TYPE_CONFIG: Record<string, TypeConfig> = {
  person:            { color: '#3B82F6', bg: '#EFF6FF', border: '#93C5FD', label: 'Person' },
  vendor:            { color: '#0D9488', bg: '#F0FDFA', border: '#5EEAD4', label: 'Vendor' },
  company:           { color: '#0D9488', bg: '#F0FDFA', border: '#5EEAD4', label: 'Company' },
  organization:      { color: '#0D9488', bg: '#F0FDFA', border: '#5EEAD4', label: 'Organization' },
  location:          { color: '#16A34A', bg: '#F0FDF4', border: '#86EFAC', label: 'Location' },
  bank_account:      { color: '#CA8A04', bg: '#FEFCE8', border: '#FDE047', label: 'Bank Account' },
  financial:         { color: '#CA8A04', bg: '#FEFCE8', border: '#FDE047', label: 'Financial' },
  financial_account: { color: '#CA8A04', bg: '#FEFCE8', border: '#FDE047', label: 'Financial' },
  po:                { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'PO' },
  invoice:           { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Invoice' },
  document:          { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Document' },
  reference:         { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Reference' },
  phone:             { color: '#EC4899', bg: '#FDF2F8', border: '#F9A8D4', label: 'Phone' },
  benefit:           { color: '#F97316', bg: '#FFF7ED', border: '#FDBA74', label: 'Benefit' },
}
const FALLBACK_CONFIG: TypeConfig = { color: '#8B5CF6', bg: '#F5F3FF', border: '#C4B5FD', label: 'Other' }

function typeConfig(t: string): TypeConfig {
  const known = TYPE_CONFIG[t.toLowerCase()]
  if (known) return known
  // Dynamic label for any AI-returned type not in the preset list
  const label = t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  return { ...FALLBACK_CONFIG, label }
}

// ── Custom node ────────────────────────────────────────────────────────────

function EntityNode({ data, selected }: NodeProps) {
  const entity = data.entity as Entity
  const cfg = typeConfig(entity.entity_type)
  const pct = Math.round((entity.confidence_score ?? 1) * 100)

  return (
    <>
      <Handle type="target" position={Position.Top}    id="t" style={{ opacity: 0, width: 1, height: 1 }} isConnectable={false} />
      <Handle type="target" position={Position.Left}   id="l" style={{ opacity: 0, width: 1, height: 1 }} isConnectable={false} />
      <Handle type="source" position={Position.Bottom} id="b" style={{ opacity: 0, width: 1, height: 1 }} isConnectable={false} />
      <Handle type="source" position={Position.Right}  id="r" style={{ opacity: 0, width: 1, height: 1 }} isConnectable={false} />

      <div style={{
        background: cfg.bg,
        border: `${selected ? 2 : 1}px solid ${selected ? cfg.color : cfg.border}`,
        borderRadius: 12,
        padding: '10px 14px',
        minWidth: 160,
        maxWidth: 220,
        boxShadow: selected
          ? `0 0 0 3px ${cfg.color}33, 0 4px 12px rgba(0,0,0,0.1)`
          : '0 2px 6px rgba(0,0,0,0.08)',
        cursor: 'pointer',
        userSelect: 'none',
      }}>
        <div style={{ height: 3, background: cfg.color, borderRadius: 2, marginBottom: 8 }} />
        <p style={{
          fontSize: 12, fontWeight: 700, color: '#1A2332',
          lineHeight: 1.4, wordBreak: 'break-word', marginBottom: 6,
        }}>
          {entity.canonical_name}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: cfg.color, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {cfg.label}
          </span>
          <span style={{ fontSize: 10, color: '#9CA3AF', fontVariantNumeric: 'tabular-nums' }}>
            {pct}%
          </span>
        </div>
      </div>
    </>
  )
}

const NODE_TYPES = { entityNode: EntityNode }

// ── Layout ─────────────────────────────────────────────────────────────────

function buildGraph(
  entities: Entity[],
  relationships: Relationship[],
): { nodes: Node[]; edges: Edge[] } {
  if (entities.length === 0) return { nodes: [], edges: [] }

  const groups = new Map<string, Entity[]>()
  for (const e of entities) {
    const key = e.entity_type.toLowerCase()
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(e)
  }

  const types = Array.from(groups.keys())
  const CLUSTER_R = Math.max(320, types.length * 160)
  const CX = 480, CY = 360

  const nodes: Node[] = []
  types.forEach((type, ti) => {
    const cluster = groups.get(type)!
    const clusterAngle = (ti / types.length) * 2 * Math.PI - Math.PI / 2
    const cx = CX + Math.cos(clusterAngle) * CLUSTER_R
    const cy = CY + Math.sin(clusterAngle) * CLUSTER_R

    cluster.forEach((entity, ni) => {
      const NODE_R = cluster.length === 1 ? 0 : Math.max(150, cluster.length * 70)
      const a = (ni / cluster.length) * 2 * Math.PI
      nodes.push({
        id: entity.canonical_name,
        type: 'entityNode',
        position: { x: cx + Math.cos(a) * NODE_R, y: cy + Math.sin(a) * NODE_R },
        data: { entity },
      })
    })
  })

  // Case-insensitive lookup: normalised name → canonical node id
  const nameMap = new Map<string, string>()
  entities.forEach(e => nameMap.set(e.canonical_name.toLowerCase().trim(), e.canonical_name))

  const edges: Edge[] = relationships
    .map(r => {
      const src = nameMap.get(r.source_name.toLowerCase().trim())
      const tgt = nameMap.get(r.target_name.toLowerCase().trim())
      if (!src || !tgt) return null
      return {
        id: r.relationship_id,
        source: src,
        target: tgt,
        label: r.relationship_type.replace(/_/g, ' '),
        type: 'smoothstep',
        style: { stroke: '#94A3B8', strokeWidth: 1.5 },
        labelStyle: { fontSize: 9, fill: '#475569', fontWeight: 500 },
        labelBgStyle: { fill: '#F8FAFC', fillOpacity: 0.92 },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 3,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#94A3B8',
          width: 10,
          height: 10,
        },
      }
    })
    .filter((e): e is Edge => e !== null)

  return { nodes, edges }
}

// ── Detail side-panel ──────────────────────────────────────────────────────

function EntityDetail({
  entity,
  relationships,
  onClose,
}: {
  entity: Entity
  relationships: Relationship[]
  onClose: () => void
}) {
  const cfg = typeConfig(entity.entity_type)
  const pct = Math.round((entity.confidence_score ?? 1) * 100)
  const outgoing = relationships.filter(r => r.source_name === entity.canonical_name)
  const incoming = relationships.filter(r => r.target_name === entity.canonical_name)

  return (
    <aside className="w-64 shrink-0 bg-panel border-l border-border flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <span
            className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full self-start"
            style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}` }}
          >
            {cfg.label}
          </span>
          <p className="text-sm font-bold text-text leading-snug break-words">{entity.canonical_name}</p>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 text-text-mute hover:text-text mt-0.5 transition-colors"
          aria-label="Close"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-5">
        {/* Confidence */}
        <div className="flex flex-col gap-1.5">
          <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Confidence</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-panel-3 rounded-full overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${pct}%`, background: cfg.color }} />
            </div>
            <span className="text-xs font-semibold text-text tabular-nums">{pct}%</span>
          </div>
        </div>

        {/* Aliases */}
        {entity.aliases && entity.aliases.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Also known as</p>
            <div className="flex flex-wrap gap-1">
              {entity.aliases.map((a: string) => (
                <span key={a} className="text-[10px] bg-panel-2 border border-border text-text-mid px-2 py-0.5 rounded-full">
                  {a}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Relationships */}
        {(outgoing.length > 0 || incoming.length > 0) && (
          <div className="flex flex-col gap-2">
            <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Relationships</p>
            {outgoing.map(r => (
              <div key={r.relationship_id} className="flex items-start gap-2 text-xs">
                <span className="shrink-0 text-teal mt-0.5">→</span>
                <span className="text-text-mute italic">{r.relationship_type.replace(/_/g, ' ')}</span>
                <span className="font-medium text-text truncate">{r.target_name}</span>
              </div>
            ))}
            {incoming.map(r => (
              <div key={r.relationship_id} className="flex items-start gap-2 text-xs">
                <span className="shrink-0 text-text-mute mt-0.5">←</span>
                <span className="text-text-mute italic">{r.relationship_type.replace(/_/g, ' ')}</span>
                <span className="font-medium text-text truncate">{r.source_name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}

// ── Main panel ─────────────────────────────────────────────────────────────

export default function EntityGraphPanel({
  caseId,
  onRunAnalysis,
  analysisState,
}: {
  caseId: string
  onRunAnalysis?: () => void
  analysisState?: string
}) {
  const [data, setData] = useState<{ entities: Entity[]; relationships: Relationship[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const rfRef = useRef<ReactFlowInstance | null>(null)

  function fitAfterLoad() {
    setTimeout(() => rfRef.current?.fitView({ padding: 0.25, duration: 400 }), 80)
  }

  useEffect(() => {
    fetchEntities(caseId)
      .then(d => {
        setData(d)
        const { nodes: n, edges: e } = buildGraph(d.entities, d.relationships)
        setNodes(n)
        setEdges(e)
        fitAfterLoad()
      })
      .catch(() => setError('Failed to load entity graph.'))
  }, [caseId, setNodes, setEdges])

  const entityMap = useMemo(
    () => Object.fromEntries((data?.entities ?? []).map(e => [e.canonical_name, e])),
    [data],
  )

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedEntity(entityMap[node.id] ?? null)
    },
    [entityMap],
  )

  const onPaneClick = useCallback(() => setSelectedEntity(null), [])

  // Legend: only show types present in data
  const presentTypes = useMemo(() => {
    const seen = new Set((data?.entities ?? []).map(e => e.entity_type.toLowerCase()))
    return Object.entries(TYPE_CONFIG).filter(([k]) => seen.has(k))
  }, [data])

  if (error) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <p className="text-sm text-red">{error}</p>
      </div>
    )
  }

  if (data === null) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-teal/30 border-t-teal rounded-full animate-spin" />
      </div>
    )
  }

  if (data.entities.length === 0) {
    return (
      <div className="flex-1 bg-canvas-deep flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center px-6">
          <div className="w-12 h-12 bg-panel border border-border rounded-xl flex items-center justify-center shadow-sm">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#878E99" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="5" r="2" /><circle cx="5" cy="19" r="2" /><circle cx="19" cy="19" r="2" />
              <line x1="12" y1="7" x2="5" y2="17" /><line x1="12" y1="7" x2="19" y2="17" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-text">No entities yet</p>
          <p className="text-xs text-text-mute max-w-xs">
            Run analysis to extract people, organizations, and relationships from the documents.
          </p>
          {onRunAnalysis && (
            <button
              onClick={onRunAnalysis}
              disabled={analysisState === 'running'}
              className="mt-1 flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-teal hover:bg-teal-soft rounded-lg transition-colors duration-150 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {analysisState === 'running' && (
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              {analysisState === 'running' ? 'Running analysis…' : 'Run Analysis'}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Graph canvas */}
      <div className="flex-1 relative" style={{ background: '#F8FAFC' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onInit={(instance) => { rfRef.current = instance }}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.25}
          maxZoom={2}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable
        >
          <Background color="#CBD5E1" gap={20} size={1} />
          <Controls showInteractive={false} style={{ bottom: 16, left: 16 }} />

          {/* Legend */}
          {presentTypes.length > 0 && (
            <div
              className="absolute top-3 left-3 z-10 bg-white/95 border border-slate-200 rounded-xl px-3 py-2.5 flex flex-col gap-1.5 shadow-sm"
              style={{ backdropFilter: 'blur(4px)' }}
            >
              <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-0.5">Entity Types</p>
              {presentTypes.map(([, cfg]) => (
                <div key={cfg.label} className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: cfg.color }} />
                  <span className="text-[10px] text-slate-600 font-medium">{cfg.label}</span>
                </div>
              ))}
            </div>
          )}

          {/* Stats + Re-run */}
          <div className="absolute top-3 right-3 z-10 flex items-center gap-2">
            <div className="bg-white/95 border border-slate-200 rounded-xl px-3 py-2 shadow-sm flex items-center gap-3">
              <span className="text-[10px] text-slate-500">
                <span className="font-semibold text-slate-700">{data.entities.length}</span> entities
              </span>
              <span className="text-slate-300">·</span>
              <span className="text-[10px] text-slate-500">
                <span className="font-semibold text-slate-700">{data.relationships.length}</span> relationships
              </span>
            </div>
            <button
              onClick={() => rfRef.current?.fitView({ padding: 0.25, duration: 400 })}
              title="Fit all nodes in view"
              className="flex items-center justify-center w-8 h-8 bg-white/95 border border-slate-200 rounded-xl shadow-sm hover:bg-slate-50 transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
              </svg>
            </button>
            {onRunAnalysis && (
              <button
                onClick={onRunAnalysis}
                disabled={analysisState === 'running'}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-teal hover:bg-teal-soft rounded-xl shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {analysisState === 'running' && (
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                )}
                {analysisState === 'running' ? 'Running…' : 'Re-run Analysis'}
              </button>
            )}
          </div>
        </ReactFlow>
      </div>

      {/* Entity detail panel */}
      {selectedEntity && (
        <EntityDetail
          entity={selectedEntity}
          relationships={data.relationships}
          onClose={() => setSelectedEntity(null)}
        />
      )}
    </div>
  )
}
