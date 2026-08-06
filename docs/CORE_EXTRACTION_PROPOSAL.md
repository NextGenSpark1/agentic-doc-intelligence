# Shared Core Extraction — Architecture Proposal

> **Purpose:** How we make the Investigation Intelligence backend reusable for Tendering Intelligence (and future products)


---

## 1. The core idea

we Dont copy the repo into a new folder for tenders (a "fork"). A fork means two copies of the same document pipeline that slowly drift apart — every bug fix has to be done twice

Instead, reorganise the **one existing backend** into two parts:

- **`core/`** — the shared engine every product reuses (upload, OCR, chunking, embeddings, vector search, chat, auth, orgs, audit).
- **`apps/`** — the product-specific logic (Investigation today; Tendering next), built *on top of* core.

```
backend/
├── core/                  ← shared by every product (write once)
├── apps/
│   ├── investigation/     ← existing product
│   └── tendering/         ← the new product
```

**"Drops in" = reuse almost unchanged.** Most of the backend drops into `core/` as-is. The new product mostly adds its own schemas, prompts, and a few new pipeline stages — it borrows everything else.

---

## 2. Where each existing file goes


| File | Lines | Bucket | Reason |
|---|---:|:---:|---|
| `ade_client.py` | 323 | 🟦 CORE | Document parsing / OCR — generic |
| `llm.py` | 33 | 🟦 CORE | LLM router — generic |
| `pipeline/llm_reasoning.py` | 53 | 🟦 CORE | Grounding / anti-hallucination guardrail — generic |
| `auth.py` | 79 | 🟦 CORE | Login / JWT verification — generic |
| `orgs.py` | 250 | 🟦 CORE | Orgs, roles, invites, tenant isolation — generic |
| `email.py` | 93 | 🟦 CORE | Invitation emails — generic |
| `config.py` | 86 | 🟦 CORE | Settings — generic |
| `pipeline/extract.py` | 138 | 🟦 CORE | Chunk + embed — generic |
| `pipeline/classify.py` | 54 | 🟨 SPLIT | Classify *engine* → core; fraud doc-type *labels* → app |
| `db.py` | 437 | 🟨 SPLIT | Cases/documents/chunks queries → core; findings/relationships/entities → app |
| `main.py` | 755 | 🟨 SPLIT | Upload/chat/auth routes → core; findings/entities/timeline routes → app |
| `schemas/investigation.py` | 101 | 🟩 INVESTIGATION | Fraud extraction schemas — stays |
| `pipeline/detect_anomalies.py` | 416 | 🟩 INVESTIGATION | Fraud detection rules — stays |
| `pipeline/build_relationships.py` | 282 | 🟩 INVESTIGATION | Entity relationship graph — stays |
| `pipeline/resolve_entities.py` | 168 | 🟩 INVESTIGATION | Entity resolution — stays |
| `pipeline/reconstruct_timeline.py` | 274 | 🟩 INVESTIGATION | Timeline reconstruction — stays |
| `pipeline/summarise.py` | 65 | 🟩 INVESTIGATION | Case risk summary — stays |


## 3. Target folder structure

```
backend/
├── core/                        ← shared by BOTH products
│   ├── ade_client.py
│   ├── llm.py
│   ├── llm_reasoning.py
│   ├── auth.py
│   ├── orgs.py
│   ├── email.py
│   ├── config.py
│   ├── db_core.py               ← generic queries (cases, documents, chunks)
│   ├── extract.py               ← chunk + embed
│   └── classify.py              ← classify engine (labels passed in as an argument)
│
├── apps/
│   ├── investigation/           ← existing product
│   │   ├── main.py              ← findings / entities / timeline routes (router)
│   │   ├── schemas.py           ← fraud extraction schemas
│   │   ├── db.py                ← findings / relationships / entities queries
│   │   └── pipeline/
│   │       ├── detect_anomalies.py
│   │       ├── build_relationships.py
│   │       ├── resolve_entities.py
│   │       ├── reconstruct_timeline.py
│   │       └── summarise.py
│   │
│   └── tendering/               ← NEW productt
│       ├── main.py              ← requirement / compliance / readiness routes (router)
│       ├── schemas.py           ← tender extraction schemas
│       ├── db.py                ← requirements / evidence / task queries
│       └── pipeline/
│           ├── extract_requirements.py   ← NEW
│           ├── compliance_matrix.py      ← NEW
│           ├── evidence_matching.py      ← NEW 
│           └── readiness_review.py       ← NEW
```

---

## 4. How the 3 SPLIT files are divided

**Golden rule:** the *engine* (the HOW) goes to `core/`; the *content* (the WHAT — labels, rules, schemas) stays in the app and is passed in.

### 4.1 `classify.py` — pass the type list as an argument

- **Engine → core:** `classify()` + `heuristic()` (take text → ask LLM → keyword fallback). Domain-agnostic.
- **Content → app:** the `KNOWN_TYPES` list and `_HEURISTICS` keyword map.
- **Change:** `classify(markdown, known_types, heuristics)` — each app hands it its own list.
  - Investigation passes: `invoice, bank_statement, payment_voucher, …`
  - Tendering passes: `tender_notice, instructions_to_tenderers, BOQ, pricing_schedule, …`

### 4.2 `db.py` — split by table

| Function group | Goes to |
|---|---|
| `get_client`, `_content_hash`, `_is_unique_violation` (shared helpers) | 🟦 `core/db_core.py` |
| `insert_case` / `get_case` / `list_cases` | 🟦 `core/db_core.py` |
| `insert_document` / `list_documents` / chunks / `match_chunks` / embeddings / `count_*` | 🟦 `core/db_core.py` |
| `insert_finding` / `insert_relationship` / `insert_timeline_events` / entities | 🟩 `apps/investigation/db.py` |

The app-level `db.py` **imports `get_client` from core** — it does not open its own connection.

### 4.3 `main.py` — split by route, using FastAPI routers

We already do this with `orgs.py` (`app.include_router(orgs_module.router)`)

| Endpoints | Goes to |
|---|---|
| `/health`, auth, `/cases` CRUD, `/documents` upload, `/chat`, `_load_case_or_403` | 🟦 `core/main.py` |
| `/findings`, `/entities`, `/timeline`, `/report`, `/analysis` | 🟩 `apps/investigation` router |
| (later) `/requirements`, `/compliance`, `/readiness`, `/vault` | 🟨 `apps/tendering` router |

Core owns the FastAPI `app` and wires each product in:
```python
app.include_router(investigation.router)
app.include_router(tendering.router)
```

**Important:** none of this changes behaviour. Investigation runs exactly the same afterwards — code is moved, and content is passed as arguments

---


