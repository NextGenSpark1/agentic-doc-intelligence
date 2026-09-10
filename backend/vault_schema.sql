-- Vault Pipeline Schema — run AFTER tendering_pipeline_schema.sql
-- Safe to re-run (all statements are idempotent).

-- 1. Supplier vault tables (org-level document index, separate from the per-case chunks table).
CREATE TABLE IF NOT EXISTS supplier_documents (
    supplier_document_id TEXT        PRIMARY KEY,
    org_id               TEXT        NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    title                TEXT        DEFAULT '',
    doc_type             TEXT        DEFAULT 'other'
        CHECK (doc_type IN ('registration','certification','financial','technical','personnel','other')),
    storage_path         TEXT        DEFAULT '',
    filename             TEXT        DEFAULT '',
    issued_date          DATE,
    expiry_date          DATE,
    version              INTEGER     DEFAULT 1,
    extraction_status    TEXT        DEFAULT 'uploaded'
        CHECK (extraction_status IN ('uploaded','queued','processing','done','failed')),
    page_count           INTEGER     DEFAULT 0,
    superseded_by        TEXT,
    library_doc_id       TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS supplier_document_chunks (
    chunk_id             TEXT        PRIMARY KEY,
    org_id               TEXT        NOT NULL,
    supplier_document_id TEXT        NOT NULL REFERENCES supplier_documents(supplier_document_id) ON DELETE CASCADE,
    text                 TEXT        DEFAULT '',
    page                 INTEGER,
    bbox                 JSONB       DEFAULT '[]',
    embedding            vector(1536),
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Link supplier_documents back to the library_documents row they were created from
--    (no-op if the column already exists — tables created above already include it).
ALTER TABLE supplier_documents
    ADD COLUMN IF NOT EXISTS library_doc_id TEXT;

CREATE INDEX IF NOT EXISTS supplier_documents_library_doc_id_idx
    ON supplier_documents(library_doc_id)
    WHERE library_doc_id IS NOT NULL;

-- 3. Supplier-chunk vector search RPC.
CREATE OR REPLACE FUNCTION match_supplier_chunks(
    p_org_id          TEXT,
    p_query_embedding vector(1536),
    p_match_count     INT DEFAULT 12
)
RETURNS TABLE (
    supplier_document_id TEXT,
    chunk_id             TEXT,
    text                 TEXT,
    page                 INT,
    title                TEXT,
    doc_type             TEXT,
    expiry_date          DATE,
    library_doc_id       TEXT,
    similarity           FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        sdc.supplier_document_id,
        sdc.chunk_id,
        sdc.text,
        sdc.page,
        sd.title,
        sd.doc_type,
        sd.expiry_date,
        sd.library_doc_id,
        1 - (sdc.embedding <=> p_query_embedding) AS similarity
    FROM supplier_document_chunks sdc
    INNER JOIN supplier_documents sd
        ON sd.supplier_document_id = sdc.supplier_document_id
    WHERE sdc.org_id = p_org_id
      AND sdc.embedding IS NOT NULL
      AND sd.superseded_by IS NULL
      AND (sd.expiry_date IS NULL OR sd.expiry_date > CURRENT_DATE)
    ORDER BY sdc.embedding <=> p_query_embedding
    LIMIT p_match_count;
$$;

-- 4. Index to accelerate the org-scoped supplier chunk search.
CREATE INDEX IF NOT EXISTS supplier_document_chunks_org_embedding_idx
    ON supplier_document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
    WHERE embedding IS NOT NULL;
