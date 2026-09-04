import axios from 'axios';
import type {
  TenderWorkspace,
  WorkspaceDocument,
  Requirement,
  BidDecisionReport,
  LibraryDocument,
  DashboardStats,
  OrgMember,
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

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_WORKSPACES: TenderWorkspace[] = [
  {
    id: 'ws1',
    org_id: 'org1',
    title: 'National Broadband Infrastructure — Phase 3',
    reference: 'ICT/INFRA/2026/047',
    buyer: 'Ministry of ICT & Digital Economy',
    category: 'Telecommunications',
    closing_date: '2026-09-15',
    contract_value: 12500000,
    currency: 'USD',
    stage: 'preparing',
    bid_decision: 'bid',
    readiness_score: 72,
    requirements_count: 10,
    requirements_met: 6,
    requirements_gap: 3,
    requirements_partial: 1,
    description:
      'Design, supply, installation, and commissioning of a national broadband backbone network covering 47 districts. Includes fibre optic infrastructure, last-mile connectivity, and a 24/7 managed NOC.',
    documents: [
      { id: 'd1', name: 'RFP_ICT047_v2.pdf', url: '#', size_bytes: 4800000, uploaded_at: '2026-08-02T09:00:00Z' },
      { id: 'd2', name: 'Technical_Specifications.pdf', url: '#', size_bytes: 2100000, uploaded_at: '2026-08-02T09:05:00Z' },
      { id: 'd3', name: 'BOQ_Annex_C.xlsx', url: '#', size_bytes: 380000, uploaded_at: '2026-08-03T11:30:00Z' },
    ],
    team_members: ['Amina Al-Rashid', 'David Osei', 'Sarah Kim', 'Nawran Al-Hamdi'],
    created_at: '2026-08-01T00:00:00Z',
  },
  {
    id: 'ws2',
    org_id: 'org1',
    title: 'Hospital Management Information System — 12 Facilities',
    reference: 'MOH/IT/2026/031',
    buyer: 'Ministry of Health',
    category: 'IT & Software',
    closing_date: '2026-08-30',
    contract_value: 450000,
    currency: 'USD',
    stage: 'analysing',
    bid_decision: 'pending',
    readiness_score: 45,
    requirements_count: 8,
    requirements_met: 3,
    requirements_gap: 2,
    requirements_partial: 3,
    description:
      'Supply, installation, configuration, and maintenance of an integrated HMIS covering patient records, pharmacy, laboratory, billing, and reporting for 12 regional hospitals.',
    documents: [
      { id: 'd4', name: 'MOH_RFP_031.pdf', url: '#', size_bytes: 3200000, uploaded_at: '2026-08-05T10:00:00Z' },
      { id: 'd5', name: 'HL7_FHIR_Requirements.pdf', url: '#', size_bytes: 890000, uploaded_at: '2026-08-05T10:10:00Z' },
    ],
    team_members: ['David Osei', 'Fatima Hassan'],
    created_at: '2026-08-04T00:00:00Z',
  },
  {
    id: 'ws3',
    org_id: 'org1',
    title: 'Urban Transit Electrification — Metro Line 4',
    reference: 'CTA/ELEC/2026/012',
    buyer: 'City Transport Authority',
    category: 'Infrastructure',
    closing_date: '2026-10-05',
    contract_value: 8500000,
    currency: 'USD',
    stage: 'new',
    bid_decision: 'pending',
    readiness_score: 12,
    requirements_count: 14,
    requirements_met: 1,
    requirements_gap: 8,
    requirements_partial: 5,
    description:
      'Design and build electrification infrastructure for the 28km Metro Line 4 extension, including overhead catenary systems, substations, and integration with existing SCADA.',
    documents: [
      { id: 'd6', name: 'CTA_Tender_012.pdf', url: '#', size_bytes: 6100000, uploaded_at: '2026-08-09T14:00:00Z' },
    ],
    team_members: ['Amina Al-Rashid'],
    created_at: '2026-08-08T00:00:00Z',
  },
  {
    id: 'ws4',
    org_id: 'org1',
    title: 'Digital Classrooms Programme — 200 Schools',
    reference: 'MOE/DIG/2026/089',
    buyer: 'Ministry of Education',
    category: 'IT & Education',
    closing_date: '2026-09-01',
    contract_value: 2200000,
    currency: 'USD',
    stage: 'submitted',
    bid_decision: 'bid',
    readiness_score: 100,
    requirements_count: 7,
    requirements_met: 7,
    requirements_gap: 0,
    requirements_partial: 0,
    description:
      'Supply and installation of interactive digital classroom systems for 200 public schools, including smart boards, student tablets, teacher workstations, and connectivity.',
    documents: [
      { id: 'd7', name: 'MOE_RFP_089.pdf', url: '#', size_bytes: 2700000, uploaded_at: '2026-07-28T08:00:00Z' },
      { id: 'd8', name: 'Technical_Annex_A.pdf', url: '#', size_bytes: 1400000, uploaded_at: '2026-07-28T08:15:00Z' },
    ],
    team_members: ['Sarah Kim', 'David Osei', 'Fatima Hassan'],
    created_at: '2026-07-27T00:00:00Z',
  },
  {
    id: 'ws5',
    org_id: 'org1',
    title: 'Desalination Plant O&M Contract — Northern Zone',
    reference: 'WA/OAM/2025/156',
    buyer: 'National Water Authority',
    category: 'Energy & Utilities',
    closing_date: '2026-07-31',
    contract_value: 3800000,
    currency: 'USD',
    stage: 'lost',
    bid_decision: 'bid',
    readiness_score: 88,
    requirements_count: 9,
    requirements_met: 8,
    requirements_gap: 0,
    requirements_partial: 1,
    description:
      'Operations and maintenance of two desalination plants with combined capacity of 120,000 m³/day, including preventive maintenance, chemical dosing, and 24/7 operations staffing.',
    documents: [
      { id: 'd9', name: 'WA_Tender_156.pdf', url: '#', size_bytes: 5200000, uploaded_at: '2026-07-01T07:00:00Z' },
    ],
    team_members: ['Amina Al-Rashid', 'Nawran Al-Hamdi'],
    created_at: '2026-06-30T00:00:00Z',
  },
];

const MOCK_REQUIREMENTS: Record<string, Requirement[]> = {
  ws1: [
    {
      req_id: 'r1', tender_id: 'ws1',
      description: 'ISO 9001:2015 Quality Management System certification',
      category: 'certification', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 23, clause: '4.2.1',
      confidence: 97, status: 'met', owner: 'Compliance Team',
      notes: 'Valid certificate on file — expires Jun 2027.',
      matched_doc_ids: ['d-iso9001'],
    },
    {
      req_id: 'r2', tender_id: 'ws1',
      description: 'Minimum 10 years of experience in large-scale telecommunications infrastructure projects',
      category: 'experience', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 25, clause: '4.3.2',
      confidence: 91, status: 'met', owner: 'Business Development',
      notes: 'Portfolio confirms 14 years with 8 comparable projects.',
      matched_doc_ids: ['d-portfolio'],
    },
    {
      req_id: 'r3', tender_id: 'ws1',
      description: 'Local workforce participation ≥ 40% of total project headcount',
      category: 'legal', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 28, clause: '5.1.a',
      confidence: 88, status: 'gap', owner: 'HR',
      notes: 'Current plan is 28% — 12% below threshold. Subcontracting plan under revision.',
    },
    {
      req_id: 'r4', tender_id: 'ws1',
      description: 'Performance bond equal to 5% of contract value, valid for project duration',
      category: 'financial', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 31, clause: '6.2',
      confidence: 94, status: 'partial', owner: 'Finance',
      notes: 'Bank can issue bond — written confirmation pending for this contract size.',
      matched_doc_ids: ['d-bankguarantee'],
    },
    {
      req_id: 'r5', tender_id: 'ws1',
      description: 'Valid Telecommunications Regulatory Commission (TRC) Class 1 operator license',
      category: 'legal', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 22, clause: '4.1.3',
      confidence: 99, status: 'met', owner: 'Legal',
      notes: 'TRC license valid until Jan 2027.',
      matched_doc_ids: ['d-trc'],
    },
    {
      req_id: 'r6', tender_id: 'ws1',
      description: 'Dedicated Project Manager with PMP certification and ≥8 years telecoms experience',
      category: 'personnel', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 26, clause: '4.4.1',
      confidence: 82, status: 'partial', owner: 'HR',
      notes: 'Have PMP-certified engineers but none with 8yr telecoms PM track record. External hire being considered.',
      matched_doc_ids: ['d-pmp'],
    },
    {
      req_id: 'r7', tender_id: 'ws1',
      description: '24/7 Network Operations Centre (NOC) with SLA-backed response time ≤15 min',
      category: 'technical', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 34, clause: '7.1',
      confidence: 90, status: 'gap', owner: 'Operations',
      notes: 'No owned NOC infrastructure. Partnership with TechOps Ltd under evaluation.',
    },
    {
      req_id: 'r8', tender_id: 'ws1',
      description: 'ISO/IEC 27001 Information Security Management certification or equivalent',
      category: 'certification', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 35, clause: '7.3',
      confidence: 78, status: 'gap', owner: 'IT Security',
      notes: 'Certificate expired Nov 2025. Recertification audit scheduled for Oct 2026.',
      matched_doc_ids: ['d-iso27001'],
    },
    {
      req_id: 'r9', tender_id: 'ws1',
      description: 'Annual turnover ≥ USD 25M for each of the past three financial years',
      category: 'financial', mandatory: true,
      source_doc: 'RFP_ICT047_v2.pdf', page: 30, clause: '6.1',
      confidence: 96, status: 'met', owner: 'Finance',
      notes: '3-year average turnover: USD 32.4M. Audited statements attached.',
      matched_doc_ids: ['d-fin2025', 'd-fin2024'],
    },
    {
      req_id: 'r10', tender_id: 'ws1',
      description: '5-year equipment warranty with in-country spare parts inventory ≥30 days coverage',
      category: 'technical', mandatory: false,
      source_doc: 'RFP_ICT047_v2.pdf', page: 38, clause: '8.4',
      confidence: 86, status: 'met', owner: 'Technical',
      notes: 'Standard hardware warranty offered; local warehouse partnership confirmed.',
      matched_doc_ids: ['d-portfolio'],
    },
  ],
  ws2: [
    {
      req_id: 'r11', tender_id: 'ws2',
      description: 'HL7 FHIR R4 compliant API for all clinical data exchange',
      category: 'technical', mandatory: true,
      source_doc: 'HL7_FHIR_Requirements.pdf', page: 4, clause: '2.1',
      confidence: 95, status: 'met', owner: 'Tech Lead',
      notes: 'Our HMIS platform is FHIR R4 certified as of Jan 2026.',
    },
    {
      req_id: 'r12', tender_id: 'ws2',
      description: 'Patient data must be stored exclusively within national data centre infrastructure',
      category: 'legal', mandatory: true,
      source_doc: 'MOH_RFP_031.pdf', page: 12, clause: '3.4',
      confidence: 88, status: 'partial', owner: 'Legal',
      notes: 'We use a regional cloud provider with in-country nodes — MoH legal review ongoing.',
    },
    {
      req_id: 'r13', tender_id: 'ws2',
      description: '24/7 SLA support with 4-hour on-site response for critical incidents',
      category: 'technical', mandatory: true,
      source_doc: 'MOH_RFP_031.pdf', page: 18, clause: '5.2',
      confidence: 91, status: 'partial', owner: 'Support',
      notes: 'Currently offer 8hr on-site; upgrading SLA tier for this bid.',
    },
    {
      req_id: 'r14', tender_id: 'ws2',
      description: 'Minimum 3 HMIS implementation references in public health sector',
      category: 'experience', mandatory: true,
      source_doc: 'MOH_RFP_031.pdf', page: 9, clause: '2.3',
      confidence: 82, status: 'met', owner: 'BD',
      notes: '5 comparable implementations available for reference.',
    },
    {
      req_id: 'r15', tender_id: 'ws2',
      description: 'Software escrow arrangement with approved third-party agent',
      category: 'legal', mandatory: false,
      source_doc: 'MOH_RFP_031.pdf', page: 21, clause: '6.1',
      confidence: 75, status: 'gap', owner: 'Legal',
      notes: 'No escrow arrangement currently in place. Legal to advise on options.',
    },
  ],
};

const MOCK_BID_DECISIONS: Record<string, BidDecisionReport> = {
  ws1: {
    tender_id: 'ws1',
    score: 68,
    recommendation: 'bid',
    rationale:
      'This opportunity aligns strongly with our core infrastructure capabilities. We have a proven 14-year track record in telecoms projects and meet 6 of 10 requirements outright. The three gaps — local workforce threshold, NOC infrastructure, and ISO 27001 recertification — are addressable before the September 15 deadline. The contract value of USD 12.5M and strategic relationship with the Ministry of ICT make this a high-priority pursuit.',
    strengths: [
      '14 years proven telecoms infrastructure experience with 8 comparable projects',
      'ISO 9001:2015 certified — directly covers a mandatory requirement',
      'Valid TRC Class 1 operator license on file',
      'Strong financial capacity (3yr avg turnover: USD 32.4M vs. USD 25M threshold)',
      'Existing relationship with Ministry of ICT from Phase 1 & 2 projects',
    ],
    risks: [
      'Local workforce at 28% — 12% below the 40% mandatory threshold',
      'ISO 27001 certificate expired Nov 2025 — recertification audit is Oct 2026, after closing date',
      'No owned NOC infrastructure — subcontractor arrangement needed within 5 weeks',
      'Dedicated PM with 8yr telecoms experience not yet identified',
    ],
    generated_at: '2026-08-09T16:45:00Z',
  },
  ws2: {
    tender_id: 'ws2',
    score: 55,
    recommendation: 'pending',
    rationale:
      'Our HMIS platform meets the core FHIR R4 requirement but data residency and on-site SLA need urgent clarification before a bid decision can be made. The 20-day window is tight. Recommend a go/no-go meeting by August 16.',
    strengths: [
      'FHIR R4 certified platform — direct match on the primary technical requirement',
      '5 public health HMIS references exceeds the 3-reference threshold',
      'Competitive pricing advantage in the USD 450K range',
    ],
    risks: [
      'Data residency requirement may not be fully satisfied by regional cloud provider',
      '4-hour on-site SLA exceeds our current support tier — cost and staffing implications',
      'Software escrow setup in 20 days is very tight',
    ],
    generated_at: '2026-08-07T11:00:00Z',
  },
};

const MOCK_LIBRARY: LibraryDocument[] = [
  {
    doc_id: 'd-reg',
    org_id: 'org1',
    category: 'registration',
    title: 'Company Registration Certificate',
    filename: 'company_registration_2022.pdf',
    issue_date: '2022-03-15',
    expiry_date: '2028-03-31',
    verification_status: 'verified',
    tags: ['incorporation', 'legal entity'],
    used_in_tenders: 4,
    uploaded_at: '2026-01-10T00:00:00Z',
  },
  {
    doc_id: 'd-iso9001',
    org_id: 'org1',
    category: 'certification',
    title: 'ISO 9001:2015 Quality Management Certificate',
    filename: 'ISO9001_cert_2024.pdf',
    issue_date: '2024-06-28',
    expiry_date: '2027-06-30',
    verification_status: 'verified',
    tags: ['quality', 'ISO', 'management system'],
    used_in_tenders: 3,
    uploaded_at: '2026-01-12T00:00:00Z',
  },
  {
    doc_id: 'd-fin2025',
    org_id: 'org1',
    category: 'financial',
    title: 'Audited Financial Statements 2025',
    filename: 'financial_statements_2025.pdf',
    issue_date: '2026-04-01',
    verification_status: 'verified',
    tags: ['financial', 'audit', '2025', 'turnover'],
    used_in_tenders: 3,
    uploaded_at: '2026-04-15T00:00:00Z',
  },
  {
    doc_id: 'd-fin2024',
    org_id: 'org1',
    category: 'financial',
    title: 'Audited Financial Statements 2024',
    filename: 'financial_statements_2024.pdf',
    issue_date: '2025-04-01',
    verification_status: 'verified',
    tags: ['financial', 'audit', '2024', 'turnover'],
    used_in_tenders: 3,
    uploaded_at: '2025-04-20T00:00:00Z',
  },
  {
    doc_id: 'd-portfolio',
    org_id: 'org1',
    category: 'technical',
    title: 'Project Experience Portfolio 2012–2026',
    filename: 'project_portfolio_2026.pdf',
    issue_date: '2026-07-01',
    verification_status: 'verified',
    tags: ['portfolio', 'experience', 'references', 'telecoms', 'infrastructure'],
    used_in_tenders: 4,
    uploaded_at: '2026-07-05T00:00:00Z',
  },
  {
    doc_id: 'd-pmp',
    org_id: 'org1',
    category: 'personnel',
    title: 'PMP-Certified Engineers Register',
    filename: 'pmp_engineers_register.pdf',
    issue_date: '2026-08-01',
    expiry_date: '2027-02-28',
    verification_status: 'pending',
    tags: ['PMP', 'engineers', 'personnel', 'certifications'],
    used_in_tenders: 2,
    uploaded_at: '2026-08-01T00:00:00Z',
  },
  {
    doc_id: 'd-trc',
    org_id: 'org1',
    category: 'registration',
    title: 'TRC Class 1 Telecommunications License',
    filename: 'TRC_license_2026.pdf',
    issue_date: '2024-01-15',
    expiry_date: '2027-01-15',
    verification_status: 'verified',
    tags: ['TRC', 'license', 'telecoms', 'regulatory'],
    used_in_tenders: 2,
    uploaded_at: '2026-01-20T00:00:00Z',
  },
  {
    doc_id: 'd-bankguarantee',
    org_id: 'org1',
    category: 'financial',
    title: 'Bank Guarantee Capability Letter',
    filename: 'bank_guarantee_letter.pdf',
    issue_date: '2026-07-20',
    verification_status: 'verified',
    tags: ['bank', 'guarantee', 'performance bond', 'financial capacity'],
    used_in_tenders: 2,
    uploaded_at: '2026-07-22T00:00:00Z',
  },
  {
    doc_id: 'd-iso27001',
    org_id: 'org1',
    category: 'certification',
    title: 'ISO/IEC 27001 Information Security Certificate',
    filename: 'ISO27001_cert_expired.pdf',
    issue_date: '2022-11-30',
    expiry_date: '2025-11-30',
    verification_status: 'expired',
    tags: ['ISO 27001', 'information security', 'cybersecurity'],
    used_in_tenders: 1,
    uploaded_at: '2022-12-01T00:00:00Z',
  },
  {
    doc_id: 'd-cvs',
    org_id: 'org1',
    category: 'personnel',
    title: 'Key Personnel CVs — Senior Management',
    filename: 'senior_mgmt_cvs_2026.pdf',
    issue_date: '2026-06-01',
    verification_status: 'verified',
    tags: ['CVs', 'management', 'personnel', 'experience'],
    used_in_tenders: 3,
    uploaded_at: '2026-06-05T00:00:00Z',
  },
];

const MOCK_STATS: DashboardStats = {
  active_workspaces: 3,
  closing_soon: 2,
  avg_readiness: 57,
  pending_decisions: 2,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function withMockFallback<T>(fn: () => Promise<T>, mock: T): Promise<T> {
  try {
    return await fn();
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return mock;
    }
    throw error;
  }
}

// ─── API functions ────────────────────────────────────────────────────────────

export const getWorkspaces = (): Promise<TenderWorkspace[]> =>
  withMockFallback(() => api.get<TenderWorkspace[]>('/tendering/workspaces').then((response) => response.data), MOCK_WORKSPACES);

export const getWorkspace = (id: string): Promise<TenderWorkspace> =>
  withMockFallback(
    () => api.get<TenderWorkspace>(`/tendering/workspaces/${id}`).then((response) => response.data),
    MOCK_WORKSPACES.find((workspace) => workspace.id === id) ?? MOCK_WORKSPACES[0],
  );

export const getRequirements = (tenderId: string): Promise<Requirement[]> =>
  withMockFallback(
    () => api.get<Requirement[]>(`/tendering/workspaces/${tenderId}/requirements`).then((response) => response.data),
    MOCK_REQUIREMENTS[tenderId] ?? [],
  );

export const getBidDecision = (tenderId: string): Promise<BidDecisionReport | null> =>
  withMockFallback(
    () => api.get<BidDecisionReport>(`/tendering/workspaces/${tenderId}/bid-decision`).then((response) => response.data),
    MOCK_BID_DECISIONS[tenderId] ?? null,
  );

export const getDashboardStats = (): Promise<DashboardStats> =>
  withMockFallback(() => api.get<DashboardStats>('/tendering/stats').then((response) => response.data), MOCK_STATS);

export const getLibraryDocuments = (): Promise<LibraryDocument[]> =>
  withMockFallback(() => api.get<LibraryDocument[]>('/tendering/library').then((response) => response.data), MOCK_LIBRARY);

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

export const fetchMyTeam = (): Promise<OrgMember[]> =>
  withMockFallback(() => api.get<OrgMember[]>('/tendering/my-team').then((response) => response.data), []);

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

export const deleteWorkspaceDocument = (workspaceId: string, docId: string): Promise<void> =>
  api.delete(`/tendering/workspaces/${workspaceId}/documents/${docId}`).then(() => undefined);

export const analyseWorkspace = (workspaceId: string): Promise<{ status: string }> =>
  api.post<{ status: string }>(`/tendering/workspaces/${workspaceId}/analyse`).then((r) => r.data);

export const addLibraryDocument = (data: {
  title: string;
  filename?: string;
  category?: string;
  file_type?: string;
  expiry_date?: string;
  url?: string;
}): Promise<LibraryDocument> =>
  api.post<LibraryDocument>('/tendering/library', data).then((response) => response.data);

export const deleteLibraryDocument = (docId: string): Promise<void> =>
  api.delete(`/tendering/library/${docId}`).then(() => undefined);

export const replaceLibraryDocument = (docId: string, data: { url: string; filename?: string }): Promise<LibraryDocument> =>
  api.patch<LibraryDocument>(`/tendering/library/${docId}`, data).then((r) => r.data);

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
