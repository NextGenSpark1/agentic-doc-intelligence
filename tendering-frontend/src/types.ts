// ─── Tender Workspace ─────────────────────────────────────────────────────────

export type WorkspaceStage =
  | 'new'
  | 'analysing'
  | 'preparing'
  | 'submitted'
  | 'awarded'
  | 'lost'
  | 'no_bid';

export type BidDecision = 'pending' | 'bid' | 'no_bid';

export type RequirementStatus = 'met' | 'gap' | 'partial' | 'unchecked';
export type RequirementCategory =
  | 'technical'
  | 'financial'
  | 'legal'
  | 'experience'
  | 'personnel'
  | 'certification'
  | 'other';

export interface TenderWorkspace {
  id: string;
  org_id: string;
  title: string;
  reference: string;
  buyer: string;
  category: string;
  closing_date: string;
  contract_value?: number;
  currency: string;
  stage: WorkspaceStage;
  bid_decision: BidDecision;
  readiness_score: number;
  requirements_count: number;
  requirements_met: number;
  requirements_gap: number;
  requirements_partial: number;
  description: string;
  documents: WorkspaceDocument[];
  team_members: string[];
  created_at: string;
}

export interface WorkspaceDocument {
  id: string;
  name: string;
  url: string;
  size_bytes: number;
  uploaded_at: string;
}

// ─── Requirements ─────────────────────────────────────────────────────────────

export interface Requirement {
  req_id: string;
  tender_id: string;
  description: string;
  category: RequirementCategory;
  mandatory: boolean;
  source_doc?: string;
  page?: number;
  clause?: string;
  confidence: number;
  status: RequirementStatus;
  owner?: string;
  notes?: string;
  matched_doc_ids?: string[];
}

// ─── Bid Decision ─────────────────────────────────────────────────────────────

export interface BidDecisionReport {
  tender_id: string;
  score: number;
  recommendation: BidDecision;
  rationale: string;
  strengths: string[];
  risks: string[];
  generated_at: string;
}

// ─── Document Library ─────────────────────────────────────────────────────────

export type DocCategory =
  | 'registration'
  | 'certification'
  | 'financial'
  | 'technical'
  | 'personnel'
  | 'other';

export type VerificationStatus = 'verified' | 'pending' | 'expired' | 'missing';

export interface LibraryDocument {
  doc_id: string;
  org_id: string;
  category: DocCategory;
  title: string;
  filename: string;
  issue_date?: string;
  expiry_date?: string;
  verification_status: VerificationStatus;
  tags: string[];
  used_in_tenders?: number;
  uploaded_at: string;
}

// ─── Dashboard Stats ──────────────────────────────────────────────────────────

export interface DashboardStats {
  active_workspaces: number;
  closing_soon: number;
  avg_readiness: number;
  pending_decisions: number;
}
