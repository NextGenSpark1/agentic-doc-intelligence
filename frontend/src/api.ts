import axios from 'axios'
import type { Case, CasesListResponse, CreateCasePayload, Document as CaseDocument, Extraction, ChatResponse, Finding, TimelineEvent, Entity, Relationship, DocumentChunk } from './types'

type CasePatch = Partial<Pick<Case, 'title' | 'case_type' | 'status' | 'lead_investigator' | 'allegation_summary' | 'schema_fields'>>
import { supabase } from './lib/supabaseClient'

const BASE_URL = 'http://localhost:8000'

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

export async function generateReport(caseId: string): Promise<{ markdown: string; finding_count: number }> {
  const response = await client.post<{ markdown: string; finding_count: number }>(`/cases/${caseId}/report`)
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
  status: 'confirmed' | 'dismissed',
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
