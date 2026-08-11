# Tendering Intelligence — Backend Specification

> **Purpose:** Product spec for `apps/tendering/` — what to build, what each endpoint does, what each pipeline stage produces.  
> This complements the shared-core architecture in `CORE_EXTRACTION_PROPOSAL.md`, which covers how to structure the code. This document covers what the tendering product actually needs.

---

## 1. Database Tables

All tables live in the same Supabase project as Investigation Intelligence. Every table has `org_id` for tenant isolation. RLS policies should mirror the existing investigation tables (org members see only their org's rows).

### `tender_workspaces`
One row per tender a company is bidding on.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `org_id` | `uuid` FK → orgs | tenant isolation |
| `title` | `text` | e.g. "National Broadband Infrastructure — Phase 3" |
| `reference` | `text` | issuing body's reference number |
| `buyer` | `text` | name of the issuing authority |
| `category` | `text` | e.g. "ICT Infrastructure" |
| `closing_date` | `date` | bid submission deadline |
| `contract_value` | `numeric` | optional |
| `currency` | `text` | default `'USD'` |
| `stage` | `text` | `new \| analysing \| preparing \| submitted \| awarded \| lost \| no_bid` |
| `bid_decision` | `text` | `pending \| bid \| no_bid` |
| `readiness_score` | `integer` | 0–100, recomputed after each pipeline run |
| `requirements_count` | `integer` | total extracted |
| `requirements_met` | `integer` | |
| `requirements_gap` | `integer` | |
| `requirements_partial` | `integer` | |
| `description` | `text` | optional, from tender notice |
| `team_members` | `text[]` | display names of assigned team |
| `created_at` | `timestamptz` | |

### `workspace_documents`
RFP files uploaded to a workspace (the tender documents themselves).

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `workspace_id` | `uuid` FK → tender_workspaces | |
| `org_id` | `uuid` FK → orgs | |
| `name` | `text` | original filename |
| `url` | `text` | Supabase Storage URL |
| `size_bytes` | `integer` | |
| `extracted_text` | `text` | raw output from ADE |
| `uploaded_at` | `timestamptz` | |

### `requirements`
One row per requirement extracted from the RFP. The core of the platform.

| Column | Type | Notes |
|---|---|---|
| `req_id` | `uuid` PK | |
| `tender_id` | `uuid` FK → tender_workspaces | |
| `org_id` | `uuid` FK → orgs | |
| `description` | `text` | full requirement text as extracted |
| `category` | `text` | `technical \| financial \| legal \| experience \| personnel \| certification \| other` |
| `mandatory` | `boolean` | true = must-have, false = desirable |
| `source_doc` | `text` | filename of the RFP document it was found in |
| `page` | `integer` | page number |
| `clause` | `text` | clause/section reference, e.g. "5.1.a" |
| `confidence` | `integer` | AI confidence 0–100 |
| `status` | `text` | `met \| partial \| gap \| unchecked` |
| `owner` | `text` | team member assigned to address this requirement |
| `notes` | `text` | AI or manual notes on how it is/isn't met |
| `matched_doc_ids` | `text[]` | doc_ids from library_documents that cover this requirement |

### `bid_decision_reports`
AI-generated analysis for the bid/no-bid decision.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `tender_id` | `uuid` FK → tender_workspaces | |
| `org_id` | `uuid` FK → orgs | |
| `score` | `integer` | overall bid viability 0–100 |
| `recommendation` | `text` | `bid \| no_bid \| pending` |
| `rationale` | `text` | one-paragraph AI explanation |
| `strengths` | `text[]` | bullet points (why to bid) |
| `risks` | `text[]` | bullet points (why not to bid) |
| `generated_at` | `timestamptz` | |

### `library_documents`
The company's own documents uploaded once and reused across tenders.

| Column | Type | Notes |
|---|---|---|
| `doc_id` | `uuid` PK | |
| `org_id` | `uuid` FK → orgs | |
| `category` | `text` | `registration \| certification \| financial \| technical \| personnel \| other` |
| `title` | `text` | human-readable name, e.g. "ISO 9001:2015 Certificate" |
| `filename` | `text` | original upload filename |
| `url` | `text` | Supabase Storage URL |
| `size_bytes` | `integer` | |
| `issue_date` | `date` | when the document was issued |
| `expiry_date` | `date` | null if does not expire |
| `verification_status` | `text` | `verified \| pending \| expired \| missing` |
| `tags` | `text[]` | e.g. `["ISO", "quality"]` |
| `used_in_tenders` | `integer` | count, recomputed when matched |
| `uploaded_at` | `timestamptz` | |

### `library_document_chunks`
Chunked and embedded content for semantic search against requirements.
Mirrors the `chunks` table in Investigation Intelligence — reuse `core/extract.py`.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `doc_id` | `uuid` FK → library_documents | |
| `org_id` | `uuid` FK → orgs | |
| `chunk_index` | `integer` | order within document |
| `content` | `text` | chunk text |
| `embedding` | `vector(768)` | Gemini embedding |
| `page` | `integer` | |

---

## 2. API Endpoints

All endpoints sit under `apps/tendering/main.py` and are included in the core FastAPI app as:
```python
app.include_router(tendering.router, prefix="/tendering")
```

All routes require a valid JWT (via `core/auth.py`). All queries filter by `org_id` extracted from the JWT.

### Workspaces

| Method | Path | Description |
|---|---|---|
| `GET` | `/tendering/workspaces` | List org's workspaces. Returns array with readiness_score, stage, closing_date, requirements counts. |
| `POST` | `/tendering/workspaces` | Create a new workspace. Body: title, reference, buyer, category, closing_date, contract_value, currency, description. Sets stage = `new`. |
| `GET` | `/tendering/workspaces/{id}` | Full workspace detail including documents list and team_members. |
| `PATCH` | `/tendering/workspaces/{id}` | Update stage, bid_decision, team_members, or any metadata field. |
| `DELETE` | `/tendering/workspaces/{id}` | Soft-delete (set stage = archived) or hard delete. |

### RFP Documents (upload triggers pipeline)

| Method | Path | Description |
|---|---|---|
| `POST` | `/tendering/workspaces/{id}/documents` | Upload RFP file (multipart). Stores in Supabase Storage, inserts `workspace_documents` row, triggers the analysis pipeline (sets stage = `analysing`). |
| `GET` | `/tendering/workspaces/{id}/documents` | List uploaded RFP files for a workspace. |
| `DELETE` | `/tendering/workspaces/{id}/documents/{doc_id}` | Remove RFP file. |

### Requirements

| Method | Path | Description |
|---|---|---|
| `GET` | `/tendering/workspaces/{id}/requirements` | List all requirements for a workspace. Supports query params: `status`, `category`, `mandatory`. |
| `PATCH` | `/tendering/requirements/{req_id}` | Manual override — update status, owner, notes, matched_doc_ids. Used when a team member resolves a gap or corrects AI output. |
| `POST` | `/tendering/workspaces/{id}/analyse` | Re-trigger the full pipeline (extract → match → score). Useful after uploading additional RFP documents or new library docs. |

### Bid Decision

| Method | Path | Description |
|---|---|---|
| `GET` | `/tendering/workspaces/{id}/bid-report` | Fetch the latest generated bid decision report. Returns null if not yet generated. |
| `POST` | `/tendering/workspaces/{id}/bid-report` | Trigger AI bid report generation. Requires requirements to exist. |
| `POST` | `/tendering/workspaces/{id}/confirm-decision` | Record the team's confirmed bid/no_bid decision. Body: `{ decision: "bid" | "no_bid" }`. Updates `tender_workspaces.bid_decision` and sets stage accordingly. |

### Document Library

| Method | Path | Description |
|---|---|---|
| `POST` | `/tendering/library/documents` | Upload org document (multipart). Stores file, inserts `library_documents` row, triggers embedding pipeline. |
| `GET` | `/tendering/library/documents` | List org's library documents. Supports query params: `category`, `verification_status`, `expiring_soon` (docs expiring within 30 days). |
| `PATCH` | `/tendering/library/documents/{doc_id}` | Update metadata: title, category, issue_date, expiry_date, tags, verification_status. |
| `DELETE` | `/tendering/library/documents/{doc_id}` | Remove document and its chunks. |
| `POST` | `/tendering/library/documents/{doc_id}/reprocess` | Re-run embedding pipeline (e.g. after replacing the file). |

### Dashboard

| Method | Path | Description |
|---|---|---|
| `GET` | `/tendering/dashboard/stats` | Returns: `active_workspaces`, `closing_soon` (≤14 days), `avg_readiness`, `pending_decisions`. All scoped to org. |

---

## 3. Pipeline Stages

Lives in `apps/tendering/pipeline/`. Each stage is a Python function that can be called independently and is chained in sequence when a new RFP document is uploaded.

### Stage 1 — `extract_requirements.py`

**Trigger:** Called after `core/extract.py` has run ADE on the uploaded RFP file (text + page structure already available in `workspace_documents.extracted_text`).

**What it does:**
1. Feeds extracted RFP text to LLM (`groq/llama-3.3-70b-versatile`, same tier as ADI's `reasoning`)
2. Prompt instructs the LLM to identify every requirement in the document — explicit ("the vendor shall…") and implicit ("previous experience in…")
3. For each requirement, LLM outputs:
   - `description` — full requirement text
   - `category` — one of: technical, financial, legal, experience, personnel, certification, other
   - `mandatory` — true/false
   - `clause` — section/clause reference if visible in text
   - `page` — page number from ADE output
   - `confidence` — 0–100
4. Inserts all rows into `requirements` table with `status = "unchecked"`
5. Updates `workspace.stage = "analysing"` → `"preparing"` after completion
6. Updates `requirements_count` on workspace

**Uses from core:** `core/llm.py` (LLM call), `core/llm_reasoning.py` (anti-hallucination — drop any requirement citing a page/clause not present in the extracted text)

---

### Stage 2 — `evidence_matching.py`

**Trigger:** Runs immediately after Stage 1. Also callable standalone via `POST /workspaces/{id}/analyse` when new library docs are added.

**What it does:**
1. For each requirement (status = `unchecked`), generates an embedding of the requirement description
2. Runs `match_chunks` against `library_document_chunks` for this org (same vector search as ADI chat — reuse `core/db_core.py match_chunks`)
3. Retrieves top-k candidate library document chunks
4. LLM validation pass: "Given this requirement and this library document content, does the document satisfy the requirement? Answer: fully / partially / not at all"
5. Sets `requirement.status`:
   - All mandatory evidence present → `met`
   - Partially covered → `partial`
   - No evidence found → `gap`
6. Sets `requirement.matched_doc_ids[]` — the `doc_id`s of matching library documents
7. Sets `requirement.notes` — brief AI explanation of why it's met/partial/gap
8. Updates `used_in_tenders` count on each matched `library_documents` row

**Uses from core:** `core/db_core.py` (match_chunks), `core/llm.py`

---

### Stage 3 — `compliance_matrix.py`

**Trigger:** Runs after Stage 2 completes.

**What it does:**
1. Reads all requirements for the workspace
2. Computes aggregate counts: met, partial, gap, unchecked
3. Computes `readiness_score`:
   ```
   score = (met × 1.0 + partial × 0.5) / total_requirements × 100
   ```
4. Updates `tender_workspaces`: `readiness_score`, `requirements_met`, `requirements_partial`, `requirements_gap`

This stage is lightweight (no LLM call) — pure aggregation from the requirements table.

---

### Stage 4 — `readiness_review.py`

**Trigger:** Called explicitly via `POST /workspaces/{id}/bid-report`. Not auto-run — team triggers it when they feel requirements and compliance are ready for review.

**What it does:**
1. Reads workspace metadata + all requirements with their statuses + matched docs
2. LLM prompt: "You are a bid advisor. Given the following tender requirements and our company's evidence coverage, assess whether we should bid. Provide: a score 0–100, a recommendation (bid/no_bid), a one-paragraph rationale, up to 5 strengths, up to 5 risks."
3. Anti-hallucination: any strength/risk citing a specific document is validated against `matched_doc_ids` (same guardrail pattern as ADI's `llm_reasoning.py`)
4. Inserts row into `bid_decision_reports`
5. Updates `workspace.stage` if not already past `preparing`

**Uses from core:** `core/llm.py`, `core/llm_reasoning.py`

---

## 4. Document Library Embedding Pipeline

Lives in `apps/tendering/` but reuses `core/extract.py` (chunk + embed) almost unchanged.

**Trigger:** `POST /tendering/library/documents` upload.

**Flow:**
```
Upload file → Supabase Storage
    → ADE (core/ade_client.py) → extracted text + page structure
    → Chunk text (core/extract.py chunk logic, ~500 token chunks)
    → Gemini embeddings (core/extract.py embed logic)
    → Insert into library_document_chunks
    → Set library_documents.verification_status = "pending"
```

`verification_status` starts as `pending` (extracted, not yet human-verified). Team manually sets to `verified` via `PATCH /library/documents/{doc_id}`. Expired docs are flagged automatically by comparing `expiry_date` to today — a daily or on-load check sets `verification_status = "expired"`.

---

## 5. Document Type Labels (for `core/classify.py`)

When the shared `classify()` engine runs on tendering documents, pass these labels instead of the investigation ones:

```python
TENDERING_DOC_TYPES = [
    "tender_notice",
    "instructions_to_tenderers",
    "bill_of_quantities",
    "pricing_schedule",
    "technical_specifications",
    "evaluation_criteria",
    "contract_draft",
    "other",
]
```

---

## 6. What Reuses Unchanged from Core

| Core component | How tendering uses it |
|---|---|
| `core/auth.py` | JWT verification on every tendering route — no change |
| `core/orgs.py` | Org/user lookup, org_id extraction from JWT — no change |
| `core/ade_client.py` | ADE document extraction for both RFP files and library docs |
| `core/llm.py` | LLM calls in all four pipeline stages |
| `core/llm_reasoning.py` | Anti-hallucination guardrail in stages 1 and 4 |
| `core/extract.py` | Chunking + Gemini embedding for library document chunks |
| `core/db_core.py` | `match_chunks` vector search for evidence matching (Stage 2) |
| `core/email.py` | (Future) notify team when pipeline completes or gaps are found |
