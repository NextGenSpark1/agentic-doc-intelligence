-- ============================================================================
-- Tendering Compliance — schema migration
-- ============================================================================
-- Ships SEPARATELY from backend/schema.sql. Run it in the Supabase SQL Editor
-- AFTER schema.sql. Idempotent — safe to re-run.
--
-- ---------------------------------------------------------------------------
-- REPLACES AN EARLIER VERSION OF THIS FILE.
-- ---------------------------------------------------------------------------
-- An earlier draft modelled a tender as a `cases` row with case_type='tender'
-- plus a `tender_meta` side-table. That approach was rejected: the tender model
-- is too different from an investigation case (buyers, references, bid
-- decisions, readiness scores, requirements). If you ran that draft, section 0
-- below drops its tables. There is no data migration — the draft was never used
-- against real tenders.
--
-- Settled model:
--   * Dedicated `tenders` table. NOT a flavour of `cases`.
--   * Tender documents reuse the shared `documents` + `chunks` tables via a
--     nullable `tender_id`, so the whole extract/chunk/embed pipeline is reused
--     and investigation rows are untouched.
--   * The supplier vault is ORG-level (shared across a company's tenders) and
--     gets its own vector table, separate from investigation's chunks.
--
-- Rules encoded structurally rather than by convention:
--   * Rule 2 (every AI record cites its source) — `requirements_ai_must_cite`
--     and `evidence_links_ai_must_explain` CHECK constraints.
--   * Rule 3 (AI never decides) — `bid_decision` and the review-status columns
--     are only written by human-invoked routes; pipeline stages insert
--     'pending' rows and nothing else.
--   * Rule 4 (tenant isolation) — `match_supplier_docs` filters on org_id
--     inside SQL, exactly as match_chunks filters on case_id, so isolation
--     cannot be lost by an application-layer mistake.
-- ============================================================================


-- ===================== 0. drop the rejected draft =====================
-- Safe no-ops if the draft was never run.
drop index if exists requirements_pending_dedup_idx;
drop table if exists tender_tasks cascade;
drop table if exists requirements cascade;
drop table if exists tender_meta cascade;


-- ===================== 1. shared tables gain a tender scope =====================
-- documents.case_id and chunks.case_id are already nullable, so adding a parallel
-- nullable tender_id is additive: every existing investigation row is untouched and
-- keeps its case_id.
alter table documents  add column if not exists tender_id text;
alter table chunks     add column if not exists tender_id text;
alter table audit_log  add column if not exists tender_id text;

create index if not exists documents_tender_idx on documents (tender_id);
create index if not exists chunks_tender_idx    on chunks (tender_id);
create index if not exists audit_log_tender_idx on audit_log (tender_id);


-- ===================== 2. tenders =====================
create table if not exists tenders (
    tender_id          text primary key,
    org_id             text,
    title              text not null,
    buyer              text,
    reference_no       text,
    closing_date       timestamptz,
    contract_value     numeric,
    currency           text,
    submission_method  text,
    -- identified -> assessing -> bidding -> submitted -> awarded/lost/withdrawn
    tender_stage       text not null default 'identified',
    status             text not null default 'Intake',
    ai_summary         text,
    -- Human-only fields (Rule 3). No pipeline stage may write these.
    bid_decision       text,
    bid_decision_by    text,
    bid_decision_at    timestamptz,
    -- Derived by the readiness stage (slice 4); advisory, never gating.
    readiness_score    float,
    owner_id           text,
    created_by         text,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz,
    last_analysed_at   timestamptz,

    constraint tenders_bid_decision_valid check (bid_decision is null or bid_decision in ('bid', 'no_bid'))
);

create index if not exists tenders_org_idx     on tenders (org_id);
create index if not exists tenders_creator_idx on tenders (created_by);
create index if not exists tenders_closing_idx on tenders (closing_date);

-- Now that `tenders` exists, point the shared tables' tender_id at it. Done as a
-- separate step so the ALTERs above stay runnable on a fresh database.
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'documents_tender_fk') then
        alter table documents add constraint documents_tender_fk
            foreign key (tender_id) references tenders(tender_id) on delete cascade;
    end if;
    if not exists (select 1 from pg_constraint where conname = 'chunks_tender_fk') then
        alter table chunks add constraint chunks_tender_fk
            foreign key (tender_id) references tenders(tender_id) on delete cascade;
    end if;
end $$;


-- ===================== 3. requirements =====================
-- One extracted obligation. Modelled on `findings`: same source/confidence columns,
-- same content_hash dedup, same human_review_status state machine.
create table if not exists requirements (
    requirement_id       text primary key,
    tender_id            text not null references tenders(tender_id) on delete cascade,
    org_id               text,

    description          text not null,
    -- legal | financial | technical | certification | submission_instruction |
    -- evaluation_criterion | other
    category             text not null default 'other',
    is_mandatory         boolean not null default false,
    required_evidence    text,

    -- Rule 2: provenance.
    source_document_id   text references documents(document_id) on delete set null,
    source_page          int,
    source_clause        text,
    source_text          text,
    confidence           float,
    source               text not null default 'llm',   -- rule | llm | manual

    -- Workflow (human-owned).
    owner_id             text,
    completion_status    text not null default 'not_started',
    human_review_status  text not null default 'pending',
    reviewed_by          text,
    reviewed_at          timestamptz,
    dismissal_reason     text,

    content_hash         text,
    created_at           timestamptz not null default now(),

    -- Rule 2 as an invariant: an AI-generated requirement that cannot point at a
    -- document and page is rejected by the database, not merely discouraged by a
    -- prompt. Manually-entered requirements are exempt — a human is the source.
    constraint requirements_ai_must_cite check (
        source = 'manual'
        or (source_document_id is not null and source_page is not null)
    ),
    constraint requirements_review_status_valid check (
        human_review_status in ('pending', 'confirmed', 'dismissed')
    ),
    constraint requirements_completion_valid check (
        completion_status in ('not_started', 'in_progress', 'complete')
    )
);

create index if not exists requirements_tender_idx   on requirements (tender_id);
create index if not exists requirements_org_idx      on requirements (org_id);
create index if not exists requirements_review_idx   on requirements (tender_id, human_review_status);
create index if not exists requirements_category_idx on requirements (tender_id, category);

-- Re-running extraction must not double-insert rows a human has not yet reviewed.
-- Confirmed/dismissed rows stay out of scope, so a re-run can resurface something
-- already ruled on. The md5 formula MUST stay in sync with
-- backend/core/db_core.py::_content_hash (parts joined by chr(0)).
create unique index if not exists requirements_pending_dedup_idx
    on requirements (tender_id, content_hash)
    where human_review_status = 'pending' and content_hash is not null;


-- ===================== 4. supplier vault (org-level) =====================
-- Reusable across every tender the org bids on — a company uploads its CIDB
-- certificate once, not once per tender.
create table if not exists supplier_documents (
    supplier_document_id text primary key,
    org_id               text not null,
    title                text not null,
    doc_type             text,           -- certificate | licence | financial | policy | cv | reference | other
    storage_path         text,
    filename             text,
    issued_date          date,
    expiry_date          date,           -- drives the "expired evidence" readiness gap
    version              int not null default 1,
    superseded_by        text references supplier_documents(supplier_document_id) on delete set null,
    extraction_status    text not null default 'uploaded',
    page_count           int default 0,
    uploaded_by          text,
    created_at           timestamptz not null default now()
);

create index if not exists supplier_documents_org_idx    on supplier_documents (org_id);
create index if not exists supplier_documents_type_idx   on supplier_documents (org_id, doc_type);
create index if not exists supplier_documents_expiry_idx on supplier_documents (org_id, expiry_date);

-- The vault's own vector table. Deliberately separate from `chunks` so a vault
-- document can never surface in an investigation case's RAG, and vice versa.
create table if not exists supplier_document_chunks (
    id                   bigserial primary key,
    org_id               text not null,
    supplier_document_id text references supplier_documents(supplier_document_id) on delete cascade,
    chunk_id             text,
    text                 text,
    page                 int,
    bbox                 jsonb,
    embedding            vector(1536)
);

create index if not exists supplier_chunks_org_idx on supplier_document_chunks (org_id);
create index if not exists supplier_chunks_doc_idx on supplier_document_chunks (supplier_document_id);
create index if not exists supplier_chunks_embedding_idx on supplier_document_chunks
    using hnsw (embedding vector_cosine_ops);


-- ===================== 5. evidence links =====================
-- The join between a requirement and the vault document that satisfies it.
-- AI proposes (pending); a human approves before it counts toward a submission.
create table if not exists evidence_links (
    evidence_link_id     text primary key,
    requirement_id       text not null references requirements(requirement_id) on delete cascade,
    supplier_document_id text not null references supplier_documents(supplier_document_id) on delete cascade,
    org_id               text,

    match_score          float,
    rationale            text,           -- why this document satisfies this requirement
    matched_chunk_id     text,           -- the vault excerpt the match was read from
    source               text not null default 'llm',   -- llm | manual

    human_review_status  text not null default 'pending',
    reviewed_by          text,
    reviewed_at          timestamptz,
    dismissal_reason     text,
    created_at           timestamptz not null default now(),

    -- Rule 2, applied to matching: an AI-proposed link must say WHY. A match a
    -- bidder cannot justify is worse than no match — they would submit on it.
    constraint evidence_links_ai_must_explain check (
        source = 'manual' or (rationale is not null and match_score is not null)
    ),
    constraint evidence_links_review_status_valid check (
        human_review_status in ('pending', 'confirmed', 'dismissed')
    ),
    -- One link per (requirement, document) pair — re-running matching updates
    -- rather than duplicating.
    constraint evidence_links_unique unique (requirement_id, supplier_document_id)
);

create index if not exists evidence_links_requirement_idx on evidence_links (requirement_id);
create index if not exists evidence_links_document_idx    on evidence_links (supplier_document_id);
create index if not exists evidence_links_review_idx      on evidence_links (org_id, human_review_status);


-- ===================== 6. tasks =====================
create table if not exists tasks (
    task_id         text primary key,
    tender_id       text not null references tenders(tender_id) on delete cascade,
    requirement_id  text references requirements(requirement_id) on delete cascade,
    org_id          text,
    title           text not null,
    assignee_id     text,
    due_date        timestamptz,
    status          text not null default 'open',
    created_by      text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz,

    constraint tasks_status_valid check (status in ('open', 'in_progress', 'done', 'blocked'))
);

create index if not exists tasks_tender_idx      on tasks (tender_id);
create index if not exists tasks_requirement_idx on tasks (requirement_id);
create index if not exists tasks_assignee_idx    on tasks (assignee_id, status);


-- ===================== 7. tender chunk retrieval =====================
-- Tender-scoped vector search, mirroring match_chunks. The tender_id filter lives
-- in SQL for the same reason case_id does: isolation must not depend on the
-- application remembering to add a WHERE clause.
DROP FUNCTION IF EXISTS match_tender_chunks(text, vector, int);
CREATE OR REPLACE FUNCTION match_tender_chunks(
    p_tender_id text,
    p_query_embedding vector(1536),
    p_match_count int
)
RETURNS TABLE (
    document_id text,
    chunk_id text,
    text text,
    page int,
    bbox jsonb,
    similarity float
)
LANGUAGE sql STABLE AS $$
    SELECT c.document_id, c.chunk_id, c.text, c.page, c.bbox,
           1 - (c.embedding <=> p_query_embedding) AS similarity
    FROM chunks c
    WHERE c.tender_id = p_tender_id AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT p_match_count;
$$;


-- ===================== 8. supplier vault retrieval =====================
-- Evidence matching's retrieval arm. Rule 4: the org_id filter is IN THE SQL, so
-- org A can never match against org B's vault even if application code forgets to
-- scope the query. Expired documents are excluded at the source — proposing an
-- expired certificate as evidence is worse than proposing nothing.
DROP FUNCTION IF EXISTS match_supplier_docs(text, vector, int, boolean);
CREATE OR REPLACE FUNCTION match_supplier_docs(
    p_org_id text,
    p_query_embedding vector(1536),
    p_match_count int,
    p_include_expired boolean DEFAULT false
)
RETURNS TABLE (
    supplier_document_id text,
    chunk_id text,
    text text,
    page int,
    title text,
    doc_type text,
    expiry_date date,
    similarity float
)
LANGUAGE sql STABLE AS $$
    SELECT sd.supplier_document_id, sdc.chunk_id, sdc.text, sdc.page,
           sd.title, sd.doc_type, sd.expiry_date,
           1 - (sdc.embedding <=> p_query_embedding) AS similarity
    FROM supplier_document_chunks sdc
    JOIN supplier_documents sd ON sd.supplier_document_id = sdc.supplier_document_id
    WHERE sdc.org_id = p_org_id
      AND sd.org_id = p_org_id            -- belt and braces: both sides scoped
      AND sdc.embedding IS NOT NULL
      AND sd.superseded_by IS NULL        -- never propose a superseded version
      AND (p_include_expired OR sd.expiry_date IS NULL OR sd.expiry_date >= current_date)
    ORDER BY sdc.embedding <=> p_query_embedding
    LIMIT p_match_count;
$$;
