// ─── Tender ──────────────────────────────────────────────────────────────────

export type TenderStatus = 'open' | 'closed' | 'draft' | 'awarded';

export interface Tender {
  id: string;
  title: string;
  issuer: string;
  category: string;
  status: TenderStatus;
  deadline: string;        // ISO date string
  budget_min?: number;
  budget_max?: number;
  currency: string;
  description: string;
  requirements: string[];
  documents: TenderDocument[];
  created_at: string;
}

export interface TenderDocument {
  id: string;
  name: string;
  url: string;
  size_bytes: number;
}

// ─── Compliance ───────────────────────────────────────────────────────────────

export type ComplianceResult = 'pass' | 'fail' | 'partial';

export interface ComplianceCheck {
  id: string;
  tender_id: string;
  tender_title: string;
  checked_at: string;
  overall_score: number;   // 0–100
  result: ComplianceResult;
  items: ComplianceItem[];
}

export interface ComplianceItem {
  requirement: string;
  result: ComplianceResult;
  note: string;
}

// ─── Reference Library ────────────────────────────────────────────────────────

export type ReferenceCategory = 'legal' | 'financial' | 'technical' | 'template' | 'other';

export interface ReferenceDocument {
  id: string;
  title: string;
  category: ReferenceCategory;
  description: string;
  url: string;
  tags: string[];
  created_at: string;
}

// ─── Dashboard Stats ──────────────────────────────────────────────────────────

export interface DashboardStats {
  active_tenders: number;
  closing_soon: number;
  compliance_checks: number;
  avg_compliance_score: number;
}
