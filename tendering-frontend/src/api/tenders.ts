import axios from 'axios';
import type {
  TenderWorkspace,
  WorkspaceDocument,
  Requirement,
  BidDecisionReport,
  LibraryDocument,
  DashboardStats,
  OrgMember,
  EvidenceLink,
} from '../types';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

api.interceptors.request.use((config) => {
  const session = localStorage.getItem('sb-session');
  if (session) {
    try {
      const { access_token } = JSON.parse(session);
      config.headers.Authorization = `Bearer ${access_token}`;
    } catch {
      // no valid session
    }
  }
  return config;
});

// ─── API functions ────────────────────────────────────────────────────────────

export const getWorkspaces = (): Promise<TenderWorkspace[]> =>
  api.get<TenderWorkspace[]>('/tendering/workspaces').then((response) => response.data);

export const getWorkspace = (id: string): Promise<TenderWorkspace> =>
  api.get<TenderWorkspace>(`/tendering/workspaces/${id}`).then((response) => response.data);

export const getRequirements = (tenderId: string): Promise<Requirement[]> =>
  api.get<Requirement[]>(`/tendering/workspaces/${tenderId}/requirements`).then((response) => response.data);

export const getBidDecision = (tenderId: string): Promise<BidDecisionReport | null> =>
  api.get<BidDecisionReport | null>(`/tendering/workspaces/${tenderId}/bid-decision`).then((response) => response.data);

// Generates a fresh recommendation from the current evidence position and stores it. No mock
// fallback: a recommendation that did not come from the backend is exactly the kind of thing
// nobody should be reading off this screen. The team's own bid/no-bid stays with updateWorkspace.
export const generateBidDecision = (tenderId: string): Promise<BidDecisionReport> =>
  api
    .post<BidDecisionReport>(`/tendering/workspaces/${tenderId}/generate-bid-decision`)
    .then((response) => response.data);

export const getDashboardStats = (): Promise<DashboardStats> =>
  api.get<DashboardStats>('/tendering/stats').then((response) => response.data);

export const getLibraryDocuments = (): Promise<LibraryDocument[]> =>
  api.get<LibraryDocument[]>('/tendering/library').then((response) => response.data);

export const getEvidenceLinks = (workspaceId: string): Promise<EvidenceLink[]> =>
  api.get<EvidenceLink[]>(`/tendering/workspaces/${workspaceId}/evidence-links`).then((response) => response.data);

export const reviewEvidenceLink = (linkId: string, status: 'confirmed' | 'dismissed'): Promise<void> =>
  api.patch(`/tendering/evidence-links/${linkId}`, { status }).then(() => undefined);

export const createWorkspace = (data: {
  title: string;
  reference?: string;
  buyer?: string;
  category?: string;
  closing_date?: string;
  contract_value?: number;
  currency?: string;
}): Promise<TenderWorkspace> =>
  api.post<TenderWorkspace>('/tendering/workspaces', data).then((response) => response.data);

export const updateWorkspace = (
  id: string,
  patch: Partial<Pick<TenderWorkspace, 'bid_decision' | 'stage' | 'title' | 'reference' | 'buyer' | 'category' | 'closing_date' | 'contract_value' | 'currency' | 'readiness_score' | 'description' | 'team_members'>>,
): Promise<TenderWorkspace> =>
  api.patch<TenderWorkspace>(`/tendering/workspaces/${id}`, patch).then((response) => response.data);

export const fetchMyTeam = (orgId?: string): Promise<OrgMember[]> =>
  api.get<OrgMember[]>('/tendering/my-team', { params: orgId ? { org_id: orgId } : {} }).then((response) => response.data);

export const updateRequirement = (
  reqId: string,
  patch: { status?: Requirement['status']; owner?: string; notes?: string },
): Promise<Requirement> =>
  api.patch<Requirement>(`/tendering/requirements/${reqId}`, patch).then((response) => response.data);

export const addWorkspaceDocument = (
  workspaceId: string,
  data: { name: string; category?: string; file_type?: string; size_bytes?: number; url?: string; storage_path?: string },
): Promise<WorkspaceDocument> =>
  api.post<WorkspaceDocument>(`/tendering/workspaces/${workspaceId}/documents`, data).then((response) => response.data);

export const extractWorkspaceDocument = (workspaceId: string, docId: string): Promise<{ status: string }> =>
  api.post<{ status: string }>(`/tendering/workspaces/${workspaceId}/documents/${docId}/extract`).then((r) => r.data);

export const deleteWorkspace = (workspaceId: string): Promise<void> =>
  api.delete(`/tendering/workspaces/${workspaceId}`).then(() => undefined);

export const deleteWorkspaceDocument = (workspaceId: string, docId: string): Promise<void> =>
  api.delete(`/tendering/workspaces/${workspaceId}/documents/${docId}`).then(() => undefined);

export const getDocumentExtraction = (workspaceId: string, docId: string): Promise<{ markdown: string }> =>
  api.get<{ markdown: string }>(`/tendering/workspaces/${workspaceId}/documents/${docId}/extraction`).then((r) => r.data);

export const analyseWorkspace = (workspaceId: string): Promise<{ status: string }> =>
  api.post<{ status: string }>(`/tendering/workspaces/${workspaceId}/analyse`).then((r) => r.data);

export const generateBidDecision = (workspaceId: string): Promise<BidDecisionReport> =>
  api.post<BidDecisionReport>(`/tendering/workspaces/${workspaceId}/generate-bid-decision`).then((r) => r.data);

export const addLibraryDocument = (data: {
  title: string;
  filename?: string;
  category?: string;
  file_type?: string;
  expiry_date?: string;
  url?: string;
  storage_path?: string;
}): Promise<LibraryDocument> =>
  api.post<LibraryDocument>('/tendering/library', data).then((response) => response.data);

export const deleteLibraryDocument = (docId: string): Promise<void> =>
  api.delete(`/tendering/library/${docId}`).then(() => undefined);

// storage_path is what the backend actually downloads — without it a replacement updates the
// preview only, and Extract goes on reading the previous file.
export const replaceLibraryDocument = (docId: string, data: { url: string; filename?: string; storage_path?: string }): Promise<LibraryDocument> =>
  api.patch<LibraryDocument>(`/tendering/library/${docId}`, data).then((r) => r.data);

export const extractLibraryDocument = (docId: string): Promise<{ status: string }> =>
  api.post<{ status: string }>(`/tendering/library/${docId}/extract`).then((r) => r.data);

export const getLibraryDocumentExtraction = (docId: string): Promise<{ text: string; chunk_count: number }> =>
  api.get<{ text: string; chunk_count: number }>(`/tendering/library/${docId}/extraction`).then((r) => r.data);

export const verifyLibraryDocument = (docId: string): Promise<LibraryDocument> =>
  api.patch<LibraryDocument>(`/tendering/library/${docId}`, { verification_status: 'verified' }).then((r) => r.data);

export interface ChatCitation {
  document_id: string;
  page: number;
  quoted_text: string;
  chunk_id: string;
}

export interface ChatResponse {
  answer: string;
  citations: ChatCitation[];
}

export const chatWithWorkspace = (
  workspaceId: string,
  message: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }>,
): Promise<ChatResponse> =>
  api
    .post<ChatResponse>(`/tendering/workspaces/${workspaceId}/chat`, { message, history })
    .then((r) => r.data);
