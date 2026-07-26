# Investigation Intelligence Platform — Documentation

> **ADI** (Agentic Document Intelligence) — AI-powered platform for forensic investigation teams to ingest, extract, and reason over large document corpora using LLM-driven pipelines.

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Architecture](#2-architecture)
3. [Environment Variables](#3-environment-variables)
4. [External Services Setup](#4-external-services-setup)
5. [Multi-tenancy & Role System](#5-multi-tenancy--role-system)
6. [Database Schema](#6-database-schema)
7. [API Endpoints](#7-api-endpoints)
8. [Pipeline Stages](#8-pipeline-stages)
9. [Frontend Pages & Features](#9-frontend-pages--features)
10. [Deployment Guide](#10-deployment-guide)
11. [SQL Migrations](#11-sql-migrations)
12. [Testing](#12-testing)

---

## 1. Platform Overview

**What it is:** A closed, invite-only SaaS platform that helps forensic investigation teams process large volumes of documents using AI — extracting structured data, identifying entities and relationships, detecting anomalies, reconstructing timelines, and generating formal investigation reports.

**Who it is for:** Enterprise investigation teams (audit, compliance, fraud, legal) that need to surface signals across large document corpora without manual review.

**Core workflow:**
1. Upload documents (PDFs, images, scanned files)
2. AI extracts structured fields using LandingAI ADE
3. Case analysis runs: entity resolution, relationship mapping, timeline reconstruction, anomaly detection
4. Investigators review flagged findings (confirm or dismiss)
5. Generate a formal PDF-ready investigation report

### Deployment Models

| Model | Description | Who controls orgs | Monetisation |
|---|---|---|---|
| **SaaS** | Hosted by NextGen Spark on Vercel + Railway | NextGen Spark (platform admin) | Monthly/annual subscription per org |
| **On-Prem** | Client installs on their own infrastructure | Client's IT admin | One-time or annual licence fee |

For on-prem, set `PLATFORM_ADMIN_EMAILS` to the client's IT admin email. They get full control. NextGen Spark has zero visibility into their data.

---

## 2. Architecture

| Layer | Technology | Hosting |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS | Vercel |
| Backend API | FastAPI (Python 3.11+) | Railway |
| Database | Supabase (Postgres 15 + pgvector) | Supabase |
| File Storage | Supabase Storage (S3-compatible) | Supabase |
| Auth | Supabase Auth (email/password + Google OAuth) | Supabase |
| Document Extraction | LandingAI ADE (Agentic Document Extraction) | LandingAI cloud |
| LLM Routing | LiteLLM (provider-agnostic) | — |
| LLM — Reasoning | Groq `llama-3.3-70b-versatile` (default) | Groq |
| LLM — Fast | Groq `llama-3.1-8b-instant` (default) | Groq |
| LLM — Embeddings | Google Gemini `gemini-embedding-001` @ 1536 dims | Google AI Studio |
| Email | Resend (transactional invitation emails) | Resend |

### Request Flow

```
Browser → Vercel (React SPA)
             ↓ HTTPS API calls (Bearer token)
          Railway (FastAPI)
             ↓
          Supabase (Postgres + Storage)
             ↓ (pipeline stages)
          LandingAI ADE  ←→  LiteLLM → Groq / Gemini
```

---

## 3. Environment Variables

### Backend (Railway)

#### Supabase
| Variable | Description | Where to get |
|---|---|---|
| `SUPABASE_URL` | Project URL | Supabase Dashboard → Project Settings → API |
| `SUPABASE_ANON_KEY` | Public anon key (used by frontend too) | Same |
| `SUPABASE_SERVICE_KEY` | Service role key — backend only, never expose | Same |
| `SUPABASE_JWT_SECRET` | JWT secret for verifying user tokens | Supabase Dashboard → Project Settings → API → JWT Settings |
| `STORAGE_BUCKET` | Storage bucket name (default: `evidence`) | Create in Supabase Storage |

#### LandingAI
| Variable | Description | Where to get |
|---|---|---|
| `LANDINGAI_API_KEY` | ADE extraction API key | LandingAI dashboard |
| `MOCK_ADE` | Set `true` to skip real ADE calls and return fake data (testing) | — |

#### LLM
| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API key for Llama models | groq.com |
| `GEMINI_API_KEY` | Google AI Studio key for embeddings | aistudio.google.com |
| `OPENAI_API_KEY` | OpenAI key (if switching to GPT-4o models) | platform.openai.com |
| `LLM_REASONING_MODEL` | Model for summaries, chat, anomaly reasoning | `groq/llama-3.3-70b-versatile` |
| `LLM_FAST_MODEL` | Model for classification, cheap calls | `groq/llama-3.1-8b-instant` |
| `LLM_CASE_REASONING_MODEL` | Model for cross-document case reasoning | `groq/llama-3.3-70b-versatile` |
| `LLM_EMBEDDING_MODEL` | Model for RAG embeddings | `gemini/gemini-embedding-001` |

#### Multi-tenancy
| Variable | Description | Example |
|---|---|---|
| `PLATFORM_ADMIN_EMAILS` | Comma-separated emails with platform admin access | `admin@nextgenspark.com,cto@nextgenspark.com` |

#### Email (Resend)
| Variable | Description | Notes |
|---|---|---|
| `RESEND_API_KEY` | Resend API key | resend.com — optional, invites fall back to copy-link if not set |
| `RESEND_FROM_EMAIL` | Sender address | `onboarding@resend.dev` for testing; `noreply@yourdomain.com` after domain verified |

#### CORS
| Variable | Description | Example |
|---|---|---|
| `CORS_ALLOW_ORIGINS` | Comma-separated allowed origins | `https://investigate.nextgenspark.solutions` |

### Frontend (Vercel)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend Railway URL, e.g. `https://your-app.railway.app` |
| `VITE_SUPABASE_URL` | Same as `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | Same as `SUPABASE_ANON_KEY` |

---

## 4. External Services Setup

### Supabase
1. Create a new project at [supabase.com](https://supabase.com)
2. Go to SQL Editor → paste and run the full contents of `backend/schema.sql`
3. Go to Storage → create a bucket named `evidence` (set to private)
4. Go to Authentication → Providers → enable Google OAuth (see below)
5. Copy keys from Project Settings → API into your `.env`

### LandingAI ADE
1. Sign up at [landing.ai](https://landing.ai)
2. Go to API Keys → create a key
3. Set `LANDINGAI_API_KEY` in your environment
4. The backend bridges this to `VISION_AGENT_API_KEY` automatically

### Groq (LLM — Reasoning & Fast tiers)
1. Sign up at [groq.com](https://groq.com)
2. Go to API Keys → create a key
3. Set `GROQ_API_KEY` — free tier is generous for development

### Google AI Studio (Embeddings)
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Create an API key
3. Set `GEMINI_API_KEY` — used for `gemini-embedding-001` at 1536 dimensions

### Google OAuth (Supabase Auth)
1. Go to [console.cloud.google.com](https://console.cloud.google.com) → Create project
2. APIs & Services → OAuth consent screen → configure
3. Credentials → Create OAuth Client ID → Web application
4. Add `https://<your-supabase-project>.supabase.co/auth/v1/callback` as authorised redirect URI
5. Copy Client ID and Secret into Supabase Dashboard → Authentication → Providers → Google

### Resend (Email)
1. Sign up at [resend.com](https://resend.com)
2. Create an API key → set `RESEND_API_KEY`
3. **Testing without a domain:** use `RESEND_FROM_EMAIL=onboarding@resend.dev` — can only send to your Resend account email
4. **Production:** verify your domain in Resend dashboard → set `RESEND_FROM_EMAIL=noreply@yourdomain.com` → can send to any address

### Vercel (Frontend)
1. Import the GitHub repo into Vercel
2. Set root directory to `frontend`
3. Framework preset: Vite
4. Add environment variables: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
5. Deploy — Vercel auto-deploys on every push to `main`

### Railway (Backend)
1. Create a new project → deploy from GitHub repo
2. Set start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. Set root directory: `/` (repo root)
4. Add all backend environment variables listed in Section 3
5. Railway auto-deploys on every push to `main`

---

## 5. Multi-tenancy & Role System

### Role Hierarchy

```
NextGen Spark (Platform Admin)
    └── Organisation (e.g. "Habiba Corp")
            └── Org Admin
                    └── Supervisor A          Supervisor B
                            └── Member 1              └── Member 3
                            └── Member 2              └── Member 4
```

### Roles

| Role | Can do |
|---|---|
| **Platform Admin** | Create/view organisations, see org metadata (never case content). Identified by email in `PLATFORM_ADMIN_EMAILS`. |
| **Org Admin** | Invite supervisors and members, see all cases in the org, manage the team |
| **Supervisor** | Invite members, create cases, see only their own team's cases |
| **Member** | View and work on cases created by their supervisor only |

### Team Isolation

Each supervisor + the members they invited = one team. Cases are scoped to the creator (`created_by` column). Members see only cases where `created_by = their supervisor's user_id`. Org admins see all cases across the org.

### Invite Chain

1. **Platform Admin** creates an organisation via `/admin` → gets a first invite link
2. Link is sent to the **Org Admin** → they register/login → accept → join as org_admin
3. **Org Admin** goes to Case Settings → Team tab → invites supervisors
4. **Supervisor** invites members
5. Registration at `/register` is blocked without an invite token — the platform is invite-only

### Email Invitations

When `RESEND_API_KEY` is set and a domain is verified, invitation emails are sent automatically with a branded HTML template. Without a domain, the invite link is shown in the UI for manual sharing (copy-link fallback).

---

## 6. Database Schema

| Table | Purpose |
|---|---|
| `cases` | Core case records — title, type, status, risk score, org/team scoping |
| `documents` | Uploaded files — metadata, storage path, extraction status |
| `extractions` | Structured JSON output from LandingAI ADE per document |
| `chunks` | Text chunks with 1536-dim vector embeddings for RAG search |
| `entities` | Named entities resolved across all documents (person, company, amount, etc.) |
| `relationships` | Directed edges between entities with relationship type and confidence |
| `findings` | Flagged anomalies/red flags — pending human review (confirm/dismiss) |
| `timeline_events` | Chronological events extracted from documents |
| `audit_log` | Immutable log of all actions (case created, finding reviewed, etc.) |
| `organisations` | Org records — name, plan, created_by |
| `org_members` | User ↔ org membership with role and invited_by (supervisor reference) |
| `invitations` | Pending invite tokens — email, role, expiry, accepted_at |

**Vector search functions:**
- `match_chunks(case_id, embedding, count)` — similarity search across a case's chunks
- `match_chunks_in_document(document_id, embedding, count)` — scoped to one document

---

## 7. API Endpoints

All authenticated endpoints require `Authorization: Bearer <supabase_jwt>`.

### Health
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service health check |

### Cases
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/cases` | Required | List cases (team-scoped by role) |
| POST | `/cases` | Required | Create a new case |
| GET | `/cases/{id}` | Required | Get a single case |
| PATCH | `/cases/{id}` | Required | Update case fields |
| DELETE | `/cases/{id}` | Required | Delete case and all its documents |
| GET | `/cases/{id}/graph-state` | Required | Get saved entity graph layout |
| PUT | `/cases/{id}/graph-state` | Required | Save entity graph layout |

### Documents
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/cases/{id}/documents` | Required | Upload a document |
| GET | `/cases/{id}/documents` | Required | List case documents |
| DELETE | `/cases/{id}/documents/{doc_id}` | Required | Delete a document |
| POST | `/cases/{id}/documents/{doc_id}/extract` | Required | Trigger AI extraction |
| GET | `/cases/{id}/documents/{doc_id}/extraction` | Required | Get extraction result |
| GET | `/cases/{id}/documents/{doc_id}/summary` | Required | Get AI-generated document summary |
| GET | `/cases/{id}/documents/{doc_id}/file-url` | Required | Get signed storage URL |
| GET | `/cases/{id}/documents/{doc_id}/chunks` | Required | Get RAG chunks with bounding boxes |

### Case Analysis
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/cases/{id}/analysis` | Required | Run full case analysis pipeline |
| GET | `/cases/{id}/entities` | Required | Get entities and relationships |
| GET | `/cases/{id}/timeline` | Required | Get timeline events |
| GET | `/cases/{id}/findings` | Required | Get all findings |
| POST | `/cases/{id}/report` | Required | Generate markdown investigation report |
| POST | `/cases/{id}/chat` | Required | RAG-grounded Q&A over case documents |

### Findings
| Method | Path | Auth | Description |
|---|---|---|---|
| PATCH | `/findings/{id}/review` | Required | Confirm or dismiss a finding |

### Organisations (Multi-tenancy)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/orgs/me` | Required | Get current user's org and role |
| GET | `/orgs/{org_id}/members` | Required | List org members |
| POST | `/orgs/{org_id}/invite` | Required | Send invite (role-gated) |
| DELETE | `/orgs/{org_id}/members/{user_id}` | Org Admin | Remove a member |
| GET | `/platform/orgs` | Platform Admin | List all orgs with metadata |
| POST | `/platform/orgs` | Platform Admin | Create a new organisation |
| DELETE | `/platform/orgs/{org_id}/members/{user_id}` | Platform Admin | Remove any member |
| GET | `/invitations/{token}` | None (public) | Get invite details by token |
| POST | `/invitations/{token}/accept` | Required | Accept an invitation |

---

## 8. Pipeline Stages

### Per-Document (triggered on upload → extract)

| Stage | Module | Description |
|---|---|---|
| **Upload** | `main.py` | File stored in Supabase Storage, document row created |
| **Classify** | `pipeline/classify.py` | LLM classifies document type (invoice, contract, audit report, etc.) |
| **Extract** | `pipeline/extract.py` | LandingAI ADE extracts structured JSON fields from the document |

### Case-Level (triggered by "Run Analysis")

| Stage | Module | Description |
|---|---|---|
| **Resolve Entities** | `pipeline/resolve_entities.py` | Rule pass + LLM pass: named entities (persons, companies, amounts) resolved and deduplicated across all documents |
| **Build Relationships** | `pipeline/build_relationships.py` | Rule pass + LLM pass: directed relationships between entities extracted and stored |
| **Reconstruct Timeline** | `pipeline/reconstruct_timeline.py` | Rule pass + LLM pass: all dated events chronologically sorted; LLM flags sequencing anomalies |
| **Detect Anomalies** | `pipeline/detect_anomalies.py` | Rule pass + LLM pass: red flags generated as findings pending human review |
| **Summarise** | `pipeline/summarise.py` | LLM generates case-level AI summary and risk score from active findings |

**Resilience:** Every LLM pass is a non-blocking second pass on top of deterministic rules. If the LLM fails, the rule-based results are kept. All failures are logged to `audit_log` with `action=case_reasoning_failed`.

**Deduplication:** Findings, relationships, and timeline events use content hashes to prevent duplicate rows on re-analysis.

---

## 9. Frontend Pages & Features

| Route | Page | Description |
|---|---|---|
| `/login` | Login | Email/password + Google OAuth. Preserves invite token for redirect. |
| `/register` | Register | **Invite-only** — blocked without `?invite=TOKEN` in URL |
| `/invite/:token` | Invite Accept | Public page showing org name + role; accept button for logged-in users |
| `/cases` | Cases List | All cases visible to the user (team-scoped). Stats cards, new case modal. |
| `/cases/:id` | Case Workspace | Full investigation workspace (see tabs below) |
| `/account` | Account | Profile, password change, appearance settings |
| `/admin` | Platform Admin | Create organisations, view all orgs with member/case counts. Platform admin only. |

### Case Workspace Tabs

| Tab | Description |
|---|---|
| **Documents** | Upload files, trigger extraction, view PDF with chunk overlays and bounding boxes |
| **Entity Graph** | Interactive force-directed graph of entities and relationships. Edit mode: add/remove nodes and edges. |
| **Timeline** | Chronological events extracted from all documents. LLM-flagged anomalies highlighted. |
| **Findings** | AI-detected red flags pending human review. Confirm or dismiss each finding. |
| **Report** | Generate a branded PDF-ready investigation report from confirmed findings. Custom sections and instructions. |
| **Chat** | RAG-grounded Q&A — ask questions, get answers with document citations and page references. |

### Case Settings Tabs

| Tab | Description |
|---|---|
| **Details** | Edit case title, type, status, lead investigator, allegation summary |
| **Schema** | Customise extraction fields per case type |
| **Team** | Invite team members (role-gated), view member list, remove members |

---

## 10. Deployment Guide

### SaaS Deployment

**Prerequisites:** GitHub repo, Supabase project, Railway account, Vercel account.

1. **Database:** Run `backend/schema.sql` in Supabase SQL Editor (full file, top to bottom)
2. **Storage:** Create `evidence` bucket in Supabase Storage → set to private
3. **Backend (Railway):**
   - New project → Deploy from GitHub → select repo
   - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Add all backend env vars (Section 3)
   - Note the Railway URL (e.g. `https://app-production-xxxx.up.railway.app`)
4. **Frontend (Vercel):**
   - Import repo → set root directory to `frontend`
   - Add env vars: `VITE_API_URL=<railway-url>`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
   - Deploy
5. **CORS:** Set `CORS_ALLOW_ORIGINS=<vercel-url>` in Railway env vars
6. **Domain (optional):** Add subdomain CNAME in DNS → point to Vercel → configure in Vercel project settings

### On-Prem Deployment

1. Clone the repo onto the client's server
2. Set `PLATFORM_ADMIN_EMAILS` to the client's IT admin email
3. Client runs their own Supabase (self-hosted) or uses Supabase cloud with their own account
4. Deploy backend with Docker or directly with uvicorn
5. Deploy frontend with any static host (Nginx, Caddy, etc.)
6. NextGen Spark has **zero access** to client data in this model

---

## 11. SQL Migrations

All migrations live at the top of `backend/schema.sql` under the `-- MIGRATIONS` comment. Run them **in order** in the Supabase SQL Editor. They are idempotent (`IF NOT EXISTS`, `IF EXISTS`) — safe to re-run.

| Migration | Effect |
|---|---|
| `created_by` on cases | Team-level isolation — tracks which supervisor created each case |
| `summary` on extractions | Caches AI-generated document summaries |
| `schema_fields` on cases | Per-case custom extraction schema |
| `owner_id` on cases | Legacy per-user isolation (pre-multi-tenancy) |
| `supporting_chunks` on findings | Traceability — links findings to source chunks |
| `source` + `reasoning` columns | Tags rows as rule-generated or LLM-generated |
| `content_hash` columns | Deduplication indexes on findings, relationships, timeline_events |
| `hnsw` chunk index | Replaces ivfflat — better recall for growing corpora, no retuning needed |
| organisations / org_members / invitations tables | Multi-tenancy — full invite-chain role system |
| `org_id` on cases | Links cases to their organisation |

---

## 12. Testing

### Run Tests

```bash
# From repo root
pytest tests/ -v
```

### Test Files

| File | What it covers |
|---|---|
| `tests/test_access_control.py` | 9 tests — legacy owner, cross-org, org-admin, supervisor, member access matrix |
| `tests/test_anomalies.py` | Anomaly detection pipeline — rule pass and LLM pass |
| `tests/test_db_dedup.py` | Content-hash deduplication for findings, relationships, timeline events |
| `tests/test_relationships.py` | Relationship extraction — rule + LLM combined pass |
| `tests/test_schemas.py` | Extraction schema validation |
| `tests/test_summarise.py` | Case summarisation — active vs dismissed findings, risk score |

### Design Principles

- LLM calls are mocked in tests — no real API calls, no cost, no flakiness
- Tests cover both the happy path and edge cases (empty data, duplicate inserts, expired invitations)
- Access control tests cover every role combination explicitly

---

*Last updated: July 2026 — ADI v0.1 (multi-tenancy release)*
