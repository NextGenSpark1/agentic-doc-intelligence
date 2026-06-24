import axios from 'axios'
import type { Case, CasesListResponse, CreateCasePayload, Document as CaseDocument, Extraction } from './types'

const BASE_URL = 'http://localhost:8000'

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Timeout after 15s to surface backend-not-running errors quickly
  timeout: 15_000,
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

export async function uploadDocument(caseId: string, file: File): Promise<CaseDocument> {
  const formData = new FormData()
  formData.append('file', file)
  // Use axios directly (not client) so Content-Type is unset and browser sets multipart boundary
  const response = await axios.post<CaseDocument>(
    `${BASE_URL}/cases/${caseId}/documents`,
    formData,
    { timeout: 60_000 },
  )
  return response.data
}
