import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
  Handle,
  Position,
  type NodeProps,
  type ReactFlowInstance,
  type Node,
  type Edge,
  type Connection,
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
  tender:            { color: '#7C3AED', bg: '#F5F3FF', border: '#C4B5FD', label: 'Tender' },
  document:          { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Document' },
  reference:         { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Reference' },
  phone:             { color: '#EC4899', bg: '#FDF2F8', border: '#F9A8D4', label: 'Phone' },
  benefit:           { color: '#F97316', bg: '#FFF7ED', border: '#FDBA74', label: 'Benefit' },
  unknown:           { color: '#9CA3AF', bg: '#F9FAFB', border: '#E5E7EB', label: 'Unknown' },
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
  const confidencePercentage = Math.round((entity.confidence_score ?? 1) * 100)
  const editMode = data.editMode as boolean | undefined
  const onDelete = data.onDelete as ((id: string) => void) | undefined

  return (
    <>
      <Handle type="target" position={Position.Top}    id="t" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />
      <Handle type="target" position={Position.Left}   id="l" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />
      <Handle type="source" position={Position.Bottom} id="b" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />
      <Handle type="source" position={Position.Right}  id="r" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />

      <div style={{
        background: cfg.bg,
        border: `${selected ? 2.5 : 1.5}px solid ${selected ? cfg.color : (editMode ? cfg.color + '88' : cfg.border)}`,
        borderRadius: 14,
        padding: '14px 18px',
        minWidth: 200,
        maxWidth: 280,
        boxShadow: selected
          ? `0 0 0 4px ${cfg.color}33, 0 6px 16px rgba(0,0,0,0.12)`
          : '0 2px 8px rgba(0,0,0,0.10)',
        cursor: 'pointer',
        userSelect: 'none',
        position: 'relative',
      }}>
        {editMode && onDelete && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(entity.entity_id) }}
            title="Remove node"
            style={{
              position: 'absolute', top: 6, right: 6,
              width: 18, height: 18, borderRadius: '50%',
              background: '#FEE2E2', border: '1px solid #FCA5A5',
              color: '#DC2626', fontSize: 12, lineHeight: '16px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', padding: 0,
            }}
          >
            ×
          </button>
        )}
        <div style={{ height: 4, background: cfg.color, borderRadius: 2, marginBottom: 10 }} />
        <p style={{
          fontSize: 14, fontWeight: 700, color: '#1A2332',
          lineHeight: 1.4, wordBreak: 'break-word', marginBottom: 8,
        }}>
          {entity.canonical_name}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{
            fontSize: 11, fontWeight: 700, color: cfg.color,
            textTransform: 'uppercase', letterSpacing: '0.07em',
            background: `${cfg.color}18`, borderRadius: 4, padding: '2px 6px',
          }}>
            {cfg.label}
          </span>
          <span style={{ fontSize: 11, color: '#9CA3AF', fontVariantNumeric: 'tabular-nums' }}>
            {confidencePercentage}%
          </span>
        </div>
      </div>
    </>
  )
}

const NODE_TYPES = { entityNode: EntityNode }

// ── Layout ─────────────────────────────────────────────────────────────────

// Mirrors Python's _normalise in resolve_entities.py:
// strips role-in-parens, comma-role suffix, collapses whitespace, lowercases
function normalizeName(name: string): string {
  return name
    .replace(/\s*\([^)]*\)/g, '')
    .replace(/,.*$/, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

const NODE_WIDTH = 260
const NODE_HEIGHT = 100

function buildGraph(
  entities: Entity[],
  relationships: Relationship[],
): { nodes: Node[]; edges: Edge[] } {
  // Multi-key lookup: exact lowercase, normalised form, and all aliases
  const nameMap = new Map<string, string>()
  const entityByCanonical = new Map<string, Entity>()
  entities.forEach(e => {
    entityByCanonical.set(e.canonical_name, e)
    nameMap.set(e.canonical_name.toLowerCase().trim(), e.canonical_name)
    nameMap.set(normalizeName(e.canonical_name), e.canonical_name)
    ;(e.aliases ?? []).forEach((alias: string) => {
      nameMap.set(alias.toLowerCase().trim(), e.canonical_name)
      nameMap.set(normalizeName(alias), e.canonical_name)
    })
  })

  function resolveToNodeId(raw: string): string {
    return nameMap.get(raw.toLowerCase().trim())
        ?? nameMap.get(normalizeName(raw))
        ?? raw.trim()
  }

  // Set up dagre graph for automatic layout
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 70, ranksep: 160, marginx: 60, marginy: 60 })

  // Register all entity nodes
  const registeredIds = new Set<string>()
  entities.forEach(e => {
    g.setNode(e.canonical_name, { width: NODE_WIDTH, height: NODE_HEIGHT })
    registeredIds.add(e.canonical_name)
  })

  // Register virtual nodes for any relationship endpoint not in the entity list.
  // Use source_type / target_type from the relationship evidence so the AI's
  // own type label is shown instead of "unknown".
  const virtualEntities = new Map<string, Entity>()
  relationships.forEach(r => {
    const pairs: [string, string][] = [
      [resolveToNodeId(r.source_name), String(r.evidence?.source_type ?? '').toLowerCase().trim()],
      [resolveToNodeId(r.target_name), String(r.evidence?.target_type ?? '').toLowerCase().trim()],
    ]
    pairs.forEach(([id, aiType]) => {
      if (!registeredIds.has(id)) {
        g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT })
        registeredIds.add(id)
        virtualEntities.set(id, {
          entity_id: `virt-${id}`,
          case_id: '',
          canonical_name: id,
          entity_type: aiType || 'unknown',
          aliases: [],
          confidence_score: 0.5,
        } as Entity)
      }
    })
  })

  // Register all edges so dagre can compute a clean layout
  relationships.forEach(r => {
    const src = resolveToNodeId(r.source_name)
    const tgt = resolveToNodeId(r.target_name)
    if (src !== tgt) g.setEdge(src, tgt)
  })

  dagre.layout(g)

  // Convert dagre positions to React Flow nodes
  const nodes: Node[] = g.nodes().map(id => {
    const pos = g.node(id)
    const entity = entityByCanonical.get(id)
      ?? virtualEntities.get(id)
      ?? { entity_id: `virt-${id}`, case_id: '', canonical_name: id, entity_type: 'unknown', aliases: [], confidence_score: 0.5 } as Entity
    return {
      id,
      type: 'entityNode',
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: { entity },
    }
  })

  // ALL relationships become edges — nothing is ever dropped
  const edges: Edge[] = relationships.map((r): Edge => ({
    id: r.relationship_id,
    source: resolveToNodeId(r.source_name),
    target: resolveToNodeId(r.target_name),
    label: r.relationship_type.replace(/_/g, ' '),
    type: 'smoothstep',
    style: { stroke: '#94A3B8', strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: '#475569', fontWeight: 600 },
    labelBgStyle: { fill: '#F8FAFC', fillOpacity: 0.95 },
    labelBgPadding: [5, 3] as [number, number],
    labelBgBorderRadius: 4,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#94A3B8', width: 12, height: 12 },
  }))

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
  const confidencePercentage = Math.round((entity.confidence_score ?? 1) * 100)
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
              <div className="h-full rounded-full" style={{ width: `${confidencePercentage}%`, background: cfg.color }} />
            </div>
            <span className="text-xs font-semibold text-text tabular-nums">{confidencePercentage}%</span>
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
  const [statsOpen, setStatsOpen] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const rfRef = useRef<ReactFlowInstance | null>(null)

  function fitAfterLoad() {
    setTimeout(() => rfRef.current?.fitView({ padding: 0.3, maxZoom: 0.85, duration: 400 }), 80)
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
      // Use entity from node data directly so virtual nodes are also clickable
      setSelectedEntity((node.data.entity as Entity) ?? entityMap[node.id] ?? null)
    },
    [entityMap],
  )

  const onPaneClick = useCallback(() => setSelectedEntity(null), [])

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges(eds => addEdge({
        ...connection,
        id: `manual-${Date.now()}`,
        type: 'smoothstep',
        style: { stroke: '#94A3B8', strokeWidth: 1.5, strokeDasharray: '5,3' },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#94A3B8', width: 12, height: 12 },
      }, eds))
    },
    [setEdges],
  )

  const onDeleteNode = useCallback(
    (entityId: string) => {
      setNodes(ns => {
        const target = ns.find(n => (n.data.entity as Entity).entity_id === entityId)
        if (!target) return ns
        setEdges(es => es.filter(e => e.source !== target.id && e.target !== target.id))
        return ns.filter(n => n !== target)
      })
      setSelectedEntity(prev => prev?.entity_id === entityId ? null : prev)
    },
    [setNodes, setEdges],
  )

  // Keep editMode flag and onDelete handler in each node's data so EntityNode can read them
  useEffect(() => {
    setNodes(ns => ns.map(n => ({
      ...n,
      data: { ...n.data, editMode, onDelete: editMode ? onDeleteNode : undefined },
    })))
  }, [editMode, onDeleteNode, setNodes])

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
          onConnect={onConnect}
          onInit={(instance) => { rfRef.current = instance }}
          fitView
          fitViewOptions={{ padding: 0.3, maxZoom: 0.85 }}
          minZoom={0.2}
          maxZoom={2}
          nodesDraggable
          nodesConnectable={editMode}
          elementsSelectable
          deleteKeyCode={editMode ? 'Delete' : null}
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
            {/* Clickable stats badge */}
            <div className="relative">
              <button
                onClick={() => setStatsOpen(s => !s)}
                className="bg-white/95 border border-slate-200 rounded-xl px-3 py-2 shadow-sm flex items-center gap-3 hover:bg-slate-50 transition-colors"
                title="Click to see full list"
              >
                <span className="text-[10px] text-slate-500">
                  <span className="font-semibold text-slate-700">{data.entities.length}</span> entities
                </span>
                <span className="text-slate-300">·</span>
                <span className="text-[10px] text-slate-500">
                  <span className="font-semibold text-slate-700">{data.relationships.length}</span> relationships
                </span>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                  className={`transition-transform duration-150 ${statsOpen ? 'rotate-180' : ''}`}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {statsOpen && (
                <div className="absolute top-full mt-1.5 right-0 bg-white border border-slate-200 rounded-xl shadow-xl w-80 max-h-[420px] overflow-y-auto z-30">
                  {/* Entities section */}
                  <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 rounded-t-xl">
                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      Entities ({data.entities.length})
                    </p>
                  </div>
                  {data.entities.map(e => {
                    const cfg = typeConfig(e.entity_type)
                    return (
                      <div key={e.entity_id} className="px-3 py-2 flex items-center gap-2.5 border-b border-slate-50 hover:bg-slate-50">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cfg.color }} />
                        <span className="text-xs text-slate-700 flex-1 min-w-0 truncate">{e.canonical_name}</span>
                        <span className="text-[10px] font-medium shrink-0" style={{ color: cfg.color }}>{cfg.label}</span>
                        <span className="text-[10px] text-slate-400 shrink-0">{Math.round((e.confidence_score ?? 1) * 100)}%</span>
                      </div>
                    )
                  })}
                  {/* Relationships section */}
                  <div className="px-3 py-2 border-b border-slate-100 border-t bg-slate-50">
                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      Relationships ({data.relationships.length})
                    </p>
                  </div>
                  {data.relationships.map(r => (
                    <div key={r.relationship_id} className="px-3 py-2.5 border-b border-slate-50 hover:bg-slate-50">
                      <div className="flex items-start gap-1.5 text-[11px] flex-wrap">
                        <span className="font-semibold text-slate-700">{r.source_name}</span>
                        <span className="text-slate-400 italic shrink-0">→ {r.relationship_type.replace(/_/g, ' ')} →</span>
                        <span className="font-semibold text-slate-700">{r.target_name}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={() => rfRef.current?.fitView({ padding: 0.3, maxZoom: 0.85, duration: 400 })}
              title="Fit all nodes in view"
              className="flex items-center justify-center w-8 h-8 bg-white/95 border border-slate-200 rounded-xl shadow-sm hover:bg-slate-50 transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
              </svg>
            </button>
            <button
              onClick={() => setEditMode(v => !v)}
              title={editMode ? 'Exit edit mode' : 'Enter edit mode — drag handles to connect, × to delete'}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl shadow-sm transition-colors ${
                editMode
                  ? 'bg-amber-500 text-white border border-amber-400 hover:bg-amber-600'
                  : 'bg-white/95 text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
              {editMode ? 'Done' : 'Edit'}
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
