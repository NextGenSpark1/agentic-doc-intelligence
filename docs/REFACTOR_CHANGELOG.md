# Core Extraction — Refactor Changelog

> What actually changed when we split the backend into `core/` + `apps/investigation/`.
> **Branch:** `refactor/core-extraction` · **Behaviour change:** none · **Tests:** 39/39 pass · **Endpoints:** all 27 preserved.

---

## TL;DR (read this first)

- **No code was deleted.** Every line was **moved** or **split into two places**. The backend does exactly what it did before.
- **`backend/main.py` is now 9 lines on purpose.** It used to be 755. The code moved into `core/main.py` + `apps/investigation/routes.py`. `main.py` is now a one-line shim so `uvicorn backend.main:app` (the deploy command) keeps working. **This is correct, not a bug.**
- **Same API.** All 27 endpoints keep identical URLs — the frontend needs zero changes.

---

## Where every file went

### Moved into `backend/core/` (shared, unchanged logic)
| Was | Now | Change |
|---|---|---|
| `backend/ade_client.py` | `backend/core/ade_client.py` | moved as-is |
| `backend/llm.py` | `backend/core/llm.py` | moved as-is |
| `backend/auth.py` | `backend/core/auth.py` | moved as-is |
| `backend/email.py` | `backend/core/email.py` | moved as-is |
| `backend/config.py` | `backend/core/config.py` | moved as-is |
| `backend/orgs.py` | `backend/core/orgs.py` | moved; `db` import → `db_core` |
| `backend/pipeline/llm_reasoning.py` | `backend/core/llm_reasoning.py` | moved as-is |
| `backend/pipeline/extract.py` | `backend/core/extract.py` | moved; **schema selection now injected** (see below) |

### Moved into `backend/apps/investigation/` (fraud-specific, unchanged logic)
| Was | Now |
|---|---|
| `backend/schemas/investigation.py` | `backend/apps/investigation/schemas.py` |
| `backend/pipeline/detect_anomalies.py` | `backend/apps/investigation/pipeline/detect_anomalies.py` |
| `backend/pipeline/build_relationships.py` | `backend/apps/investigation/pipeline/build_relationships.py` |
| `backend/pipeline/resolve_entities.py` | `backend/apps/investigation/pipeline/resolve_entities.py` |
| `backend/pipeline/reconstruct_timeline.py` | `backend/apps/investigation/pipeline/reconstruct_timeline.py` |
| `backend/pipeline/summarise.py` | `backend/apps/investigation/pipeline/summarise.py` |
| `backend/pipeline/__init__.py` (orchestrator) | `backend/apps/investigation/pipeline/__init__.py` |

---

## The 3 files that were SPLIT (this is where the "new files" came from)

### 1. `db.py` (437 lines) → split by table
- **`backend/core/db_core.py`** — generic queries: cases, documents, chunks/RAG, extractions, orgs, storage, audit + shared helpers (`get_client`, `_content_hash`, `_is_unique_violation`).
- **`backend/apps/investigation/db.py`** *(new)* — investigation tables: findings, entities, relationships, timeline. **Re-exports everything from `db_core`** so investigation code still uses one unified `db` object (a "facade").

### 2. `classify.py` (54 lines) → engine + labels
- **`backend/core/classify.py`** — the classify *engine* (`classify(md, known_types, heuristics)`). Doesn't know about fraud or tenders.
- **`backend/apps/investigation/classify.py`** *(new)* — the fraud document-type **labels**, passed into the engine.

### 3. `main.py` (755 lines) → app + shared routes + investigation router
- **`backend/core/main.py`** *(new)* — creates the FastAPI `app`, CORS, shared helpers, and the **shared routes**: health, cases CRUD, documents, graph-state. Mounts the product routers at the bottom.
- **`backend/apps/investigation/routes.py`** *(new)* — the **investigation routes**: analysis, entities, timeline (+CRUD), findings, report, review, chat.
- **`backend/main.py`** — reduced to a 9-line shim: `from backend.core.main import app`.

---

## Genuinely new files created (and why)

| New file | Why it exists |
|---|---|
| `backend/core/main.py` | The real app now lives here (was `main.py`). |
| `backend/core/db_core.py` | The generic half of the old `db.py`. |
| `backend/core/classify.py` | The generic classify engine. |
| `backend/core/access.py` | `load_case_or_403` / `assert_case_access` — the case-access guard, pulled into its own module so both core and product routers can import it **without a circular import**. |
| `backend/core/text_utils.py` | `strip_html` / `keyword_or_filter` — tiny helpers shared by core and the chat route (also to avoid a circular import). |
| `backend/apps/investigation/db.py` | Investigation-table queries + a facade over `db_core`. |
| `backend/apps/investigation/classify.py` | Investigation document-type labels. |
| `backend/apps/investigation/routes.py` | Investigation API routes. |
| `backend/apps/investigation/pipeline/__init__.py` | The analysis orchestrator (moved + injects the investigation schema resolver). |
| `backend/apps/__init__.py`, `backend/apps/investigation/__init__.py`, `backend/core/__init__.py` | Empty package markers so Python treats the folders as importable packages. |

---

## Two design "seams" added for Tendering

These are the only real *logic* changes — they let a second product plug in later without touching core:

1. **Schema injection** — `core/extract.py`'s `run_extraction(document, case, schema_resolver)` now takes the schema-picker as an argument. Investigation passes its fraud schemas; Tendering will pass its tender schemas. Core never imports an app.
2. **Classify labels injection** — `core/classify.py`'s `classify(md, known_types, heuristics)` takes the document-type list as arguments, for the same reason.

---

## Two pragmatic calls (documented, revisit when Tendering lands)

1. **`count_pending_findings` stays in `core/db_core.py`** even though `findings` is an investigation table — it's just a `COUNT` query used by the shared `/cases` stats. Moving it would complicate the shared endpoint for no real gain right now.
2. **`/chat` lives in the investigation router**, not core — because its answer is enriched with investigation "case intelligence" (entities/findings/relationships). When Tendering needs chat, this becomes an injected hook. For now it keeps the exact same behaviour and URL.

---

## How it was verified (not just "trust me")

- **39/39 unit tests pass** (same as before the refactor — no test lost or weakened).
- **App boots cleanly** — no circular imports (`from backend.main import app` succeeds).
- **All 27 endpoints confirmed live via the OpenAPI schema** with identical paths — checked explicitly because unit tests don't cover route wiring.
- Files moved with `git mv` → **git history is preserved** (GitHub shows them as renames, not delete+add).

---

## What to do with this branch

1. Open the PR: `refactor/core-extraction` → `main`.
2. Review (especially: frontend still hits the same paths — it does).
3. **Merge the PR on GitHub** — that's what lands it on `main`. Don't hand-commit to main.
