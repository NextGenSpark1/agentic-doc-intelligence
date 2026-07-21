-- Supabase schema for the Investigation Intelligence platform.
-- Run in the Supabase SQL editor. Enables pgvector for RAG.

-- MIGRATIONS — run once in the Supabase SQL editor if upgrading an existing database:
ALTER TABLE extractions ADD COLUMN IF NOT EXISTS summary text;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS schema_fields jsonb DEFAULT '[]'::jsonb;
-- Per-user isolation: each case is owned by the Supabase user who created it.
-- Existing rows keep NULL and remain visible to all authenticated users (safe migration path).
ALTER TABLE cases ADD COLUMN IF NOT EXISTS owner_id text;
-- Finding traceability: stores the top matching chunk(s) per finding as {document_id, chunk_id, page, quoted_text}.
-- Populated automatically after analysis; empty on old findings until analysis is re-run.
ALTER TABLE findings ADD COLUMN IF NOT EXISTS supporting_chunks jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS type text DEFAULT 'text';

-- LLM case-reasoning pass on top of the rule-based stages: every findings/entities/
-- relationships/timeline_events row is now tagged by how it was produced, and the LLM-sourced
-- ones carry a short justification.
ALTER TABLE findings ADD COLUMN IF NOT EXISTS source text DEFAULT 'rule';
ALTER TABLE findings ADD COLUMN IF NOT EXISTS reasoning text;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS source text DEFAULT 'rule';
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS source text DEFAULT 'rule';
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS reasoning text;
ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS source text DEFAULT 'rule';
ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS reasoning text;

-- Upgrade embedding dimension 768 → 1536 (gemini-embedding-001 at 1536 dims).
-- WARNING: drops all existing chunk embeddings. Re-extract every document after running.
ALTER TABLE chunks DROP COLUMN IF EXISTS embedding;
ALTER TABLE chunks ADD COLUMN embedding vector(1536);
DROP FUNCTION IF EXISTS match_chunks(text, vector, int);
CREATE OR REPLACE FUNCTION match_chunks(
    p_case_id text,
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
    WHERE c.case_id = p_case_id AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT p_match_count;
$$;

create extension if not exists vector;

-- ----------------------------- cases -----------------------------
create table if not exists cases (
    case_id            text primary key,
    title              text not null,
    case_type          text not null,
    status             text not null default 'Intake',
    lead_investigator  text,
    allegation_summary text default '',
    ai_summary         text,
    risk_score         float default 0,
    last_analysed_at   timestamptz,
    created_at         timestamptz not null default now()
);

-- --------------------------- documents ---------------------------
create table if not exists documents (
    document_id       text primary key,
    case_id           text references cases(case_id) on delete cascade,
    filename          text,
    file_hash         text,
    storage_path      text,
    document_type     text default 'unclassified',
    extraction_status text default 'queued',   -- queued|processing|done|failed
    page_count        int default 0,
    uploaded_at       timestamptz not null default now()
);

-- -------------------------- extractions --------------------------
create table if not exists extractions (
    extraction_id         text primary key,
    document_id           text references documents(document_id) on delete cascade,
    schema_name           text,
    extracted_json        jsonb,
    visual_grounding_json jsonb,
    extracted_at          timestamptz not null default now()
);

-- ----------------------- chunks (RAG index) ----------------------
create table if not exists chunks (
    id          bigserial primary key,
    case_id     text references cases(case_id) on delete cascade,
    document_id text references documents(document_id) on delete cascade,
    chunk_id    text,
    text        text,
    page        int,
    bbox        jsonb,
    embedding   vector(768)             -- embedding dimension varies by provider: Gemini text-embedding-004=768, OpenAI text-embedding-3-small=1536
);
create index if not exists chunks_case_idx on chunks(case_id);
create index if not exists chunks_embedding_idx on chunks
    using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ---------------------------- entities ---------------------------
create table if not exists entities (
    entity_id           text primary key,
    case_id             text references cases(case_id) on delete cascade,
    entity_type         text,
    canonical_name      text,
    aliases             jsonb default '[]'::jsonb,
    confidence_score    float default 0.9,
    source_document_ids jsonb default '[]'::jsonb,
    unique (case_id, entity_type, canonical_name)
);

-- ------------------------- relationships (edges) -----------------
create table if not exists relationships (
    relationship_id   text primary key,
    case_id           text references cases(case_id) on delete cascade,
    source_name       text,
    target_name       text,
    relationship_type text,
    evidence          jsonb default '{}'::jsonb
);

-- ----------------------------- findings --------------------------
create table if not exists findings (
    finding_id              text primary key,
    case_id                 text references cases(case_id) on delete cascade,
    finding_type            text,
    severity                text,            -- high|medium|low
    confidence              float,
    statement               text,
    supporting_document_ids jsonb default '[]'::jsonb,
    human_review_status     text default 'pending',  -- pending|confirmed|dismissed
    reviewed_by             text,
    reviewed_at             timestamptz,
    dismissal_reason        text,
    created_at              timestamptz not null default now()
);

-- -------------------------- timeline events ----------------------
create table if not exists timeline_events (
    event_id    text primary key,
    case_id     text references cases(case_id) on delete cascade,
    event_date  date,
    label       text,
    document_id text
);

-- ----------------------------- audit log -------------------------
create table if not exists audit_log (
    id        bigserial primary key,
    case_id   text,
    actor     text,
    action    text,
    detail    jsonb default '{}'::jsonb,
    at        timestamptz not null default now()
);

-- ----------- per-document vector search (for finding traceability) ----------
CREATE OR REPLACE FUNCTION match_chunks_in_document(
    p_document_id text,
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
    WHERE c.document_id = p_document_id AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT p_match_count;
$$;

-- ------------------- vector search RPC for chat ------------------
create or replace function match_chunks(
    p_case_id text,
    p_query_embedding vector(768),
    p_match_count int
)
returns table (
    document_id text,
    chunk_id text,
    text text,
    page int,
    bbox jsonb,
    similarity float
)
language sql stable as $$
    select c.document_id, c.chunk_id, c.text, c.page, c.bbox,
           1 - (c.embedding <=> p_query_embedding) as similarity
    from chunks c
    where c.case_id = p_case_id and c.embedding is not null
    order by c.embedding <=> p_query_embedding
    limit p_match_count;
$$;
