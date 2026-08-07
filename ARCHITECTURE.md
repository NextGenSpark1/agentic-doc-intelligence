# Architecture — Tendering Intelligence as an Extension of the Shared Document Intelligence Core

> **Status:** Design proposal (no implementation code yet).
> **Author:** Nawran (Backend / Architecture / Data Pipeline Lead).
> **Scope:** How Tendering Intelligence *extends* the existing Investigation Intelligence backend into a shared **Document Intelligence Core**, per the Tendering Intelligence Development Roadmap (Rule 1: *no duplicate pipelines*).

This document maps the roadmap onto the code that already exists in this repository. Every "reuse" claim below points at a real module. The goal is a design where Tendering adds **schemas, prompts, config, and a small number of genuinely-new components** — and reuses everything else.

---

## 0. Grounding — what already exists

The audit of the current backend establishes the reusable substrate. These are real modules, not aspirations:

| Capability | Where it lives today | Coupling to "investigation" |
|---|---|---|
| Document upload + Supabase Storage | `backend/main.py` (`upload_document`), `db.upload_evidence` | None — generic |
| Parse + extract (ADE) | `backend/ade_client.py` | None — schema-driven |
| Schema routing by type | `backend/schemas/investigation.py` → `SCHEMA_REGISTRY`, `schema_for_case_type()` | **Registry keyed by case_type** — the extension seam |
| Classification | `backend/pipeline/classify.py` (`KNOWN_TYPES`, `_HEURISTICS`, LLM + fallback) | Labels are investigation-flavoured |
| Chunk + embed + index | `backend/pipeline/extract.py` (`_index_chunks`, batched 100, degrade-to-text) | None — generic |
| Vector search / RAG | `db.match_chunks`, `db.match_chunks_in_document`, chat in `main.py` | None — generic |
| LLM routing (tiers) | `backend/llm.py` (`fast` / `reasoning` / `case_reasoning`), `backend/config.py` | None — model strings only |
| Case-reasoning + grounding guardrail | `backend/pipeline/llm_reasoning.py` (`ask()` drops ungrounded output, logs `case_reasoning_failed`) | None — the guardrail is domain-agnostic |
| "AI record pending human review" | `findings` table + `detect()` + `human_review_status` (`pending`/`confirmed`/`dismissed`) | **Semantics are fraud-review; the pattern is general** |
| Entity resolution / relationships / timeline | `backend/pipeline/resolve_entities.py`, `build_relationships.py`, `reconstruct_timeline.py` | Rules are investigation-specific; the rule+LLM merge pattern is general |
| Dedup on re-analysis | `db._content_hash`, partial/unique indexes in `schema.sql` | None — generic |
| AuthN | `backend/auth.py` (Supabase JWT, HS256/RS256) | None — generic |
| Multi-tenancy / RBAC | `backend/orgs.py`, `_assert_case_access`, `_load_case_or_403` in `main.py` | None — org/role model is generic |
| Audit log | `db.write_audit`, `audit_log` table | None — generic |

**Reuse verdict:** ~65–70% of the backend is direct reuse. The new surface is tender **schemas, prompts, a requirement-extraction stage, a compliance/readiness layer, a supplier vault, and cross-corpus evidence matching.**

---

## 1. Extension mechanism — how Tendering plugs in without a new pipeline

The core already has the right seam: **the pipeline is schema-and-config-driven, not hardcoded per domain.** `run_extraction()` in `extract.py` already picks its extraction schema from `schema_for_case_type(case.get("case_type"))`. That indirection is the whole extension story — we widen it from "case type" to "**workspace type**".

### 1.1 Package restructure — `core/` vs `apps/` (the one decision that matters)

The roadmap says "convert to a reusable NextGen Document Intelligence Core." Concretely:

```
backend/
├── core/                      # Shared Document Intelligence Core (domain-agnostic)
│   ├── ade_client.py          # (moved as-is)
│   ├── llm.py                 # (moved as-is)
│   ├── db.py                  # generic table helpers + _content_hash + tenancy filters
│   ├── auth.py                # (moved as-is)
│   ├── orgs.py                # org/role/invite model (moved as-is)
│   ├── config.py              # base settings
│   ├── pipeline/
│   │   ├── classify.py        # engine only; label sets injected by the app
│   │   ├── extract.py         # engine only; schema resolved via a registry
│   │   ├── llm_reasoning.py   # ask() + grounding guardrail (moved as-is)
│   │   └── ingest_files.py    # NEW shared: zip-unpack, xlsx/docx pre-normalise (see §2)
│   ├── registry.py            # NEW: workspace-type → {schemas, prompts, stages, labels}
│   └── review.py              # NEW: generalised "AI record pending human review" base
│
├── apps/
│   ├── investigation/         # existing product, re-expressed as an app on core
│   │   ├── schemas.py         # FinancialTransaction, ProcurementRecord, ... (moved)
│   │   ├── prompts.py         # findings/relationship prompts (moved)
│   │   ├── stages.py          # detect_anomalies, resolve_entities, ... (moved)
│   │   └── routes.py          # /cases/* endpoints
│   └── tendering/             # NEW app
│       ├── schemas.py         # Tender, Requirement, SupplierDocument (NEW)
│       ├── prompts.py         # tender extraction / readiness prompts (NEW)
│       ├── stages.py          # requirement extraction, readiness, evidence match (NEW)
│       └── routes.py          # /tenders/* endpoints
└── main.py                    # mounts both apps' routers on one FastAPI instance
```

**Why a shared package and not a fork:** a fork always diverges — a fix to embedding batching or the grounding guardrail would have to be applied twice and drift. A `core/` package imported by both apps is the *only* structure that keeps Rule 1 true beyond week one. **This refactor must happen before tender code is written**, not "extracted later" — later never comes.

### 1.2 The extension registry (the seam, generalised)

Replace the single `SCHEMA_REGISTRY` keyed on case type with a **workspace-type registry** that binds a type to its schemas, prompt set, pipeline stages, and classifier labels:

```
# core/registry.py  (shape, not implementation)
WorkspaceType = "investigation" | "tender"

REGISTRY[WorkspaceType] = {
    "extraction_schemas": {...},     # doc_type -> pydantic schema  (drives ADE extract)
    "classifier_labels": [...],      # replaces classify.KNOWN_TYPES
    "classifier_heuristics": {...},  # replaces classify._HEURISTICS
    "prompts": {...},                # named prompt templates for each stage
    "analysis_stages": [...],        # ordered stage callables for "run analysis"
}
```

- `extract.py` calls `registry[ws_type].extraction_schemas[doc_type]` instead of `schema_for_case_type`.
- `classify.py` receives its label set + heuristics from the registry instead of module constants.
- `run_case_analysis()` becomes `run_analysis(workspace_id)` that iterates `registry[ws_type].analysis_stages` — so investigation runs entity/relationship/timeline/findings, and tendering runs requirement-extraction/compliance/readiness, **through the same orchestrator with the same failure-audit wrapper**.

**Net:** Tendering introduces new *values* in the registry and new *stage functions*, but the ingestion → parse → chunk → embed → index path and the orchestration/guardrail/dedup machinery are untouched.

### 1.3 Prompt templates as data, not code

Today prompts are module-level string constants (e.g. `_FINDINGS_PROMPT`, `_RELATIONSHIP_PROMPT`). For Tendering they become **named templates registered per workspace type** and passed into the shared `llm_reasoning.ask(system_prompt, payload, workspace_id)` helper — which already enforces the grounding guardrail regardless of which prompt it runs. No new LLM plumbing.

---

## 2. Roadmap Layer-2 function map — config/prompt extension (a) vs new component (b)

For each Layer-2 function: whether it's a **(a) config/prompt extension** of an existing stage, or a **(b) genuinely new component** (with justification).

| # | Layer-2 function | Type | How it maps | Reuses |
|---|---|---|---|---|
| 1 | **Tender information extraction** (title, buyer, ref, dates, bonds…) | **(a)** | New `Tender` extraction schema + prompt registered in the registry; runs through `ade_client.extract` exactly like `FinancialTransaction` does today | `extract.py`, ADE path, extraction persistence |
| 2 | **Eligibility extraction** | **(a)** | Fields on the `Requirement` schema + a category value (`legal`/`financial`/`certification`); an extraction prompt variant | Requirement extraction stage (#3) |
| 3 | **Requirement extraction** (structured records w/ clause + page) | **(b, small)** | New analysis stage `extract_requirements()` — LLM pass over each tender doc producing many `Requirement` rows per doc. Justify (b): it's *one-doc → many structured child records with clause-level grounding*, a shape the current per-doc single-extraction (`extractions` = one JSON blob per doc) doesn't produce. But it reuses `llm_reasoning.ask` + the grounding guardrail + `content_hash` dedup wholesale. | guardrail, dedup, chunk store |
| 4 | **Mandatory requirement detection** | **(a)** | A boolean/enum field (`mandatory`) on the requirement extraction prompt; no separate stage | #3 |
| 5 | **Submission instruction extraction** | **(a)** | A requirement `category = "submission_instruction"` + prompt coverage | #3 |
| 6 | **Evaluation criteria extraction** | **(a)** | Extraction schema section / prompt; stored as structured records (may be its own light schema `EvaluationCriterion` if scored weights matter) | #1/#3 machinery |
| 7 | **Risk / disqualification detection** | **(b, small)** | Analysis stage analogous to `detect_anomalies` — but the *rules* are tender-specific (missing mandatory doc, expired cert, deadline conflict). Justify (b): different rule content + output semantics; **reuses the exact rule+LLM-merge pattern, `_dedupe_*`, `source`/`confidence` tagging, and grounding guardrail** from `detect_anomalies.py`. This is a *sibling stage*, not a new pipeline. | rule+LLM merge pattern, guardrail, dedup |
| 8 | **Compliance matrix generation** | **(a) + view** | The matrix is a **read-model / view over `Requirement` rows** (group by category, join `EvidenceLink` + `Task` status). No new extraction — it's aggregation + a frontend table. Backend: query endpoints only. | Requirement rows, RBAC |
| 9 | **Bid/No-bid assessment** | **(b)** | New component: a scored assessment over the 10 criteria. Justify (b): it's a *decision-support scorer* with human-owned final decision (Rule 3), not document extraction. Reuses `summarise.py`'s pattern (deterministic score + LLM narrative from structured facts) and its "LLM writes only from derived facts" discipline. | summarise pattern, LLM tier |
| 10 | **Tender clarification tracking** | **(a) + CRUD** | Mostly a structured `Clarification` table + CRUD endpoints (like the existing timeline CRUD `7f521169`). Minimal AI (optional: link a clarification to affected requirements). | timeline-CRUD pattern |
| 11 | **Submission readiness review** | **(b)** | New component `readiness_review()` producing a **Submission Readiness Score** + a checklist of gaps (missing forms, expired certs, unanswered clauses, unread addenda). Justify (b): it's a *cross-record completeness audit* spanning requirements, evidence links, tasks, and the supplier vault — genuinely new logic. Reuses: findings/review pattern for each gap, grounding for document-linked gaps, audit log. | review pattern, guardrail |
| 12 | **Evidence matching** (requirement ↔ supplier vault) | **(b, the hard one)** | New component + **a second retrieval index**. Justify (b): current RAG matches *chunks within one case*; this matches **requirements against a separate, org-scoped supplier-document corpus** (cross-corpus retrieval). Reuses the embedding path and pgvector, but needs a vault embedding store and a new match function (`match_supplier_docs(org_id, requirement_embedding)`). **This is the piece most exposed by our missing eval harness** — a wrong match on a live bid has real cost, so it needs measurement from day one. | embed path, pgvector, org isolation |

**Summary:** 6 of 12 are **(a)** pure config/prompt extensions. 6 are **(b)**, but *five of those six are "sibling stages" that reuse the orchestration, grounding guardrail, dedup, and review-record patterns* — only **evidence matching (#12)** introduces genuinely new retrieval infrastructure.

---

## 3. Data-model reconciliation — roadmap entities vs existing schema

Existing tables (from `backend/schema.sql`): `cases`, `documents`, `extractions`, `chunks`, `entities`, `relationships`, `findings`, `timeline_events`, `audit_log`, `organisations`, `org_members`, `invitations`.

| Roadmap entity | Existing equivalent | Decision | Conflict / duplication flag |
|---|---|---|---|
| **Organisation** | `organisations` (has `org_id`, name, plan, created_by) | **Reuse as-is** | ⚠️ Roadmap lists `registration_number`, `industry`, `address` — add as nullable columns; do **not** create a second org table |
| **User** | `org_members` (user↔org, role, invited_by) + Supabase Auth user | **Reuse as-is** | ✅ Roles already exist (org_admin/supervisor/member); tender "access permissions" map onto the existing RBAC |
| **Tender** | `cases` (title, type, status, org_id, created_by, risk_score) | **Reuse the table, generalise the name** | ⚠️ **Naming conflict.** `cases` is investigation-flavoured. Options: (a) keep `cases` as the generic "workspace" table with `workspace_type` discriminator + tender-specific columns (`buyer`, `closing_date`, `contract_value`, `tender_stage`, `bid_decision`, `readiness_score`) nullable; (b) a separate `tenders` table. **Recommend (a)** — one workspace table with a type discriminator keeps `_load_case_or_403`, audit, and RBAC working unchanged. `risk_score` ↔ `readiness_score` are the same column role. |
| **Tender Document** | `documents` | **Reuse as-is** | ✅ Add tender `document_type` values (tender notice, ITT, BOQ…) as classifier labels; `documents` is already generic. Roadmap's `version` → maps to the roadmap's own "document versioning" Core item (not yet built — new nullable column). |
| **Requirement** | *(none — closest is `findings`)* | **NEW table** | ✅ Genuinely new. But **model it on `findings`**: reuse `source`, `confidence`, `content_hash`, `human_review_status`, `supporting_document_ids`, + add `clause`, `page`, `category`, `mandatory`, `owner`, `completion_status`. Do not overload `findings`. |
| **Supplier Document** | *(none)* | **NEW table** + **NEW vault storage scope** | ✅ New. Org-scoped (not tender-scoped) — a reusable corpus. Needs its own chunk/embedding rows for evidence matching (#12). |
| **Evidence Link** | *(none — conceptually like `relationships`)* | **NEW table** | ✅ New: `requirement_id ↔ supplier_document_id`, `ai_relevance_score`, `ai_reason`, `user_approval_status`. Shares the "edge with confidence + human approval" shape of `relationships`, but semantically distinct — keep separate. |
| **Task** | *(none)* | **NEW table** | ✅ New. Simple CRUD (assigned_user, due_date, status). No AI. |
| **Audit Event** | `audit_log` | **Reuse as-is** | ⚠️ Roadmap wants `previous_value`/`new_value`; current `audit_log` has a generic `detail jsonb`. Store the before/after inside `detail` — do **not** add a parallel audit table. |

**Conflicts to resolve explicitly:**
1. **`cases` vs `Tender`** — the biggest one. Recommend generalising `cases` → a workspace table with a `workspace_type` discriminator, rather than a parallel `tenders` table, so all tenancy/audit/RBAC code stays shared. (If product/reporting reasons favour a separate table, that's a conscious trade for more shared-code branching.)
2. **`findings` vs `Requirement`** — resist the temptation to reuse `findings`. Same *pattern*, different *entity*; overloading it would tangle two products' review workflows. New table, shared base behaviour via `core/review.py`.
3. **Org fields** — extend `organisations` in place; never a second org concept.

---

## 4. Enforcing the roadmap's hard rules in the design

### Rule 2 — every AI finding needs document / page / clause source + confidence

**Already enforced by the core; extended for clause-level.** The current guardrail in `llm_reasoning.ask` drops any LLM output citing a `document_id` not sent to the model, and `findings`/`relationships` already carry `confidence` and `supporting_document_ids`; citations already carry `page` + `bbox` (`CitationSchema` in `shared/schemas.py`, populated from ADE grounding).

Design commitments for Tendering:
- The `Requirement` schema **requires** `source_document_id`, `page`, and (where the model can produce it) `clause` + `extracted_source_text` + `confidence` — mirroring `finding._finding(...)`.
- The requirement/risk extraction stages run through the **same `llm_reasoning.ask` grounding validator** — a requirement citing a document/clause not in the input is dropped before persistence, exactly as findings are today.
- No requirement or readiness gap is returned to the UI without `{document_name, page, clause?, source_text, confidence?}`. Enforced at the schema level (non-nullable source fields), not just by prompt.

### Rule 3 — AI may extract/suggest/flag but never auto-confirm/approve/decide

**Enforced by the existing human-review state machine, extended to new record types.** Today every `finding` is born `human_review_status="pending"` and only a human `PATCH /findings/{id}/review` moves it to `confirmed`/`dismissed`. The design applies the identical pattern:
- **Requirements** → `user_validation_status` (pending → accepted/rejected by a human).
- **Evidence links** → `user_approval_status` (AI proposes with `ai_relevance_score` + `ai_reason`; a human approves before it counts toward the submission).
- **Bid/no-bid** → the scorer returns a *recommendation* object; the `bid_decision` field on the workspace is only writable by a human endpoint, never by a pipeline stage.
- **Submission** → there is no API path by which a pipeline stage can mark a tender "submitted" or "compliant". Those transitions live behind human-only, RBAC-gated endpoints.

Structurally: **pipeline stages write `*_status = 'pending'` rows only; state advancement lives exclusively in human-invoked, access-checked route handlers.** This makes Rule 3 an architectural invariant, not a prompt instruction the model could ignore.

### Rule 4 — strict tenant isolation across DB, storage, vector search, logs, caches, jobs

**Reuse the isolation we just hardened; extend it to the new surfaces.**

| Surface | Mechanism | Status |
|---|---|---|
| DB records | `org_id` scoping + `_load_case_or_403` on every workspace route; `list_cases(org_id, created_by)` team-scoping | ✅ Exists; generalise the helper to `_load_workspace_or_403` |
| File storage | Storage paths are `{workspace_id}/{doc_id}/...`; signed URLs only issued after the access check | ✅ Exists; **supplier vault must be `{org_id}/vault/...`** and access-checked by org membership |
| Vector search | `match_chunks(case_id, …)` is workspace-scoped; **new** `match_supplier_docs` **must filter by `org_id`** | ⚠️ New path — org filter is mandatory in the RPC's `WHERE`, not just app-side |
| AI retrieval | Chat/evidence prompts only receive chunks already scoped by the access-checked query | ✅ Pattern exists; applies to evidence matching by construction |
| Logs / audit | `audit_log` rows carry `case_id`/`org_id`; reads are access-checked | ✅ Exists |
| Caches | `get_settings()` is the only process-level cache; **no per-tenant data is cached in-process** — keep it that way (any future cache must be keyed by `org_id`) | ✅ By current design; documented constraint |
| Background jobs | Pipeline runs in FastAPI `BackgroundTasks` keyed by a workspace_id that was access-checked at enqueue time | ✅ Exists; the job re-reads scoped data via `org_id`/workspace_id — it never widens scope |

**New isolation obligations introduced by Tendering:**
1. The **supplier vault** is a new *org-scoped* corpus (not workspace-scoped) — its storage prefix, table rows, and embedding rows must all filter on `org_id`, and evidence matching must never retrieve across orgs. This is the single most important new isolation boundary and should get an explicit access-control test (mirroring `tests/test_access_control.py`).
2. `match_supplier_docs` RPC must embed the `org_id` filter **in SQL** (like `match_chunks` embeds `case_id`), so isolation can't be lost by an app-layer mistake.

---

## 5. Sequencing (so "extract core later" doesn't become "never")

1. **Refactor to `core/` + `apps/investigation/`** with the registry seam — behaviour-preserving, tests stay green. *(Do this first; it's the whole plan's foundation.)*
2. **`apps/tendering/` schemas + prompts + classifier labels** → tender summary + requirement extraction + compliance matrix. This is the fast, demoable reuse win (Layer-2 #1–#8a).
3. **Supplier vault + evidence matching (#12)** — the new retrieval index; pair it with a small eval set from day one.
4. **Bid/no-bid + submission-readiness (#9, #11)** — decision-support scorers on top of the structured data.
5. **Clarifications + tasks CRUD (#10)** — low-AI, standard CRUD.

---

## 6. Risks / open decisions for the team

- **`cases` → workspace table generalisation vs separate `tenders` table** — recommend generalising; needs sign-off because it touches shared tenancy code. *(§3, decision 1.)*
- **New file types (Word/Excel/ZIP)** — the roadmap assumes them; ADE-first ingestion needs a pre-normalise step (`core/pipeline/ingest_files.py`) before parse. Small but easy to under-scope.
- **Evaluation harness is now non-optional** — evidence matching and readiness scoring are decisions users act on with money; the eval gap identified for Investigation RAG must be closed here first.
- **Scope realism** — supplier vault, evidence matching, and readiness scoring are each mini-projects; sequence per §5 rather than building all ten MVP functions in parallel.

---

*This is a design document. No implementation code has been written. It describes how Tendering Intelligence extends the Shared Document Intelligence Core through schemas, prompts, config, a workspace-type registry, and a small set of justified new components — reusing the ingestion, retrieval, orchestration, grounding-guardrail, dedup, tenancy, and audit machinery that already exists.*
