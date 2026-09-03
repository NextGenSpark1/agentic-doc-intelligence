# Tendering Compliance — Build Plan

> How we build `apps/tendering/` on top of the shared `core/`, following the same patterns the
> Investigation app already proves. Plan only — no code yet. For team review.
>
> **Decisions locked in:** Supplier Vault is **org-level (shared across a company's tenders)** ·
> tender tables ship as a **separate SQL migration** (investigation schema untouched) ·
> Tendering is its **own product/dashboard** sharing one backend (Option A).

---

## 1. What we're building (one line)

A supplier-side product that reads a tender document set and turns it into a **structured,
trackable compliance plan** — requirements → evidence → readiness score — reusing everything in
`core/` (upload, OCR, chunk, embed, vector search, chat, auth, orgs, audit).

Not a chatbot on documents. Structured records that drive dashboards and workflow.

---

## 2. What we reuse from `core/` (already built — zero new work)

| Capability | Lives in | Tendering uses it… |
|---|---|---|
| Storage + document/chunk tables | `core/db_core.py` helpers | reused as-is (tender docs are rows in the same `documents`/`document_chunks` tables — see §5) |
| OCR / parsing | `core/ade_client.py` | as-is |
| Chunk + embed | `core/extract.py` | as-is (RAG for tender docs) |
| Vector search | `core/db_core.py` `match_chunks` | as-is (chat over a tender) |
| Classify engine | `core/classify.py` | pass **tender labels** |
| Extraction engine | `core/extract.py` `run_extraction(doc, case, schema_resolver)` | pass **tender schema resolver** |
| Auth / orgs / roles / tenant isolation | `core/auth.py`, `core/orgs.py` | as-is |
| Access-guard pattern | `core/access.py` `load_case_or_403` | **mirrored, not reused** — tenders get a new `load_tender_or_403` (a tender is its own row, not a case) |
| Audit log | `core/db_core.py` `write_audit` | as-is |

**The two seams we built ahead of time both get used here:** `classify(md, known_types, heuristics)`
and `run_extraction(doc, case, schema_resolver)`. Core never imports a product.

---

## 3. What Tendering adds — the 10 MVP pieces

| # | Piece | New file(s) | Difficulty |
|---|---|---|---|
| 1 | Tender extraction schemas | `apps/tendering/schemas.py` | 🟢 |
| 2 | Tender DB tables + queries | migration + `apps/tendering/db.py` | 🟢 |
| 3 | Tender classify labels | `apps/tendering/classify.py` | 🟢 |
| 4 | Tender summary (buyer, dates, bonds, eligibility — cited) | in pipeline | 🟡 |
| 5 | **Requirement extraction** (each requirement → structured record) | `apps/tendering/pipeline/extract_requirements.py` | 🟡 core value |
| 6 | Compliance matrix + routes (assign, attach, mark complete) | `apps/tendering/routes.py` | 🟡 |
| 7 | Supplier Document Vault (org-level, reusable, expiry-tracked) | migration + vault routes | 🟡 |
| 8 | **Evidence matching** (vault docs → requirements) | `apps/tendering/pipeline/evidence_matching.py` | 🔴 the hard one |
| 9 | Submission-readiness review (missing/expired/unanswered → score) | `apps/tendering/pipeline/readiness_review.py` | 🟡 |
| 10 | Router wired into `core/main.py` | one `include_router` line | 🟢 |

---

## 4. Target structure (mirrors `apps/investigation/`)

```
backend/apps/tendering/
├── __init__.py
├── schemas.py          # Tender, Requirement, SupplierDocument, EvidenceLink, Task
├── classify.py         # tender doc-type labels → core classify engine
├── db.py               # tender-table queries + facade over core.db_core
├── routes.py           # /tenders, /requirements, /compliance, /vault, /readiness
└── pipeline/
    ├── __init__.py             # orchestrator (mirrors investigation's)
    ├── extract_requirements.py # NEW
    ├── summarise_tender.py     # NEW (tender summary)
    ├── evidence_matching.py    # NEW (hard: second retrieval index)
    └── readiness_review.py     # NEW
```

`apps/tendering/db.py` re-exports `core.db_core` (the same facade trick investigation uses) so
tender code has one unified `db` object.

---

## 5. Data model (new tables — separate migration)

All tables carry `org_id` for tenant isolation, matching core's pattern. **Tenders are their own
tables, not a flavour of `cases`** (settled — see §8): the tender data model is genuinely different
(buyers, references, bid decisions, readiness scores, requirements), so a type-flag on `cases` would
get messy.

- **`tenders`** *(dedicated table)* — `tender_id (TEN-YYYY-XXXX), org_id, owner_id, title, buyer,
  reference_no, closing_date, estimated_value, submission_method, bid_decision, readiness_score,
  status, created_at, …`. Its own CRUD + a new `load_tender_or_403` guard mirroring the case guard.
- **`requirements`** — `id, tender_id, description, category, is_mandatory, source_document_id,
  source_page, source_clause, required_evidence, owner_id, status, ai_generated, human_review_status`.
  (Deliberately mirrors the `findings` shape — same "AI record pending human review" pattern.)
- **`supplier_documents`** (the vault) — `id, org_id, doc_type, title, storage_path, issued_date,
  expiry_date, version, superseded_by`. **Org-scoped, not tender-scoped.**
- **`supplier_document_chunks`** (vault vector index) — mirrors `document_chunks`, `org_id`-scoped, so
  evidence matching can embed + search the vault **without touching investigation's RAG** (settled —
  see §8).
- **`evidence_links`** — `id, requirement_id, supplier_document_id, match_score, rationale,
  human_review_status`. The join between a requirement and the vault doc that satisfies it.
- **`tasks`** — `id, tender_id, requirement_id, assignee_id, status, due_date`.

**Tender documents** (the uploaded tender PDFs) reuse the shared `documents` + `document_chunks`
tables — **`documents.case_id` becomes nullable and a nullable `documents.tender_id` FK is added** so
a document belongs to a case *or* a tender (settled — see §8). This is one additive, low-risk change
to the shared `documents` table; investigation rows are untouched (their `tender_id` is null). The
whole extraction/chunk/embed pipeline is reused unchanged — it already keys on `document_id`.

---

## 6. Core changes required (minimal & additive)

Because tenders own their routes and tables, the tender work is almost entirely additive under
`apps/tendering/`. The only shared surface it touches:

1. **Shared `documents` migration** — `documents.case_id` becomes **nullable** and a nullable
   `documents.tender_id` FK is **added**. This is the one change to a shared table. It's additive and
   safe: every existing investigation row keeps its `case_id` and gets `tender_id = null`, so nothing
   about investigation changes.

**No change to `core/main.py` Python is needed.** The tender router owns its own
`/tenders/{tender_id}/documents/*` routes (upload, list, extract, extraction, summary, file-url,
chunks). These are thin mirrors of core's case-document routes — they call the exact same `core.db_core`
helpers and the same `extract` engine, but guard with `load_tender_or_403` and set `tender_id`. Core's
existing `/cases/...` routes (and their hardcoded investigation pipeline call) stay exactly as they are.

- `load_tender_or_403` lives in `apps/tendering` (it reads the `tenders` table), mirroring
  `core/access.py`'s `load_case_or_403`. It is not a core concern.
- The tender router's `/extract` calls `apps.tendering.pipeline.process_document` directly — no
  product-dispatch branch needed, since tender docs never flow through core's case route.

> **Optional dedup (not for MVP):** the ~7 tender document routes duplicate core's case-document route
> bodies. If that duplication grates later, extract the handler logic into a shared `core` helper that
> takes an owner (case or tender) and have both routers call it. Deferred — keeping investigation
> untouched is worth the small duplication for now.

---

## 7. Recommended build order (4 slices)

1. **Foundation** (items 1-3, 10 + the §6 migration) — tender schemas, the tender-tables migration
   (incl. the additive `documents.tender_id`), `tenders` CRUD + `load_tender_or_403`, the tender router
   with its own document routes, and tender classify labels. Outcome: create a tender workspace, upload
   docs, they get classified/extracted with tender schemas. Reuses core's engine + document tables.
   Demoable, low-risk.
2. **Value slice** (items 4-6) — tender summary + requirement extraction + compliance matrix.
   Outcome: upload a tender → get a structured requirements checklist the team can work. The "wow".
3. **Vault + matching** (items 7-8) — org-level vault + evidence matching (the second retrieval
   index). The genuinely new AI work. Build the eval harness here (see §9).
4. **Readiness** (item 9) — pre-submit scan + readiness score.

Each slice is independently shippable and testable.

---

## 8. Settled decisions

1. **Tenders get their own tables** — a dedicated `tenders` table (+ `requirements`, `evidence_links`,
   `tasks`), **not** a `case_type="tender"` flavour of `cases`. The tender data model is genuinely
   different (buyers, references, bid decisions, readiness scores, requirements); a type-flag on
   `cases` would bloat that table with tender-only columns and make every investigation query step
   around them. Cost: tenders re-implement their own CRUD + `load_tender_or_403` — accepted.
2. **Tender documents reuse the shared `documents` tables** — `documents.case_id` goes nullable and a
   nullable `documents.tender_id` FK is added, so a document belongs to a case *or* a tender. This
   reuses the entire extraction/chunk/embed pipeline unchanged and leaves investigation rows untouched.
   (Chosen over fully separate `tender_documents` tables, which would duplicate the document machinery.)
3. **Vault gets its own vector table** — a separate `supplier_document_chunks` table (not a
   discriminator column on `document_chunks`), keeping the vault's `org_id`-scoped embeddings cleanly
   isolated from investigation's per-case RAG.
4. **ID scheme** — tenders use **`TEN-YYYY-XXXX`** (mirrors investigation's `INV-YYYY-XXXX`).

---

## 9. Risks / must-not-skip (same warnings as the proposal)

- **Evidence matching needs an eval harness from day one.** It's a decision users act on with money
  (which company doc proves which requirement). Build a small golden set + measure match precision
  before trusting it. This is the highest-risk piece.
- **Human-in-the-loop is mandatory** (roadmap Rule 3). AI *suggests* requirements, *suggests* evidence
  matches, *flags* readiness gaps. Humans confirm every one. Mirror the `human_review_status` pattern
  from findings on requirements and evidence_links.
- **Every AI record cites its source** (Rule 2) — requirement → source doc/page/clause; evidence match
  → which vault doc + why. The schema fields for this are in §5; don't drop them.
- **Tenant isolation extends to the vault** (Rule 4) — org A must never match against org B's vault.
  Every vault query and vector search is `org_id`-scoped.
- **New file types** — tenders arrive as Word/Excel/ZIP. Core's pipeline assumes ADE takes the file
  directly; Excel BOQs and ZIP bundles need pre-processing (unzip → classify each; XLSX → structured
  parse). Scope this into slice 1 or explicitly defer it.

---

## 10. First concrete step (when we start slice 1)

1. Branch `feature/tendering-foundation` off `main` (after the refactor PR merges).
2. Write the tender-tables migration (new file): `tenders`, `requirements`, `supplier_documents`,
   `supplier_document_chunks`, `evidence_links`, `tasks` — plus the additive `documents.case_id`
   nullable + `documents.tender_id` change (the only shared-table edit).
3. `apps/tendering/schemas.py` + `classify.py` + `db.py` facade.
4. `apps/tendering/routes.py`: `tenders` CRUD + `load_tender_or_403` + the tender document routes
   (thin mirrors of core's case-document routes, reusing `core.db_core` + `extract`).
5. Mount the tender router in `core/main.py` (one `include_router` line — no other core Python change).
6. Confirm investigation's 39 tests still pass + the new tender path boots.
