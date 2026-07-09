# Investigation Intelligence — Claude Code Context

**Project:** Agentic Document Intelligence Platform  
**Description:** AI-powered platform for forensic investigation teams to ingest, extract, and reason over large document corpora using LLM-driven pipelines.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + custom HTML/CSS/JS (no component framework) |
| Database / Storage | Supabase (Postgres + Storage) |
| Backend API | FastAPI (Python) |
| Document Extraction | LandingAI ADE (Agentic Document Extraction) |
| AI / LLM | LiteLLM router (`backend/llm.py`): Groq llama-3.3-70b for reasoning/summaries/case-wide reasoning, Groq llama-3.1-8b for fast classification, Gemini for embeddings (see below) |

---

## Folder Structure

```
agentic-doc-intelligence/
├── shared/          # Pydantic schemas shared between dashboard and backend
├── backend/         # FastAPI app + document processing pipeline stages
│   └── pipeline/    # Individual pipeline stage modules (classify, extract, etc.)
├── dashboard/       # Streamlit multi-page app
│   ├── pages/       # Streamlit pages (1_Cases, 2_Case_Workspace, 3_Case_Settings)
│   ├── components/  # Reusable Streamlit component wrappers
│   └── utils/       # Theme tokens (theme.py) and global CSS/navbar (styles.py)
└── .env.example     # Environment variable template
```

---

## Build Phase

**Phase 0 — Foundations**

Scaffold, design system, and page shells are in place. No live data yet.

---

## Current Status

- Repo scaffolded with full folder structure and all placeholder files
- Styling foundation: IBM Plex Sans/Mono, CSS variable token system, Streamlit chrome hidden
- Navbar: two-bar fixed header (dark navy top bar + teal-navy tab row); navigation works same-tab via invisible `st.page_link()` overlays positioned with CSS `:has()` over the visual spans
- All three pages render with hardcoded HTML data — no live data
- Cases page: stat cards + 4-row cases table
- Case Workspace: three-panel layout (document list, document viewer placeholder, case assistant chat placeholder); sub-tabs (Entity Graph, Timeline, Findings, Report) are visual-only `<a href="#">` links
- Case Settings: two-column layout (left nav rail, right content cards for Case Details + Case Configuration)
- Supabase tables not yet created
- Backend FastAPI app is a skeleton with stub endpoints only — not connected to dashboard
- LandingAI ADE integration not started
- Claude RAG/chat integration not started

### Key implementation notes (hard-won)
- `[data-testid="stHeader"] { display: none !important; }` — hides Streamlit chrome cleanly; do NOT use `visibility:hidden` (causes full-page washout)
- Navigation: `st.page_link()` is the only reliable same-tab router in Streamlit; `components.html()` is sandboxed and cannot navigate the parent frame; `<a href>` in `st.markdown()` is intercepted by React and opens a new tab
- Never use blank lines inside HTML blocks in `st.markdown()` — CommonMark closes type-6 blocks at the first blank line, rendering the rest as raw source; `<style>` blocks (type-1) are safe
- All imports inside `dashboard/` must be relative to `dashboard/` (e.g. `from utils.styles import inject_styles`), not `from dashboard.utils…`
- Streamlit strips `<input>`, `<select>`, `<textarea>`, `<button>` from `unsafe_allow_html` HTML — use styled `<div>`/`<span>` replacements
- Clickable table rows: HTML `<table>` rows cannot contain Streamlit widgets. Solution: use CSS grid div for header + `st.columns()` per row. A hidden `<span class="case-row-marker ...">` in col[0] lets CSS `:has(.case-row-marker)` target the entire `stHorizontalBlock` for border/hover/stale/last-row styling
- `onclick` and JS event handlers in `unsafe_allow_html` are stripped by DOMPurify — cannot use for interactivity. Use real Streamlit widgets (buttons, page_link) instead
- Page-specific CSS belongs in `dashboard/utils/styles.py` as named functions (e.g. `get_cases_page_css()`), not inline in page files. CSS blocks must be plain strings (no f-string) to avoid `{{`/`}}` escaping; data blocks that need Python vars are separate f-string `st.markdown()` calls
- Split `st.markdown()` at `</style>` boundary when part of the block needs Python variables: CSS block = plain string, HTML content block = f-string
- Case-analysis pipeline (`backend/pipeline/`) is AI-first rule+LLM, not rule-only: `resolve_entities`/`build_relationships`/`reconstruct_timeline`/`detect_anomalies` each run a case-reasoning LLM pass (`tier="case_reasoning"` in `llm.py`, default `groq/llama-3.3-70b-versatile`) via the shared `backend/pipeline/llm_reasoning.py` helper as the PRIMARY output. The original deterministic passes (still the pure, unit-tested `compute_*` functions — untouched) run as a FALLBACK only when the LLM returns nothing (`findings`/`relationships`: `if not <llm_result>: use compute_*`). NOTE: this AI-first orchestration in `build()`/`detect()` was a teammate's change (commit 26fcfbad) layered on top of the original hybrid "rules + LLM combined" design — the tradeoff is the provable rule findings (duplicate invoice, shared bank account) are suppressed whenever the LLM returns anything. Every LLM-sourced row is tagged `source="llm"` vs `source="rule"` (new columns on `findings`/`entities`/`relationships`/`timeline_events` — migration at the top of `schema.sql`, must be run in Supabase SQL editor). Anti-hallucination guardrail: any LLM output citing a `document_id`/entity/event we didn't actually send is dropped before persisting, never trusted at face value — see `tests/test_llm_reasoning_guardrails.py`. LLM pass failures (bad key, provider error, bad JSON) are swallowed for the caller (`llm_reasoning.ask` returns `None`, stage falls back to rule results) but logged to the case's `audit_log` (`action="case_reasoning_failed"`) so a failing tier is diagnosable instead of invisible.
- `case_reasoning` was originally pointed at `gemini/gemini-2.5-pro` per the initial request to use Gemini specifically, but that model has **zero** free-tier request quota on Google AI Studio keys (confirmed via a live 429 with `limit: 0`, not just a low quota) — switched to `groq/llama-3.3-70b-versatile` instead (same model already proven reliable for the `reasoning` tier). Gemini is still used for embeddings (`llm_embedding_model`). If revisiting Gemini for case_reasoning, billing must be enabled on the underlying Google Cloud project first.

---

## Session Log

| Date | Phase | What was completed |
|---|---|---|
| 2026-05-25 | Phase 0 | Full repo scaffold: folder structure, shared schemas, backend skeleton, dashboard pages, theme + styles system, CLAUDE.md, README.md |
| 2026-05-25 | Phase 0 | Navigation fixed (st.page_link invisible overlays), visual design restored, all three pages rendering and navigable |
| 2026-06-23 | Phase 0→1 | Backend walkthrough (teammate's 29 files). Fixed: .gitignore encoding, docker-compose Dockerfile paths, missing backend/schemas/__init__.py. Connected Cases page to real GET /cases + POST /cases endpoints. Fixed real credentials in .env.example. |
| 2026-06-23 | Phase 0→1 | UX polish: moved inline CSS to styles.py (get_cases_page_css), styled New Case form widgets to match design system, replaced st.success/warning/error with custom HTML banners, made case rows clickable via st.columns + session_state → st.switch_page to Case Workspace |
| 2026-07-09 | Phase 1 | Upgraded findings/entity-resolution/relationships/timeline stages from pure rule-based to hybrid rule+LLM reasoning. Added `case_reasoning` LLM tier and shared `pipeline/llm_reasoning.py` guardrail helper; rule functions (`compute_findings`/`compute_relationships`/`compute_events`) untouched, LLM pass runs on top and is tagged `source="llm"` with document/entity-grounding validation. Added `source`/`reasoning` column migrations to schema.sql (needs running in Supabase) and `tests/test_llm_reasoning_guardrails.py`. |
| 2026-07-09 | Phase 1 | Fixed two silent-failure bugs found while testing: (1) chunk embedding (`extract.py`) sent all of a document's chunks to Gemini in one call — docs with >100 chunks failed entirely and got zero embeddings with no logging; now batches at 100, retries on rate limits, logs failures to `audit_log`, and backfilled the 2 live cases this had silently broken. (2) `case_reasoning` tier was pointed at `gemini-2.5-pro`, which has zero free-tier quota on this project (confirmed via live 429, not just low quota) — every LLM pass had been failing 100% of the time, invisibly, since it was added. Switched `case_reasoning` to `groq/llama-3.3-70b-versatile` and added audit-log logging (`action="case_reasoning_failed"`) so this class of bug is diagnosable next time instead of silent. |

---

## Notes for Next Session

- Case Workspace breadcrumb now shows `active_case_id` from session_state — confirmed navigation works
- Sub-tabs within Case Workspace (Entity Graph, Timeline, Findings, Report) are currently `<a href="#">` visual placeholders — implement with `st.tabs()` or conditional rendering inside `2_Case_Workspace.py` when building those views
- Next phase: create Supabase tables (schema.sql must be run in Supabase SQL editor), then connect Case Workspace to real case data via GET /cases/{case_id}
- Reusable UI building blocks (document cards, entity badges, risk meters) go in `dashboard/components/` as Python functions, not as separate Streamlit page files
- `dashboard/app.py` uses `st.switch_page` to redirect to Cases on load — confirmed working
- Run the new `source`/`reasoning` column migrations at the top of `backend/schema.sql` in the Supabase SQL editor before re-running case analysis, or the LLM-tagged rows will fail to insert
- If a case's chat assistant says "couldn't find anything relevant" for documents that clearly extracted fine, check `chunks.embedding IS NULL` for that case_id — this was silently broken for large documents before the batching fix; audit_log now has a `chunk_embedding_failed` entry when it happens
- Dashboard doesn't yet distinguish `source="llm"` vs `"rule"` findings/entities/relationships/timeline visually — worth a badge/filter in the workspace UI next
- Keep updating this file at the end of every session
