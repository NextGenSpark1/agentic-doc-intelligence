-- Tendering Pipeline Schema — run AFTER tendering_schema.sql
-- Safe to re-run (all statements are idempotent).

-- 1. Link core documents/chunks back to a workspace so the extraction pipeline
--    can process workspace RFPs using the same infrastructure as ADI cases.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES tender_workspaces(id) ON DELETE SET NULL;
ALTER TABLE chunks    ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES tender_workspaces(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS documents_workspace_id_idx ON documents(workspace_id) WHERE workspace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS chunks_workspace_id_idx    ON chunks(workspace_id)    WHERE workspace_id IS NOT NULL;

-- 2. workspace_documents gets a pointer to its core document row (set when extraction is triggered).
ALTER TABLE workspace_documents ADD COLUMN IF NOT EXISTS document_id UUID REFERENCES documents(document_id) ON DELETE SET NULL;

-- 3. New columns on tender_workspaces.
ALTER TABLE tender_workspaces ADD COLUMN IF NOT EXISTS ai_summary TEXT DEFAULT '';

-- 4. New columns on workspace_requirements (needed by the pipeline stages).
ALTER TABLE workspace_requirements ADD COLUMN IF NOT EXISTS source_text         TEXT    DEFAULT '';
ALTER TABLE workspace_requirements ADD COLUMN IF NOT EXISTS completion_status   TEXT    DEFAULT 'not_started'
    CHECK (completion_status IN ('not_started', 'in_progress', 'complete'));
ALTER TABLE workspace_requirements ADD COLUMN IF NOT EXISTS required_evidence   TEXT    DEFAULT '';

-- 5. Evidence links — requirement ↔ library document with human-review gate.
CREATE TABLE IF NOT EXISTS evidence_links (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID        NOT NULL REFERENCES tender_workspaces(id)        ON DELETE CASCADE,
    req_id              UUID        NOT NULL REFERENCES workspace_requirements(req_id) ON DELETE CASCADE,
    doc_id              UUID        NOT NULL REFERENCES library_documents(doc_id)    ON DELETE CASCADE,
    score               NUMERIC(4,3) DEFAULT 0 CHECK (score >= 0 AND score <= 1),
    rationale           TEXT        DEFAULT '',
    matched_chunk_id    TEXT        DEFAULT '',
    org_id              TEXT        NOT NULL REFERENCES organisations(org_id)         ON DELETE CASCADE,
    human_review_status TEXT        DEFAULT 'pending'
        CHECK (human_review_status IN ('pending', 'confirmed', 'dismissed')),
    source              TEXT        DEFAULT 'llm' CHECK (source IN ('llm', 'manual')),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (req_id, doc_id)
);

-- 6. Workspace-scoped vector search RPC.
CREATE OR REPLACE FUNCTION match_workspace_chunks(
    p_workspace_id  UUID,
    p_query_embedding vector(1536),
    p_match_count   INT
)
RETURNS TABLE (
    chunk_id    TEXT,
    text        TEXT,
    page        INT,
    document_id TEXT,
    similarity  FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        chunk_id,
        text,
        page,
        document_id::TEXT,
        1 - (embedding <=> p_query_embedding) AS similarity
    FROM chunks
    WHERE workspace_id = p_workspace_id
      AND embedding IS NOT NULL
    ORDER BY embedding <=> p_query_embedding
    LIMIT p_match_count;
$$;

-- 7. tenant_id column on audit_log so pipeline audit entries can be traced to a workspace.
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES tender_workspaces(id) ON DELETE SET NULL;
