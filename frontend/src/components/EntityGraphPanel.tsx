import '@xyflow/react/dist/style.css'
import ELK from 'elkjs/lib/elk.bundled.js'
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
import type { Entity, Relationship, Document as CaseDocument } from '../types'
import { fetchEntities, fetchGraphState, saveGraphState } from '../api'

// ── Type colour system ─────────────────────────────────────────────────────

interface TypeConfig { color: string; bg: string; border: string; label: string }

const TYPE_CONFIG: Record<string, TypeConfig> = {
  person: { color: '#3B82F6', bg: '#EFF6FF', border: '#93C5FD', label: 'Person' },
  vendor: { color: '#0D9488', bg: '#F0FDFA', border: '#5EEAD4', label: 'Vendor' },
  company: { color: '#0D9488', bg: '#F0FDFA', border: '#5EEAD4', label: 'Company' },
  organization: { color: '#0D9488', bg: '#F0FDFA', border: '#5EEAD4', label: 'Organization' },
  location: { color: '#16A34A', bg: '#F0FDF4', border: '#86EFAC', label: 'Location' },
  bank_account: { color: '#CA8A04', bg: '#FEFCE8', border: '#FDE047', label: 'Bank Account' },
  financial: { color: '#CA8A04', bg: '#FEFCE8', border: '#FDE047', label: 'Financial' },
  financial_account: { color: '#CA8A04', bg: '#FEFCE8', border: '#FDE047', label: 'Financial' },
  po: { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'PO' },
  invoice: { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Invoice' },
  tender: { color: '#7C3AED', bg: '#F5F3FF', border: '#C4B5FD', label: 'Tender' },
  document: { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Document' },
  reference: { color: '#64748B', bg: '#F8FAFC', border: '#CBD5E1', label: 'Reference' },
  phone: { color: '#EC4899', bg: '#FDF2F8', border: '#F9A8D4', label: 'Phone' },
  benefit: { color: '#F97316', bg: '#FFF7ED', border: '#FDBA74', label: 'Benefit' },
  unknown: { color: '#9CA3AF', bg: '#F9FAFB', border: '#E5E7EB', label: 'Unknown' },
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
      <Handle type="target" position={Position.Top} id="t" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />
      <Handle type="target" position={Position.Left} id="l" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />
      <Handle type="source" position={Position.Bottom} id="b" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />
      <Handle type="source" position={Position.Right} id="r" style={{ opacity: editMode ? 1 : 0, width: editMode ? 8 : 1, height: editMode ? 8 : 1, background: '#0E7C86', border: '2px solid #fff' }} isConnectable={!!editMode} />

      <div style={{
        background: '#FFFFFF',
        border: `2px solid ${selected ? cfg.color : (editMode ? cfg.color + '99' : cfg.border)}`,
        borderLeft: `5px solid ${cfg.color}`,
        borderRadius: 12,
        padding: '14px 16px 12px',
        minWidth: 220,
        maxWidth: 300,
        boxShadow: selected
          ? `0 0 0 3px ${cfg.color}40, 0 8px 24px rgba(0,0,0,0.14)`
          : '0 3px 10px rgba(0,0,0,0.10)',
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
              width: 20, height: 20, borderRadius: '50%',
              background: '#FEE2E2', border: '1px solid #FCA5A5',
              color: '#DC2626', fontSize: 13, lineHeight: '18px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', padding: 0,
            }}
          >
            ×
          </button>
        )}
        <span style={{
          display: 'inline-block', fontSize: 10, fontWeight: 700, color: cfg.color,
          textTransform: 'uppercase', letterSpacing: '0.08em',
          background: `${cfg.color}15`, borderRadius: 4, padding: '2px 7px',
          marginBottom: 8,
        }}>
          {cfg.label}
        </span>
        <p style={{
          fontSize: 13, fontWeight: 700, color: '#0F172A',
          lineHeight: 1.45, wordBreak: 'break-word', marginBottom: 8,
        }}>
          {entity.canonical_name}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ height: 3, flex: 1, background: '#F1F5F9', borderRadius: 2, overflow: 'hidden', marginRight: 8 }}>
            <div style={{ height: '100%', width: `${confidencePercentage}%`, background: cfg.color, borderRadius: 2 }} />
          </div>
          <span style={{ fontSize: 11, color: '#64748B', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
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

const NODE_WIDTH = 300
const NODE_HEIGHT = 110

const elk = new ELK()

function edgeColor(relType: string): string {
  const t = relType.toLowerCase()
  if (/conflict|similar|launder|fraud|suspect|shell/.test(t)) return '#EF4444'
  if (/own|director|sharehold|relative|family|parent|subsidiar|benefi/.test(t)) return '#F97316'
  if (/pay|financ|bank|invoice|transfer|fund|receiv/.test(t)) return '#D97706'
  if (/award|contract|approv|authoris|sign|waiv/.test(t)) return '#7C3AED'
  if (/employ|work|manag|report|supervis/.test(t)) return '#0D9488'
  return '#64748B'
}

async function buildGraph(
  entities: Entity[],
  relationships: Relationship[],
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  // Multi-key lookup: exact lowercase, normalised form, and all aliases
  const nameMap = new Map<string, string>()
  const entityByCanonical = new Map<string, Entity>()
  entities.forEach(e => {
    entityByCanonical.set(e.canonical_name, e)
    nameMap.set(e.canonical_name.toLowerCase().trim(), e.canonical_name)
    nameMap.set(normalizeName(e.canonical_name), e.canonical_name)
      ; (e.aliases ?? []).forEach((alias: string) => {
        nameMap.set(alias.toLowerCase().trim(), e.canonical_name)
        nameMap.set(normalizeName(alias), e.canonical_name)
      })
  })

  function resolveToNodeId(raw: string): string {
    return nameMap.get(raw.toLowerCase().trim())
      ?? nameMap.get(normalizeName(raw))
      ?? raw.trim()
  }

  const registeredIds = new Set<string>()
  const virtualEntities = new Map<string, Entity>()

  entities.forEach(e => registeredIds.add(e.canonical_name))

  relationships.forEach(r => {
    const pairs: [string, string][] = [
      [resolveToNodeId(r.source_name), String(r.evidence?.source_type ?? '').toLowerCase().trim()],
      [resolveToNodeId(r.target_name), String(r.evidence?.target_type ?? '').toLowerCase().trim()],
    ]
    pairs.forEach(([id, aiType]) => {
      if (!registeredIds.has(id)) {
        registeredIds.add(id)
        virtualEntities.set(id, {
          entity_id: `virt-${id}`, case_id: '', canonical_name: id,
          entity_type: aiType || 'unknown', aliases: [], confidence_score: 0.5,
        } as Entity)
      }
    })
  })

  const elkNodes = [...registeredIds].map(id => ({
    id, width: NODE_WIDTH, height: NODE_HEIGHT,
  }))

  // Deduplicate ELK edges bidirectionally so layout doesn't double-count
  const seenElkPairs = new Set<string>()
  const elkEdges: { id: string; sources: string[]; targets: string[] }[] = []
  for (const r of relationships) {
    const src = resolveToNodeId(r.source_name)
    const tgt = resolveToNodeId(r.target_name)
    if (src === tgt) continue
    const [a, b] = src < tgt ? [src, tgt] : [tgt, src]
    const key = `${a}||${b}`
    if (!seenElkPairs.has(key)) {
      seenElkPairs.add(key)
      elkEdges.push({ id: key, sources: [src], targets: [tgt] })
    }
  }

  const graph = await elk.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'stress',
      'elk.stress.desiredEdgeLength': '280',
      'elk.spacing.nodeNode': '80',
      'elk.padding': '[top=80, left=80, bottom=80, right=80]',
    },
    children: elkNodes,
    edges: elkEdges,
  })

  const nodes: Node[] = (graph.children ?? []).map(n => {
    const id = n.id
    const entity = entityByCanonical.get(id)
      ?? virtualEntities.get(id)
      ?? { entity_id: `virt-${id}`, case_id: '', canonical_name: id, entity_type: 'unknown', aliases: [], confidence_score: 0.5 } as Entity
    return {
      id,
      type: 'entityNode',
      position: { x: n.x ?? 0, y: n.y ?? 0 },
      data: { entity },
    }
  })

  // Merge parallel edges (same source→target) into one edge showing all relationship labels
  const COLOR_PRIORITY: Record<string, number> = {
    '#EF4444': 5, '#F97316': 4, '#D97706': 3, '#7C3AED': 2, '#0D9488': 1, '#64748B': 0,
  }
  // Track canonical direction for each bidirectional group key
  const edgeGroupDir = new Map<string, [string, string]>()
  const edgeGroups = new Map<string, Relationship[]>()
  for (const r of relationships) {
    const src = resolveToNodeId(r.source_name)
    const tgt = resolveToNodeId(r.target_name)
    if (src === tgt) continue
    // Normalize key so A→B and B→A land in the same group
    const [a, b] = src < tgt ? [src, tgt] : [tgt, src]
    const key = `${a}||${b}`
    if (!edgeGroupDir.has(key)) edgeGroupDir.set(key, [src, tgt])
    const group = edgeGroups.get(key) ?? []
    group.push(r)
    edgeGroups.set(key, group)
  }
  const edges: Edge[] = []
  for (const [key, group] of edgeGroups) {
    const [src, tgt] = edgeGroupDir.get(key)!
    const colors = group.map(r => edgeColor(r.relationship_type))
    const color = colors.reduce((best, c) => (COLOR_PRIORITY[c] ?? 0) > (COLOR_PRIORITY[best] ?? 0) ? c : best)
    const label = group.map(r => r.relationship_type.replace(/_/g, ' ')).join(' · ')
    edges.push({
      id: group.map(r => r.relationship_id).join('||'),
      source: src,
      target: tgt,
      label,
      type: 'bezier',
      style: { stroke: color, strokeWidth: 2 },
      labelStyle: { fontSize: 11, fill: '#0F172A', fontWeight: 700 },
      labelBgStyle: { fill: '#FFFFFF', fillOpacity: 1 },
      labelBgPadding: [6, 4] as [number, number],
      labelBgBorderRadius: 6,
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
    })
  }

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

// ── Relationship detail side-panel ────────────────────────────────────────

function RelationshipDetail({
  relationships,
  docMap,
  onClose,
}: {
  relationships: Relationship[]
  docMap: Record<string, string>
  onClose: () => void
}) {
  return (
    <aside className="w-64 shrink-0 bg-panel border-l border-border flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full self-start text-slate-500 bg-slate-100 border border-slate-200">
            {relationships.length === 1 ? 'Relationship' : `${relationships.length} Relationships`}
          </span>
          <p className="text-xs font-bold text-text leading-snug break-words">
            {relationships[0].source_name} → {relationships[0].target_name}
          </p>
        </div>
        <button onClick={onClose} className="shrink-0 text-text-mute hover:text-text mt-0.5 transition-colors" aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-5">
        {relationships.map((rel, i) => {
          const evidence = rel.evidence ?? {}
          const docIds: string[] = Array.isArray(evidence.document_ids)
            ? (evidence.document_ids as string[])
            : evidence.document_id ? [evidence.document_id as string] : []
          const extraEntries = Object.entries(evidence).filter(
            ([k]) => !['source_type', 'target_type', 'document_id', 'document_ids'].includes(k)
          )
          const color = edgeColor(rel.relationship_type)
          return (
            <div key={rel.relationship_id} className={`flex flex-col gap-2 ${i > 0 ? 'pt-4 border-t border-border' : ''}`}>
              <div className="flex items-center gap-2">
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }} />
                <span className="text-xs font-bold text-text">{rel.relationship_type.replace(/_/g, ' ')}</span>
              </div>
              {docIds.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Evidence from</p>
                  {docIds.map(id => (
                    <span key={id} className="text-[10px] bg-panel-2 border border-border text-text-mid px-2 py-0.5 rounded-full truncate" title={docMap[id] ?? id}>
                      {docMap[id] ?? id}
                    </span>
                  ))}
                </div>
              )}
              {extraEntries.length > 0 && (
                <div className="flex flex-col gap-1">
                  {extraEntries.map(([k, v]) => (
                    <div key={k} className="flex flex-col gap-0.5">
                      <span className="text-[10px] font-medium text-text-mute capitalize">{k.replace(/_/g, ' ')}</span>
                      <span className="text-xs text-text">{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </aside>
  )
}

// ── Main panel ─────────────────────────────────────────────────────────────

export default function EntityGraphPanel({
  caseId,
  docs = [],
  onRunAnalysis,
  analysisState,
}: {
  caseId: string
  docs?: CaseDocument[]
  onRunAnalysis?: () => void
  analysisState?: string
}) {
  const [data, setData] = useState<{ entities: Entity[]; relationships: Relationship[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [selectedRelationships, setSelectedRelationships] = useState<Relationship[] | null>(null)
  const [statsOpen, setStatsOpen] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [pendingConnection, setPendingConnection] = useState<Connection | null>(null)
  const [pendingLabel, setPendingLabel] = useState('')
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const rfRef = useRef<ReactFlowInstance | null>(null)
  const docMap = useMemo(
    () => Object.fromEntries(docs.map(d => [d.document_id, d.filename])),
    [docs],
  )

  function fitAfterLoad() {
    setTimeout(() => rfRef.current?.fitView({ padding: 0.3, maxZoom: 0.85, duration: 400 }), 80)
  }

  useEffect(() => {
    Promise.all([
      fetchEntities(caseId),
      fetchGraphState(caseId),
    ])
      .then(async ([d, savedState]) => {
        setData(d)
        const { nodes: n, edges: e } = await buildGraph(d.entities, d.relationships)

        // Apply saved node positions if available
        const pos = savedState?.node_positions ?? {}
        const positioned = Object.keys(pos).length > 0
          ? n.map(node => pos[node.id] ? { ...node, position: pos[node.id] } : node)
          : n

        // Restore manually drawn edges
        const manualEdges: Edge[] = (savedState?.manual_edges ?? []).map(me => ({
          ...me,
          type: 'bezier',
          ...(me.label ? {
            labelStyle: { fontSize: 11, fill: '#0F172A', fontWeight: 700 },
            labelBgStyle: { fill: '#FFFFFF', fillOpacity: 1 },
            labelBgPadding: [6, 4] as [number, number],
            labelBgBorderRadius: 6,
          } : {}),
          style: { stroke: '#94A3B8', strokeWidth: 2, strokeDasharray: '6,3' },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#94A3B8', width: 16, height: 16 },
        }))

        setNodes(positioned)
        setEdges([...e, ...manualEdges])
        if (Object.keys(pos).length === 0) fitAfterLoad()
      })
      .catch(() => setError('Failed to load entity graph.'))
  }, [caseId, setNodes, setEdges])

  const entityMap = useMemo(
    () => Object.fromEntries((data?.entities ?? []).map(e => [e.canonical_name, e])),
    [data],
  )

  const relationshipMap = useMemo(
    () => Object.fromEntries((data?.relationships ?? []).map(r => [r.relationship_id, r])),
    [data],
  )

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedRelationships(null)
      setSelectedEntity((node.data.entity as Entity) ?? entityMap[node.id] ?? null)
    },
    [entityMap],
  )

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      const rels = edge.id.split('||').map(id => relationshipMap[id]).filter(Boolean) as Relationship[]
      if (rels.length > 0) {
        setSelectedEntity(null)
        setSelectedRelationships(rels)
      }
    },
    [relationshipMap],
  )

  const onPaneClick = useCallback(() => { setSelectedEntity(null); setSelectedRelationships(null) }, [])

  const onConnect = useCallback(
    (connection: Connection) => {
      setPendingConnection(connection)
      setPendingLabel('')
    },
    [],
  )

  function confirmEdge() {
    if (!pendingConnection) return
    const label = pendingLabel.trim() || 'related to'
    setEdges(eds => addEdge({
      ...pendingConnection,
      id: `manual-${Date.now()}`,
      type: 'bezier',
      label,
      labelStyle: { fontSize: 11, fill: '#0F172A', fontWeight: 700 },
      labelBgStyle: { fill: '#FFFFFF', fillOpacity: 1 },
      labelBgPadding: [6, 4] as [number, number],
      labelBgBorderRadius: 6,
      style: { stroke: '#94A3B8', strokeWidth: 2, strokeDasharray: '6,3' },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#94A3B8', width: 16, height: 16 },
    }, eds))
    setPendingConnection(null)
    setPendingLabel('')
  }

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
          onEdgeClick={onEdgeClick}
          onPaneClick={onPaneClick}
          onConnect={onConnect}
          onInit={(instance) => { rfRef.current = instance }}
          fitView
          fitViewOptions={{ padding: 0.35, maxZoom: 1.1 }}
          minZoom={0.1}
          maxZoom={3}
          nodesDraggable
          nodesConnectable={editMode}
          elementsSelectable
          deleteKeyCode={editMode ? 'Delete' : null}
          edgesFocusable
          elevateEdgesOnSelect
        >
          <Background color="#E2E8F0" gap={24} size={1.5} />
          <Controls showInteractive={false} style={{ bottom: 60, left: 16 }} />
          {/* Legend */}
          {presentTypes.length > 0 && (
            <div
              style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, background: 'rgba(255,255,255,0.97)', border: '1px solid #E2E8F0', borderRadius: 12, padding: '10px 14px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', backdropFilter: 'blur(4px)', minWidth: 130 }}
            >
              <p style={{ fontSize: 9, fontWeight: 800, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 8 }}>Entity Types</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {presentTypes.map(([, cfg]) => (
                  <div key={cfg.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 11, color: '#475569', fontWeight: 600 }}>{cfg.label}</span>
                  </div>
                ))}
              </div>
              <div style={{ height: 1, background: '#F1F5F9', margin: '10px 0' }} />
              <p style={{ fontSize: 9, fontWeight: 800, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 8 }}>Relationship Types</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { color: '#EF4444', label: 'Conflict / Fraud' },
                  { color: '#F97316', label: 'Ownership / Family' },
                  { color: '#D97706', label: 'Financial' },
                  { color: '#7C3AED', label: 'Contract / Approval' },
                  { color: '#0D9488', label: 'Employment' },
                  { color: '#64748B', label: 'Other' },
                ].map(e => (
                  <div key={e.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 18, height: 2, background: e.color, borderRadius: 1, flexShrink: 0 }} />
                    <span style={{ fontSize: 11, color: '#475569', fontWeight: 600 }}>{e.label}</span>
                  </div>
                ))}
              </div>
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
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
              </svg>
            </button>
            <button
              onClick={() => {
                if (editMode) {
                  // Save layout when exiting edit mode
                  const node_positions: Record<string, { x: number; y: number }> = {}
                  nodes.forEach(n => { node_positions[n.id] = n.position })
                  const manual_edges = edges
                    .filter(e => e.id.startsWith('manual-'))
                    .map(e => ({ id: e.id, source: e.source, target: e.target, label: e.label as string | undefined }))
                  saveGraphState(caseId, { node_positions, manual_edges }).catch(() => { })
                }
                setEditMode(v => !v)
              }}
              title={editMode ? 'Exit edit mode and save layout' : 'Enter edit mode — drag handles to connect, × to delete'}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', fontSize: 12, fontWeight: 600,
                borderRadius: 12, cursor: 'pointer',
                background: editMode ? '#F59E0B' : 'rgba(255,255,255,0.95)',
                color: editMode ? '#fff' : '#475569',
                border: editMode ? '1px solid #D97706' : '1px solid #E2E8F0',
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                transition: 'background 0.15s, color 0.15s',
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
              </svg>
              {editMode ? 'Done editing' : 'Edit graph'}
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

      {/* Relationship detail panel */}
      {selectedRelationships && !selectedEntity && (
        <RelationshipDetail
          relationships={selectedRelationships}
          docMap={docMap}
          onClose={() => setSelectedRelationships(null)}
        />
      )}

      {/* Edge label prompt */}
      {pendingConnection && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={() => setPendingConnection(null)}
        >
          <div
            style={{
              background: '#fff', borderRadius: 14, padding: '20px 24px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.18)', width: 320,
              display: 'flex', flexDirection: 'column', gap: 14,
            }}
            onClick={e => e.stopPropagation()}
          >
            <div>
              <p style={{ fontSize: 13, fontWeight: 700, color: '#0F172A', margin: 0 }}>Name this relationship</p>
              <p style={{ fontSize: 11, color: '#94A3B8', margin: '4px 0 0' }}>Describe how these two entities are connected</p>
            </div>
            <input
              autoFocus
              type="text"
              value={pendingLabel}
              onChange={e => setPendingLabel(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') confirmEdge(); if (e.key === 'Escape') setPendingConnection(null) }}
              placeholder="e.g. Owner, Director, Supplier, Approved by…"
              style={{
                border: '1.5px solid #E2E8F0', borderRadius: 8, padding: '8px 12px',
                fontSize: 13, color: '#0F172A', outline: 'none', width: '100%', boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setPendingConnection(null)}
                style={{
                  padding: '7px 16px', fontSize: 12, fontWeight: 600,
                  background: 'transparent', border: '1px solid #E2E8F0',
                  borderRadius: 8, cursor: 'pointer', color: '#64748B',
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmEdge}
                style={{
                  padding: '7px 16px', fontSize: 12, fontWeight: 600,
                  background: '#0D9488', border: 'none',
                  borderRadius: 8, cursor: 'pointer', color: '#fff',
                }}
              >
                Add connection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
