import axios from 'axios'
import type { Case, CasesListResponse, CreateCasePayload } from './types'

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
