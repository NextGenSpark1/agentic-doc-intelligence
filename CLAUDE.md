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
| AI / LLM | Anthropic Claude (claude-sonnet-4-6 default) |

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

---

## Session Log

| Date | Phase | What was completed |
|---|---|---|
| 2026-05-25 | Phase 0 | Full repo scaffold: folder structure, shared schemas, backend skeleton, dashboard pages, theme + styles system, CLAUDE.md, README.md |
| 2026-05-25 | Phase 0 | Navigation fixed (st.page_link invisible overlays), visual design restored, all three pages rendering and navigable |
| 2026-06-23 | Phase 0→1 | Backend walkthrough (teammate's 29 files). Fixed: .gitignore encoding, docker-compose Dockerfile paths, missing backend/schemas/__init__.py. Connected Cases page to real GET /cases + POST /cases endpoints. Fixed real credentials in .env.example. |
| 2026-06-23 | Phase 0→1 | UX polish: moved inline CSS to styles.py (get_cases_page_css), styled New Case form widgets to match design system, replaced st.success/warning/error with custom HTML banners, made case rows clickable via st.columns + session_state → st.switch_page to Case Workspace |

---

## Notes for Next Session

- Case Workspace breadcrumb now shows `active_case_id` from session_state — confirmed navigation works
- Sub-tabs within Case Workspace (Entity Graph, Timeline, Findings, Report) are currently `<a href="#">` visual placeholders — implement with `st.tabs()` or conditional rendering inside `2_Case_Workspace.py` when building those views
- Next phase: create Supabase tables (schema.sql must be run in Supabase SQL editor), then connect Case Workspace to real case data via GET /cases/{case_id}
- Reusable UI building blocks (document cards, entity badges, risk meters) go in `dashboard/components/` as Python functions, not as separate Streamlit page files
- `dashboard/app.py` uses `st.switch_page` to redirect to Cases on load — confirmed working
- Keep updating this file at the end of every session
