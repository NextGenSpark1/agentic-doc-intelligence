// Mirrored from shared/schemas.py

export interface SchemaField {
  name: string
  description: string
  is_array: boolean
  custom: boolean
}

export interface Case {
  case_id: string
  title: string
  case_type: string
  status: string
  lead_investigator: string
  allegation_summary: string
  risk_score: number
  created_at: string
  doc_count?: number
  schema_fields: SchemaField[]
}

export interface Document {
  document_id: string
  case_id: string
  filename: string
  file_hash: string
  storage_path: string
  document_type: string
  extraction_status: string
  page_count: number
  uploaded_at: string
}

export interface DocumentChunk {
  chunk_id: string
  text: string
  type: string
  page: number | null
  bbox: [number, number, number, number] | []
}

export interface Extraction {
  extraction_id: string
  document_id: string
  schema_name: string
  extracted_json: Record<string, unknown>
  visual_grounding_json: Record<string, unknown>
  extracted_at: string
  raw_text?: string  // reconstructed from chunks; absent if document has no chunks yet
}

export interface Citation {
  document_id: string
  page: number
  bbox: [number, number, number, number]
  quoted_text: string
  chunk_id: string
}

export interface Finding {
  finding_id: string
  case_id: string
  finding_type: string
  severity: string
  confidence: number
  statement: string
  supporting_document_ids: string[]
  human_review_status: string
  reviewed_by?: string
  reviewed_at?: string
  dismissal_reason?: string
}

export interface Entity {
  entity_id: string
  case_id: string
  entity_type: string
  canonical_name: string
  aliases: string[]
  confidence_score: number
}

export interface Relationship {
  relationship_id: string
  case_id: string
  source_name: string
  target_name: string
  relationship_type: string
  evidence: Record<string, unknown>
}

export interface TimelineEvent {
  event_id: string
  case_id: string
  event_date: string
  label: string
  document_id: string | null
}

export interface ChatRequest {
  message: string
  scope: 'case' | 'document'
  context_id: string
  history: Record<string, unknown>[]
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
}

export interface CasesListResponse {
  cases: Case[]
  stats: {
    open_cases: number
    findings_pending_review: number
  }
}

export interface CreateCasePayload {
  title: string
  lead_investigator: string
  case_type: string
  allegation_summary: string
  schema_fields: SchemaField[]
}
