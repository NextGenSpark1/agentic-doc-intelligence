import axios from 'axios'
import type { Case, CasesListResponse, CreateCasePayload, Document as CaseDocument, Extraction, ChatResponse, Finding, TimelineEvent, Entity, Relationship, DocumentChunk, OrgContext, OrgMember, Organisation, InvitationPreview } from './types'

type CasePatch = Partial<Pick<Case, 'title' | 'case_type' | 'status' | 'lead_investigator' | 'allegation_summary' | 'schema_fields'>>
import { supabase } from './lib/supabaseClient'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Timeout after 15s to surface backend-not-running errors quickly
  timeout: 15_000,
})

// Attach the current Supabase session token to every request automatically
client.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export async function fetchCases(): Promise<CasesListResponse> {
  const response = await client.get<CasesListResponse>('/cases')
  return response.data
}

export async function createCase(payload: CreateCasePayload): Promise<Case> {
  const response = await client.post<Case>('/cases', payload)
  return response.data
}

export async function fetchCase(id: string): Promise<Case> {
  const response = await client.get<Case>(`/cases/${id}`)
  return response.data
}

export async function updateCase(id: string, patch: CasePatch): Promise<Case> {
  const response = await client.patch<Case>(`/cases/${id}`, patch)
  return response.data
}

export async function deleteCase(caseId: string): Promise<void> {
  await client.delete(`/cases/${caseId}`)
}

export async function fetchDocuments(caseId: string): Promise<CaseDocument[]> {
  const response = await client.get(`/cases/${caseId}/documents`)
  return (response.data as { documents: CaseDocument[] }).documents
}

export async function deleteDocument(caseId: string, documentId: string): Promise<void> {
  await client.delete(`/cases/${caseId}/documents/${documentId}`)
}

export async function fetchExtraction(caseId: string, documentId: string): Promise<Extraction | null> {
  try {
    const response = await client.get<Extraction>(`/cases/${caseId}/documents/${documentId}/extraction`)
    return response.data
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 404) return null
    throw err
  }
}

export async function fetchDocumentChunks(caseId: string, documentId: string): Promise<DocumentChunk[]> {
  const response = await client.get<{ chunks: DocumentChunk[] }>(`/cases/${caseId}/documents/${documentId}/chunks`)
  return response.data.chunks
}

export async function fetchSummary(caseId: string, documentId: string): Promise<{ summary: string } | null> {
  try {
    const response = await client.get<{ summary: string }>(`/cases/${caseId}/documents/${documentId}/summary`)
    return response.data
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 404) return null
    throw err
  }
}

export async function fetchFileUrl(caseId: string, documentId: string): Promise<string> {
  const response = await client.get<{ url: string }>(`/cases/${caseId}/documents/${documentId}/file-url`)
  return response.data.url
}

export async function extractDocument(caseId: string, documentId: string): Promise<void> {
  await client.post(`/cases/${caseId}/documents/${documentId}/extract`)
}

export async function uploadDocument(caseId: string, file: File): Promise<CaseDocument> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post<CaseDocument>(
    `/cases/${caseId}/documents`,
    formData,
    { headers: { 'Content-Type': undefined }, timeout: 60_000 },
  )
  return response.data
}

export async function fetchEntities(
  caseId: string,
): Promise<{ entities: Entity[]; relationships: Relationship[] }> {
  const response = await client.get<{ entities: Entity[]; relationships: Relationship[] }>(
    `/cases/${caseId}/entities`,
  )
  return response.data
}

export async function fetchTimeline(caseId: string): Promise<TimelineEvent[]> {
  const response = await client.get<{ events: TimelineEvent[] }>(`/cases/${caseId}/timeline`)
  return response.data.events
}

export async function createTimelineEvent(caseId: string, data: { event_date: string; label: string; document_id?: string | null }): Promise<TimelineEvent> {
  const response = await client.post<TimelineEvent>(`/cases/${caseId}/timeline`, data)
  return response.data
}

export async function updateTimelineEvent(caseId: string, eventId: string, data: { event_date?: string; label?: string; document_id?: string | null }): Promise<TimelineEvent> {
  const response = await client.patch<TimelineEvent>(`/cases/${caseId}/timeline/${eventId}`, data)
  return response.data
}

export async function deleteTimelineEvent(caseId: string, eventId: string): Promise<void> {
  await client.delete(`/cases/${caseId}/timeline/${eventId}`)
}

export interface ReportOptions {
  sections?: string[]
  instructions?: string
}

export async function generateReport(caseId: string, options?: ReportOptions): Promise<{ markdown: string; finding_count: number }> {
  const response = await client.post<{ markdown: string; finding_count: number }>(`/cases/${caseId}/report`, options ?? {})
  return response.data
}

export async function runCaseAnalysis(caseId: string): Promise<void> {
  await client.post(`/cases/${caseId}/analysis`)
}

export async function fetchFindings(caseId: string): Promise<Finding[]> {
  const response = await client.get<{ findings: Finding[] }>(`/cases/${caseId}/findings`)
  return response.data.findings
}

export async function reviewFinding(
  findingId: string,
  status: 'confirmed' | 'dismissed' | 'pending',
  reviewedBy: string,
  dismissalReason?: string,
): Promise<Finding> {
  const response = await client.patch<Finding>(`/findings/${findingId}/review`, {
    status,
    reviewed_by: reviewedBy,
    dismissal_reason: dismissalReason ?? null,
  })
  return response.data
}

export async function sendChatMessage(
  caseId: string,
  message: string,
  history: Array<{ role: string; content: string }>,
): Promise<ChatResponse> {
  const response = await client.post<ChatResponse>(`/cases/${caseId}/chat`, {
    message,
    scope: 'case',
    context_id: caseId,
    history,
  })
  return response.data
}

export interface GraphState {
  node_positions: Record<string, { x: number; y: number }>
  manual_edges: Array<{ id: string; source: string; target: string; label?: string }>
}

export async function fetchGraphState(caseId: string): Promise<GraphState | null> {
  try {
    const response = await client.get<GraphState>(`/cases/${caseId}/graph-state`)
    const s = response.data
    if (!s || !s.node_positions) return null
    return s
  } catch {
    return null
  }
}

export async function saveGraphState(caseId: string, state: GraphState): Promise<void> {
  await client.put(`/cases/${caseId}/graph-state`, state)
}

// ── Org / multi-tenancy ────────────────────────────────────────────────────

export async function fetchMyOrg(): Promise<OrgContext> {
  const res = await client.get<OrgContext>('/orgs/me')
  return res.data
}

export async function fetchOrgMembers(orgId: string): Promise<{ members: OrgMember[] }> {
  const res = await client.get<{ members: OrgMember[] }>(`/orgs/${orgId}/members`)
  return res.data
}

export async function inviteMember(orgId: string, email: string, role: string, name?: string): Promise<{ invite_link: string; invite_token: string; email: string; role: string; email_sent: boolean }> {
  const res = await client.post(`/orgs/${orgId}/invite`, { email, role, name })
  return res.data
}

export async function removeMember(orgId: string, userId: string): Promise<void> {
  await client.delete(`/orgs/${orgId}/members/${userId}`)
}

export async function fetchInvitation(token: string): Promise<InvitationPreview> {
  const res = await client.get<InvitationPreview>(`/invitations/${token}`)
  return res.data
}

export async function acceptInvitation(token: string): Promise<{ org_id: string; org_name: string; role: string }> {
  const res = await client.post(`/invitations/${token}/accept`)
  return res.data
}

// Platform admin
export async function platformListOrgs(): Promise<{ orgs: Organisation[] }> {
  const res = await client.get<{ orgs: Organisation[] }>('/platform/orgs')
  return res.data
}

export async function platformCreateOrg(name: string, plan: string, adminEmail: string, adminName?: string): Promise<{ org: Organisation; invite_link: string; invite_token: string }> {
  const res = await client.post('/platform/orgs', { name, plan, admin_email: adminEmail, admin_name: adminName })
  return res.data
}

export async function platformDeleteOrg(orgId: string): Promise<void> {
  await client.delete(`/platform/orgs/${orgId}`)
}

export async function platformUpdateOrg(orgId: string, fields: { plan?: string; status?: string }): Promise<Organisation> {
  const res = await client.patch<Organisation>(`/platform/orgs/${orgId}`, fields)
  return res.data
}

export async function uploadDocumentWithProgress(
  caseId: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<CaseDocument> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post<CaseDocument>(
    `/cases/${caseId}/documents`,
    formData,
    {
      headers: { 'Content-Type': undefined },
      timeout: 60_000,
      onUploadProgress: (e) => {
        if (e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    },
  )
  return response.data
}
