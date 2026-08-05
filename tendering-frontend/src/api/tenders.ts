import axios from 'axios';
import type { Tender, ComplianceCheck, ReferenceDocument, DashboardStats } from '../types';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

// Attach Supabase auth token to every request so the backend can verify identity.
api.interceptors.request.use((config) => {
  const session = localStorage.getItem('sb-session');
  if (session) {
    try {
      const { access_token } = JSON.parse(session);
      config.headers.Authorization = `Bearer ${access_token}`;
    } catch {
      // no valid session — request goes through without auth
    }
  }
  return config;
});

// ─── Mock data (used until Nawran wires up the tendering endpoints) ───────────

const MOCK_TENDERS: Tender[] = [
  {
    id: '1',
    title: 'Road Infrastructure Rehabilitation — Northern Region',
    issuer: 'Ministry of Public Works',
    category: 'Infrastructure',
    status: 'open',
    deadline: '2026-09-15',
    budget_min: 500000,
    budget_max: 2000000,
    currency: 'USD',
    description: 'Tender for the rehabilitation of 120km of road network in the northern region, including drainage and signage.',
    requirements: ['ISO 9001 certified', 'Minimum 5 years experience', 'Local subcontracting ≥ 30%'],
    documents: [{ id: 'd1', name: 'Tender Specifications.pdf', url: '#', size_bytes: 2400000 }],
    created_at: '2026-08-01T00:00:00Z',
  },
  {
    id: '2',
    title: 'Hospital Management Information System',
    issuer: 'Ministry of Health',
    category: 'IT & Software',
    status: 'open',
    deadline: '2026-08-30',
    budget_min: 150000,
    budget_max: 600000,
    currency: 'USD',
    description: 'Supply, installation, and maintenance of an integrated HMIS for 12 regional hospitals.',
    requirements: ['HL7 FHIR compliant', 'Local data residency', '24/7 SLA support'],
    documents: [{ id: 'd2', name: 'RFP Document.pdf', url: '#', size_bytes: 1800000 }],
    created_at: '2026-07-28T00:00:00Z',
  },
  {
    id: '3',
    title: 'Solar Energy Generation — Rural Electrification',
    issuer: 'National Energy Authority',
    category: 'Energy',
    status: 'closed',
    deadline: '2026-07-31',
    budget_min: 1000000,
    budget_max: 5000000,
    currency: 'USD',
    description: 'Design, supply, and installation of solar mini-grids for 50 rural communities.',
    requirements: ['IEC 61730 certified panels', 'Battery storage included', '10-year warranty'],
    documents: [],
    created_at: '2026-06-15T00:00:00Z',
  },
  {
    id: '4',
    title: 'Supply of Laboratory Equipment — Universities',
    issuer: 'Ministry of Education',
    category: 'Equipment',
    status: 'open',
    deadline: '2026-09-01',
    budget_min: 80000,
    budget_max: 300000,
    currency: 'USD',
    description: 'Procurement of science laboratory equipment for 8 national universities.',
    requirements: ['CE marked equipment', 'Installation and training included', 'Spare parts availability ≥ 5 years'],
    documents: [{ id: 'd4', name: 'Equipment List.xlsx', url: '#', size_bytes: 340000 }],
    created_at: '2026-07-20T00:00:00Z',
  },
];

const MOCK_COMPLIANCE: ComplianceCheck[] = [
  {
    id: 'c1',
    tender_id: '1',
    tender_title: 'Road Infrastructure Rehabilitation — Northern Region',
    checked_at: '2026-08-03T10:00:00Z',
    overall_score: 78,
    result: 'partial',
    items: [
      { requirement: 'ISO 9001 certified', result: 'pass', note: 'Certificate valid until 2027.' },
      { requirement: 'Minimum 5 years experience', result: 'pass', note: 'Portfolio confirms 7 years.' },
      { requirement: 'Local subcontracting ≥ 30%', result: 'partial', note: 'Current plan is 22% — needs revision.' },
    ],
  },
  {
    id: 'c2',
    tender_id: '2',
    tender_title: 'Hospital Management Information System',
    checked_at: '2026-08-04T14:30:00Z',
    overall_score: 95,
    result: 'pass',
    items: [
      { requirement: 'HL7 FHIR compliant', result: 'pass', note: 'FHIR R4 certified.' },
      { requirement: 'Local data residency', result: 'pass', note: 'Data centre located in-country.' },
      { requirement: '24/7 SLA support', result: 'pass', note: 'Confirmed in service agreement.' },
    ],
  },
];

const MOCK_REFERENCES: ReferenceDocument[] = [
  {
    id: 'r1',
    title: 'Standard Bid Evaluation Form',
    category: 'template',
    description: 'Official bid evaluation template approved for use in all public procurement.',
    url: '#',
    tags: ['procurement', 'evaluation', 'official'],
    created_at: '2026-01-10T00:00:00Z',
  },
  {
    id: 'r2',
    title: 'Public Procurement Act (2023 Revision)',
    category: 'legal',
    description: 'Updated procurement regulations covering thresholds, timelines, and appeal rights.',
    url: '#',
    tags: ['legal', 'regulations', '2023'],
    created_at: '2023-06-01T00:00:00Z',
  },
  {
    id: 'r3',
    title: 'Technical Proposal Writing Guide',
    category: 'template',
    description: 'Step-by-step guide and template for writing strong technical proposals.',
    url: '#',
    tags: ['proposal', 'template', 'guide'],
    created_at: '2026-03-15T00:00:00Z',
  },
  {
    id: 'r4',
    title: 'Financial Capacity Statement Template',
    category: 'financial',
    description: 'Standard template for declaring financial standing in tender submissions.',
    url: '#',
    tags: ['financial', 'template', 'capacity'],
    created_at: '2026-02-20T00:00:00Z',
  },
];

const MOCK_STATS: DashboardStats = {
  active_tenders: 3,
  closing_soon: 1,
  compliance_checks: 2,
  avg_compliance_score: 86,
};

// ─── API functions ────────────────────────────────────────────────────────────
// Each function tries the real backend first; falls back to mock data if the
// endpoint doesn't exist yet (404 = Nawran hasn't built it yet).

async function withMockFallback<T>(fn: () => Promise<T>, mock: T): Promise<T> {
  try {
    return await fn();
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      return mock;
    }
    throw err;
  }
}

export const getTenders = (): Promise<Tender[]> =>
  withMockFallback(() => api.get<Tender[]>('/tenders').then(r => r.data), MOCK_TENDERS);

export const getTender = (id: string): Promise<Tender> =>
  withMockFallback(() => api.get<Tender>(`/tenders/${id}`).then(r => r.data), MOCK_TENDERS.find(t => t.id === id)!);

export const getDashboardStats = (): Promise<DashboardStats> =>
  withMockFallback(() => api.get<DashboardStats>('/tenders/stats').then(r => r.data), MOCK_STATS);

export const getComplianceChecks = (): Promise<ComplianceCheck[]> =>
  withMockFallback(() => api.get<ComplianceCheck[]>('/compliance').then(r => r.data), MOCK_COMPLIANCE);

export const runComplianceCheck = (tenderId: string): Promise<ComplianceCheck> =>
  withMockFallback(
    () => api.post<ComplianceCheck>(`/tenders/${tenderId}/compliance`).then(r => r.data),
    MOCK_COMPLIANCE.find(c => c.tender_id === tenderId) ?? MOCK_COMPLIANCE[0],
  );

export const getReferenceDocuments = (): Promise<ReferenceDocument[]> =>
  withMockFallback(() => api.get<ReferenceDocument[]>('/reference-library').then(r => r.data), MOCK_REFERENCES);
