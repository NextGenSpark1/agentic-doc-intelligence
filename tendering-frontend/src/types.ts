// ─── Auth / Org ───────────────────────────────────────────────────────────────

export type OrgRole = 'org_admin' | 'supervisor' | 'member';

export interface OrgContext {
  role: 'platform_admin' | OrgRole | null;
  org_id?: string;
  org_name?: string;
  org_plan?: string;
  org_status?: string; // 'active' | 'suspended'
}

export interface OrgMember {
  member_id: string;
  org_id: string;
  user_id: string;
  email: string;
  full_name?: string;
  role: OrgRole;
  joined_at: string;
}

export interface PendingInvitation {
  token: string;
  email: string;
  role: string;
  created_at: string;
  expires_at: string;
}

export interface InvitationPreview {
  org_id: string;
  org_name: string;
  email: string;
  role: string;
  expires_at: string;
}

export interface Organisation {
  org_id: string;
  name: string;
  plan: string;
  status?: string;
  created_at: string;
  member_count?: number;
  workspace_count?: number;
  members?: OrgMember[];
}

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

export interface WorkspaceDocument {
  id: string;
  name: string;
  category?: 'rfp' | 'supporting';
  file_type?: string;
  size_kb?: number;
  size_bytes?: number;
  url?: string;
  uploaded_at?: string;
  verified?: boolean;
  page_count?: number;
}

export interface TenderWorkspace {
  id: string;
  org_id: string;
  title: string;
  reference: string;
  buyer: string;
  category: string;
  closing_date: string;
  contract_value: number;
  currency: string;
  stage: WorkspaceStage;
  bid_decision: BidDecision;
  readiness_score: number;
  requirements_count?: number;
  requirements_met?: number;
  requirements_partial?: number;
  requirements_gap?: number;
  description?: string;
  documents?: WorkspaceDocument[];
  team_members?: string[];
  created_at: string;
  updated_at?: string;
}

export interface DashboardStats {
  active_workspaces: number;
  closing_soon: number;
  avg_readiness: number;
  pending_decisions: number;
}

export interface Requirement {
  req_id: string;
  workspace_id?: string;
  tender_id?: string;
  title?: string;
  description: string;
  category: RequirementCategory;
  status: RequirementStatus;
  owner?: string;
  notes?: string;
  source_page?: number;
  source_doc?: string;
  page?: number;
  clause?: string;
  mandatory?: boolean;
  confidence?: number;
  evidence_doc_ids?: string[];
  matched_doc_ids?: string[];
}

export interface BidDecisionReport {
  workspace_id?: string;
  tender_id?: string;
  decision?: BidDecision;
  recommendation: BidDecision;
  score: number;
  readiness_score?: number;
  strengths: string[];
  risks: string[];
  gaps?: string[];
  rationale?: string;
  analysed_at?: string;
  generated_at?: string;
}

export type DocCategory = 'registration' | 'certification' | 'financial' | 'technical' | 'personnel' | 'other';
export type VerificationStatus = 'verified' | 'pending' | 'expired' | 'missing';

export interface LibraryDocument {
  doc_id: string;
  org_id: string;
  title: string;
  filename?: string;
  category: DocCategory;
  file_type?: string;
  uploaded_at: string;
  issue_date?: string;
  expiry_date?: string;
  verification_status: VerificationStatus;
  tags?: string[];
  used_in_tenders?: number;
}
