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
13. [LLM Provider Reference](#13-llm-provider-reference)
14. [Service Accounts](#14-service-accounts)

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
| **SaaS (hosted)** | Hosted by NextGen Spark on Vercel + Railway | NextGen Spark (platform admin) | Monthly/annual subscription per org |
| **On-Prem / Private Cloud** | Client installs on their own infrastructure (Docker) | Client's IT admin | One-time or annual licence fee |
| **Managed Private Cloud** | NextGen Spark deploys on client's AWS/GCP account | Shared (client owns infra, NGS manages app) | Managed service contract |

For on-prem, set `PLATFORM_ADMIN_EMAILS` to the client's IT admin email. They get full control. NextGen Spark has zero visibility into their data.

---

## 2. Architecture

| Layer | Technology | Hosting |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS | Vercel (SaaS) or Docker/Nginx (on-prem) |
| Backend API | FastAPI (Python 3.12) | Railway via Docker image (SaaS) or any Docker host (on-prem) |
| Containerisation | Docker — `backend/Dockerfile.api`, `frontend/Dockerfile.frontend`, `docker-compose.yml` | — |
| Database | Supabase (Postgres 15 + pgvector) | Supabase cloud or self-hosted |
| File Storage | Supabase Storage (S3-compatible) | Supabase cloud or self-hosted |
| Auth | Supabase Auth (email/password + Google OAuth) | Supabase |
| Document Extraction | LandingAI ADE (Agentic Document Extraction) | LandingAI cloud |
| LLM Routing | LiteLLM (provider-agnostic — swap models via env vars) | — |
| LLM — Reasoning | Groq `llama-3.3-70b-versatile` (default) | Groq |
| LLM — Fast | Groq `llama-3.1-8b-instant` (default) | Groq |
| LLM — Embeddings | Google Gemini `gemini-embedding-001` @ 1536 dims | Google AI Studio |
| Email | Resend (transactional invitation emails) | Resend |

### Request Flow

```
Browser → Vercel (React SPA)
             ↓ HTTPS API calls (Bearer token)
          Railway (FastAPI — Docker image)
             ↓
          Supabase (Postgres + Storage)
             ↓ (pipeline stages)
          LandingAI ADE  ←→  LiteLLM → Groq / Gemini / OpenAI / Kimi
```

### Local Development (Docker Compose)

```
docker-compose up --build
# Backend  → http://localhost:8000
# Frontend → http://localhost:80
# Supabase → external (cloud), pointed to via .env
```

---

## 3. Environment Variables

### Backend (Railway / Docker)

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
| `OPENAI_API_KEY` | OpenAI key (if switching to GPT-4o) | platform.openai.com |
| `MOONSHOT_API_KEY` | Kimi (Moonshot) API key | platform.moonshot.cn |
| `LLM_REASONING_MODEL` | Model for summaries, chat, anomaly reasoning | `groq/llama-3.3-70b-versatile` |
| `LLM_FAST_MODEL` | Model for classification, cheap calls | `groq/llama-3.1-8b-instant` |
| `LLM_CASE_REASONING_MODEL` | Model for cross-document case reasoning | `groq/llama-3.3-70b-versatile` |
| `LLM_EMBEDDING_MODEL` | Model for RAG embeddings | `gemini/gemini-embedding-001` |

See [Section 13](#13-llm-provider-reference) for how to swap to OpenAI, Kimi, or other providers.

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

### Frontend (Vercel / Docker build args)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend Railway URL, e.g. `https://your-app.railway.app` |
| `VITE_SUPABASE_URL` | Same as `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | Same as `SUPABASE_ANON_KEY` |

> When building the frontend Docker image, these are passed as build args (see `frontend/Dockerfile.frontend`). They are baked into the static bundle at build time — not runtime env vars.

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

### Vercel (Frontend — SaaS)
1. Import the GitHub repo into Vercel
2. Set root directory to `frontend`
3. Framework preset: Vite
4. Add environment variables: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
5. Deploy — Vercel auto-deploys on every push to `main`

### Railway (Backend — SaaS)

The backend is fully containerised (`backend/Dockerfile.api`). Railway builds and deploys the Docker image automatically.

**Primary method: Docker image deploy (used in production)**
1. New project → Deploy from GitHub → select repo
2. Railway detects `backend/Dockerfile.api` and builds the Docker image automatically
3. No start command needed — the Dockerfile `CMD` runs `uvicorn backend.main:app`
4. Add all backend environment variables (Section 3)
5. Railway auto-deploys and rebuilds the Docker image on every push to `main`

**Alternative: Source deploy (no Docker)**
If running without Docker (e.g. local testing or a plain VPS):
1. New project → Deploy from GitHub → select repo
2. Set root directory: `/` (repo root)
3. Set start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add all backend environment variables (Section 3)

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
| `relationships` | Directed edges between entities (source, target, relationship type). LLM-derived edges carry a confidence score and evidence quote inside the `evidence` JSON; rule-derived edges do not. |
| `findings` | Flagged anomalies/red flags — pending human review (confirm/dismiss) |
| `timeline_events` | Chronological events extracted from documents, plus manually added events |
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
| GET | `/cases/{id}/timeline` | Required | Get timeline events (AI-extracted + manual) |
| POST | `/cases/{id}/timeline` | Required | Add a manual timeline event |
| PATCH | `/cases/{id}/timeline/{event_id}` | Required | Edit a timeline event |
| DELETE | `/cases/{id}/timeline/{event_id}` | Required | Delete a timeline event |
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

**Rules + LLM run together (not either/or).** Each case-level stage runs its deterministic rule pass **and** an LLM pass, then merges them: the provable rule rows are always kept, LLM rows are added on top, and an LLM row that duplicates a rule row is dropped in favour of the rule row (content-hash dedup). If the LLM pass returns nothing (bad key, rate limit, provider down) the rule rows still stand; if the rules find nothing the LLM rows still stand.

**Anti-hallucination guardrail.** Every LLM pass is grounding-validated: any output citing a `document_id`, entity, or event that was not actually sent to the model is dropped before it is persisted (`backend/pipeline/llm_reasoning.py`). LLM failures are swallowed for the caller and logged to `audit_log` with `action=case_reasoning_failed`, so a failing tier is diagnosable instead of silently looking like "nothing found."

**Deduplication:** Findings, relationships, and timeline events use content hashes to prevent duplicate rows on re-analysis.

### 8.1 RAG Pipeline (Retrieval & Chat)

The case Chat tab answers questions grounded in the case's own documents. The retrieval stack is deliberately simple and lives entirely inside Postgres (no separate vector DB).

**Chunking — layout-based, no fixed size, no overlap.**
Chunk boundaries are decided by **LandingAI ADE**, not a text splitter. Each chunk is one layout element ADE detects (paragraph, table, heading, list item), carrying its page number and bounding box. There is **no configurable chunk size and no sliding-window overlap** — a trade-off: chunks follow the document's natural structure, but context that spans a boundary is not duplicated across chunks.

**Embedding — Gemini 1536-dim, batched, fault-tolerant.**
Chunk text is embedded with `gemini-embedding-001` at 1536 dimensions (`backend/pipeline/extract.py`). Embedding runs in **batches of 100** (the provider's per-request cap) with retry-and-backoff on rate limits (3 retries, 20s backoff). If a batch still fails, those chunks are stored **text-only** (embedding `NULL`) rather than dropped, and the failure is logged to `audit_log` as `chunk_embedding_failed`. So a document is never silently lost to an embedding outage.

**Retrieval — dense by default, hybrid behind a flag.**
On a chat question, the question is embedded and matched against the case's chunks via the `match_chunks` Postgres function (cosine distance, `<=>`), returning the top `rag_top_k` (default **8**) chunks. The index is **HNSW** (approximate nearest-neighbour) over pgvector. If embedding is unavailable, chat falls back to a **keyword search** (matches salient words from the question against chunk text).

With `RAG_HYBRID_ENABLED=true`, retrieval instead runs **two arms and fuses them** (`backend/core/retrieval.py`):

| Arm | Mechanism | Catches |
|---|---|---|
| Dense | pgvector cosine over `embedding` | Paraphrase, narrative, conceptual similarity |
| Keyword | Postgres full-text (`ts_rank_cd`) over the generated `text_search` tsvector | Exact tokens — invoice/account/tender references, names, statute numbers |

Both arms take their top `rag_hybrid_pool` (default 50) **inside SQL, each filtered on `case_id`**, so tenant isolation is never left to application code. The two rankings are then combined with **Reciprocal Rank Fusion** (`score = Σ weight / (rrf_k + rank)`, default `rrf_k` 60) in Python, and the top `rag_top_k` are returned.

*Why RRF rather than blending the scores:* cosine similarity and `ts_rank_cd` live on different scales with different distributions, so their raw values are not comparable. Ranks are. Fusion also lives in Python rather than SQL on purpose — the constants are what `python -m backend.eval compare` tunes, and tuning must not require a database migration each time.

Fused rows carry `found_by` (`dense` / `keyword` / `both`) and `fusion_score`, so a surprising citation can be traced to the arm that produced it. If the hybrid RPC is missing or errors, retrieval **degrades to pure dense** and logs `hybrid_retrieval_failed` to the audit log rather than failing the request.

There is still **no reranking and no similarity threshold** — the top 8 after fusion are used as-is.

**Grounding & citations.**
The retrieved chunks are the only document context handed to the LLM, alongside case-level structured intelligence (entities, confirmed findings, relationships). The answer cites sources inline as `[n]`, and each citation carries the **page number and bounding box** from ADE's visual grounding, so the UI can jump to the exact spot in the source PDF. Across the analysis pipeline, LLM output that cites a `document_id`/entity/event not actually sent to the model is **dropped before persisting** (anti-hallucination guardrail, `backend/pipeline/llm_reasoning.py`).

**Known limitations / roadmap (RAG).**
- No sliding-window overlap between chunks.
- No reranking (cross-encoder) — the next retrieval change after hybrid.
- No minimum-similarity cutoff; weak matches can still enter the top-8 context.
- Hybrid retrieval is implemented but **off by default** and **not yet measured** — see §12.1. Its SQL migration has not been run against a live database yet.
- The eval harness exists (§12.1) but **no golden set has been authored**, so there is still no retrieval number to quote.

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
| **Entity Graph** | Interactive force-directed graph of entities and relationships. Edit mode: add/remove nodes and edges manually. |
| **Timeline** | Chronological events extracted from all documents. Add, edit, and delete events manually. Manually-added events shown with a "manual" badge. AI-extracted events linked to their source document. |
| **Findings** | AI-detected red flags pending human review. Confirm or dismiss each finding with optional dismissal reason. |
| **Report** | Generate a branded investigation report from confirmed findings. Custom sections and freeform instructions. |
| **Chat** | RAG-grounded Q&A — ask questions, get answers with document citations and page references. |

### Case Settings Tabs

| Tab | Description |
|---|---|
| **Details** | Edit case title, type, status, lead investigator, allegation summary |
| **Schema** | Customise extraction fields per case type |
| **Team** | Invite team members (role-gated), view member list, remove members |

---

## 10. Deployment Guide

### 10.1 Local Development

```bash
# Copy and fill in your environment variables
cp .env.example .env

# One-command local run (Docker required)
docker-compose up --build

# Or run services separately without Docker:
# Backend
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### 10.2 Current Deployment (SaaS — Vercel + Railway)

**Prerequisites:** GitHub repo, Supabase project, Railway account, Vercel account.

1. **Database:** Run `backend/schema.sql` in Supabase SQL Editor (full file, top to bottom)
2. **Storage:** Create `evidence` bucket in Supabase Storage → set to private
3. **Backend (Railway — Docker):**
   - New project → Deploy from GitHub → select repo
   - Railway detects `backend/Dockerfile.api` and builds the image automatically
   - Add all backend env vars (Section 3)
   - Note the Railway URL (e.g. `https://app-production-xxxx.up.railway.app`)
4. **Frontend (Vercel):**
   - Import repo → set root directory to `frontend`
   - Add env vars: `VITE_API_URL=<railway-url>`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
   - Deploy — Vercel auto-deploys on every push to `main`
5. **CORS:** Set `CORS_ALLOW_ORIGINS=<vercel-url>` in Railway env vars
6. **Domain (optional):** Add CNAME in DNS pointing to Vercel → configure in Vercel project settings

### 10.3 On-Prem / Private Deployment

The platform is fully containerised and can be self-hosted on any infrastructure.

**Option A: Docker Compose (simplest — own server or VPS)**
```bash
git clone <repo>
cp .env.example .env   # fill in all variables
docker-compose up -d --build
# Backend on :8000, Frontend on :80
# Add a reverse proxy (Nginx/Caddy) for TLS and a custom domain
```

**Option B: AWS**
| Component | Recommended service |
|---|---|
| Backend | AWS App Runner (reads Dockerfile from ECR or GitHub directly) or ECS Fargate |
| Frontend | AWS Amplify (static hosting with CI/CD) or CloudFront + S3 |
| Database | Continue on Supabase cloud, or use RDS Postgres with pgvector extension |
| Storage | S3 (Supabase Storage is S3-compatible — can swap the bucket URL) |

**Option C: Google Cloud (GCP)**
| Component | Recommended service |
|---|---|
| Backend | Cloud Run (serverless containers, scales to zero, no idle cost) |
| Frontend | Firebase Hosting or Cloud Storage + Cloud CDN |
| Database | Cloud SQL Postgres + pgvector extension, or continue Supabase |

**Option D: Azure**
| Component | Recommended service |
|---|---|
| Backend | Azure Container Apps or App Service (Docker) |
| Frontend | Azure Static Web Apps |
| Database | Azure Database for PostgreSQL + pgvector |

**Platform Admin for On-Prem Clients**
- Set `PLATFORM_ADMIN_EMAILS` to the **client's** IT admin email
- The client admin creates their own orgs, invites their own users — full autonomy
- NextGen Spark has **zero access** to client data
- For a licencing gate: a `LICENCE_KEY` check can be added to `backend/config.py` if needed

### 10.4 Future Hosting — Scaling to AWS / GCP

**Current stack (Railway + Vercel)** is well-suited for the current stage — fast deploys, managed infra, zero DevOps overhead. This remains the right choice through early growth.

**When to consider moving to AWS or GCP:**
- When the platform is offered as a true multi-tenant SaaS product with paying subscribers at scale
- When enterprise clients require specific compliance certifications (SOC 2, ISO 27001) that require infrastructure we control directly
- When usage volume makes managed platforms (Railway/Vercel) more expensive than running on raw cloud

**AWS (recommended for enterprise SaaS scale):**
- Backend: ECS Fargate or App Runner — managed containers, auto-scaling, no server management
- Frontend: CloudFront + S3 or Amplify — global CDN, low latency
- Database: RDS Postgres + pgvector, or keep Supabase cloud (it's just Postgres)
- Best for: high-volume deployments, multi-region, strict compliance requirements

**GCP (good alternative):**
- Backend: Cloud Run — serverless containers, scales to zero (no idle cost for inactive orgs)
- Frontend: Firebase Hosting or Cloud Storage + CDN
- Best for: cost efficiency with variable/unpredictable load

**Government / sensitive clients** → always on-prem or their own private cloud (see On-Prem section above). They own and control their own infrastructure entirely.

**Subscription logic and pricing tiers:**
The `plan` field already exists on the `organisations` table. When the business model is defined, feature gates and limits (number of cases, documents, users, API calls) are added against that field. Pricing tier names, limits, and billing integration (e.g. Stripe) are business decisions to be made when the SaaS model is formalised.

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
| `text_search` on chunks + `match_chunks_candidates()` | **Hybrid retrieval** — generated tsvector column, GIN index, and the dense+keyword candidate RPC. Adding the stored generated column rewrites the `chunks` table; run it in a maintenance window on a large corpus. Retrieval stays pure-dense until `RAG_HYBRID_ENABLED=true`. |

### 11.1 Tendering migration — `backend/schema_tendering.sql`

The Tendering product ships its schema as a **separate file**; `schema.sql` (investigation) is
untouched by it. Run it in the Supabase SQL Editor **after** `schema.sql`. Idempotent.

> **This file replaced an earlier draft.** The draft modelled a tender as a `cases` row with
> `case_type='tender'` plus a `tender_meta` side-table; that was rejected in favour of a
> dedicated `tenders` table. Section 0 of the migration drops the draft's tables. There is no
> data migration — the draft was never used against real tenders.

| Table | Purpose |
|---|---|
| `tenders` | The tender workspace. A dedicated table, **not** a flavour of `cases`. |
| `requirements` | One extracted obligation per row, keyed on `tender_id`. Mirrors the `findings` shape — same source/confidence columns, same `content_hash` dedup, same `human_review_status` state machine. |
| `supplier_documents` | The **org-level** supplier vault: uploaded once, citable by every tender the org bids on. Tracks issue/expiry dates and supersession. |
| `supplier_document_chunks` | The vault's own vector table. Separate from `chunks` so vault evidence and case evidence can never surface in each other's retrieval. |
| `evidence_links` | The join between a requirement and the vault document that satisfies it. AI proposes; a human approves. |
| `tasks` | Plain workflow CRUD. No AI writes here. |

It also adds nullable `tender_id` to the shared `documents`, `chunks`, and `audit_log` tables,
so tender documents reuse the whole upload → parse → chunk → embed pipeline rather than
duplicating it. Existing investigation rows keep their `case_id` and are untouched.

**Four invariants are enforced by the database, not by convention:**

- **`requirements_ai_must_cite`** — a requirement whose `source` is not `manual` is rejected
  unless it carries `source_document_id` **and** `source_page`. Rule 2, enforced by Postgres.
  `RequirementRecord` enforces the same rule earlier at model construction; the CHECK is the
  backstop for anything bypassing that model.
- **`evidence_links_ai_must_explain`** — an AI-proposed evidence link must carry a rationale
  and a score. A match a bidder cannot justify is worse than no match: they would submit on it.
- **`requirements_pending_dedup_idx`** — partial unique index on pending rows. A re-run cannot
  double-insert unreviewed rows, but confirmed/dismissed rows stay out of scope so a re-run can
  resurface something a human already ruled on.
- **`match_supplier_docs`** filters on `org_id` *inside SQL* (and excludes expired and
  superseded documents at the source), so vault isolation cannot be lost by an
  application-layer mistake. Rule 4.

### 11.2 Tendering API surface

Tenders are not cases, so this router owns `/tenders/*` end to end — including its own document
routes. Core Python is untouched by the product apart from chunk scoping in `extract.py` and
mounting the router in `main.py`.

| Route group | Endpoints |
|---|---|
| Tenders | `POST/GET /tenders`, `GET/PATCH/DELETE /tenders/{id}`, `POST /tenders/{id}/analysis` |
| Documents | `GET/POST /tenders/{id}/documents`, `POST /tenders/{id}/documents/{doc}/extract` |
| Requirements | `GET/POST /tenders/{id}/requirements`, `GET /tenders/{id}/compliance-matrix`, `PATCH /requirements/{id}`, `PATCH /requirements/{id}/review` |
| Vault (org) | `GET/POST /vault/documents`, `PATCH /vault/documents/{id}`, `POST /vault/documents/{id}/supersede/{new}` |
| Evidence | `POST /tenders/{id}/evidence-matching`, `GET/POST /requirements/{id}/evidence`, `PATCH /evidence/{id}/review` |
| Readiness | `GET /tenders/{id}/readiness` (fresh scan; `?narrative=true` adds prose), `POST /tenders/{id}/readiness` (re-run and persist the score) |
| Tasks | `GET/POST /tenders/{id}/tasks`, `PATCH/DELETE /tasks/{id}` |

**Rule 3 is structural.** Pipeline stages write `human_review_status='pending'` rows and nothing
else. `bid_decision`, requirement review, and evidence approval are reachable only through
human-invoked, access-checked handlers.

### 11.3 Submission readiness

`pipeline/readiness_review.py` audits a tender across requirements, evidence links, vault
expiry dates, documents, and tasks, and answers the question a bid manager asks the night
before a deadline: *what is missing, and can we submit?*

Three properties worth knowing:

- **The score is arithmetic, not judgement.** `compute_gaps` and `compute_score` are pure
  functions over database rows — no LLM decides readiness, so the number is reproducible and
  every point of it traces to a named gap. The LLM, when available, only writes prose *from*
  the computed report; it cannot introduce a gap or change the score.
- **Score and blockers are separate.** A percentage alone hides the one unmet mandatory
  requirement that gets a bid disqualified, so `submission_blocked` is its own boolean with its
  own reasons. A tender can read 75% and still be blocked — and the UI should lead with the
  blocker.
- **Gaps are computed on demand, never stored.** They derive entirely from current state, so a
  persisted copy would be stale the moment someone approves a document. Only the score is
  written back, onto `tenders.readiness_score`. It is advisory and never gating (Rule 3).

Mandatory requirements weigh 3× optional ones. A requirement counts as satisfied only when a
human marked it complete *or* it has an **approved** evidence link to a vault document that is
neither expired nor superseded — a pending AI proposal does not count.

The gap type that most justifies the stage: **`evidence_expires_before_closing`**. A
certificate valid today but expiring before the closing date will have lapsed at evaluation,
and it is invisible to every other check.

**Status:** all four slices are built — foundation, requirement extraction + compliance matrix,
vault + evidence matching, and submission readiness. Evidence matching has no golden set yet;
see `backend/apps/tendering/evidence_goldens.md` for what needs measuring before its thresholds
are tuned. That gap now also affects readiness, since readiness depends on evidence links.

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
| `tests/test_llm_reasoning_guardrails.py` | Anti-hallucination guardrails — LLM output citing unknown document IDs is dropped |
| `tests/test_timeline_and_classify.py` | Timeline event extraction/date parsing and document classification |
| `tests/test_eval_harness.py` | Retrieval eval harness — metric arithmetic, golden-set validation, runner behaviour |
| `tests/test_tendering_foundation.py` | Tendering foundation — schema resolution, classify labels, Rule 2 grounding validation, requirement dedup, core product dispatch, router wiring |
| `tests/test_tendering_requirements.py` | Requirement extraction — rule pass, chunk-level grounding guardrail, rule/LLM merge, batching, tender summary, metadata back-fill |
| `tests/test_tendering_evidence.py` | Evidence matching — retrieval shortlisting, grounding guardrail, score clamping, expiry handling, match query |
| `tests/test_tendering_readiness.py` | Submission readiness — satisfaction rules, weighted scoring, gap detection and severity, blocker ordering, narrative |

### Design Principles

- LLM calls are mocked in tests — no real API calls, no cost, no flakiness
- Tests cover both the happy path and edge cases (empty/clean corpus, duplicate inserts, ungrounded LLM output)
- Access control tests cover every role combination explicitly

> Coverage is on the deterministic pipeline logic and access control (pure, DB-free functions). API endpoints and the org/invitation flow are not yet covered by automated tests.

### 12.1 Retrieval Evaluation Harness (`backend/eval/`)

Unit tests prove the pipeline logic is correct. They say nothing about whether retrieval finds
the *right* chunks — which is the ceiling on every answer the system gives, since a chunk that
is never retrieved can never be cited. The harness measures that.

```bash
python -m backend.eval lint --golden backend/eval/goldens/investigation.yaml   # validate a golden set
python -m backend.eval run  --golden backend/eval/goldens/investigation.yaml   # score the live retriever
python -m backend.eval run  --golden ... --record backend/eval/fixtures/dense-baseline.json
python -m backend.eval compare --golden ... --baseline <fixture> --candidate hybrid --fail-on-regression
```

| Module | Role |
|---|---|
| `goldens.py` | Golden-set schema + loader. Rejects questions with no ground truth. |
| `metrics.py` | recall@k, precision@k, hit@k, MRR, nDCG@k, abstention. Pure functions, no I/O. |
| `retrievers.py` | The A/B seam — `DenseRetriever` (production path), `KeywordRetriever` (the degraded fallback), `FixtureRetriever` (offline replay). |
| `runner.py` | Runs a golden set, scores it, records/compares fixtures. |
| `report.py` | Console, markdown, and comparison formatting. |

**Two properties worth knowing:**

1. **Validated vs unvalidated is enforced, not advisory.** A golden question whose `validated_by`
   is empty is scored into a *provisional* bucket and excluded from the headline number. Ground
   truth nobody has checked measures nothing — and in a forensic context an unverified metric is
   worse than none, because it looks like evidence.
2. **Negative questions are first-class.** Questions the corpus genuinely cannot answer are scored
   on whether the system *declines*, not on retrieval. Confident invention is the failure mode that
   matters most here, and it is otherwise unmeasured.

**Status:** the harness is built and tested; **no golden set has been authored yet.** It needs a
domain expert to write questions against real cases and verify the ground truth by hand — see
`backend/eval/goldens/README.md` for the workflow and
`backend/eval/goldens/examples/investigation.example.yaml` for the question shapes to cover.
Until that exists, there is no retrieval number to quote.

---

## 13. LLM Provider Reference

The platform uses **LiteLLM** as a provider-agnostic router. Switching models requires only environment variable changes — no code changes. The provider prefix (e.g. `groq/`, `openai/`, `moonshot/`) tells LiteLLM which API to call.

### Supported Providers

| Provider | Env var needed | Example model string |
|---|---|---|
| **Groq** (default) | `GROQ_API_KEY` | `groq/llama-3.3-70b-versatile` |
| **OpenAI** | `OPENAI_API_KEY` | `openai/gpt-4o`, `openai/gpt-4o-mini` |
| **Kimi (Moonshot)** | `MOONSHOT_API_KEY` | `moonshot/moonshot-v1-8k`, `moonshot/moonshot-v1-32k` |
| **Anthropic (Claude)** | `ANTHROPIC_API_KEY` | `anthropic/claude-3-5-sonnet-20241022` |
| **Google Gemini** | `GEMINI_API_KEY` | `gemini/gemini-1.5-pro` (reasoning), `gemini/gemini-embedding-001` (embeddings) |
| **Azure OpenAI** | `AZURE_API_KEY` + `AZURE_API_BASE` | `azure/<your-deployment-name>` |

### Switching Providers

To switch the reasoning model to OpenAI GPT-4o:
```env
OPENAI_API_KEY=sk-...
LLM_REASONING_MODEL=openai/gpt-4o
LLM_FAST_MODEL=openai/gpt-4o-mini
LLM_CASE_REASONING_MODEL=openai/gpt-4o
```

To switch to Kimi (Moonshot):
```env
MOONSHOT_API_KEY=sk-...
LLM_REASONING_MODEL=moonshot/moonshot-v1-32k
LLM_FAST_MODEL=moonshot/moonshot-v1-8k
LLM_CASE_REASONING_MODEL=moonshot/moonshot-v1-32k
```

The embedding model (`LLM_EMBEDDING_MODEL`) is independent — Gemini embeddings work alongside any reasoning provider and should be changed separately only if migrating to a different vector dimensionality (which would require re-embedding all chunks).

### Notes

- Groq free tier is generous and fast — recommended for development
- OpenAI GPT-4o gives the best reasoning quality for production deployments
- Kimi (Moonshot) is a strong option for deployments where data sovereignty in specific regions matters
- If a reasoning LLM call fails (bad key, rate limit, etc.), the pipeline falls back to rule-based results automatically and logs the failure to `audit_log`

---

## 14. Service Accounts

All external service accounts (Railway, Vercel, Supabase, Groq, LandingAI, Resend, Google AI Studio, GitHub) are created and managed under the company account. API keys and secrets are **never stored in this repository** — they live in Railway environment variables, Vercel project settings, and the local `.env` file (git-ignored).

---

*Last updated: July 2026 — ADI v0.1 (multi-tenancy + Docker release). Added §8.1 RAG Pipeline; corrected relationship-schema, rule+LLM merge, and testing-coverage notes.*
