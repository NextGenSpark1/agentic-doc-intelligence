-- Vault Pipeline Schema — run AFTER tendering_pipeline_schema.sql
-- Safe to re-run (all statements are idempotent).

-- 1. Link supplier_documents back to the library_documents row they were created from.
ALTER TABLE supplier_documents
    ADD COLUMN IF NOT EXISTS library_doc_id TEXT;

CREATE INDEX IF NOT EXISTS supplier_documents_library_doc_id_idx
    ON supplier_documents(library_doc_id)
    WHERE library_doc_id IS NOT NULL;

-- 2. Supplier-chunk vector search RPC.
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

-- 3. Index to accelerate the org-scoped supplier chunk search.
CREATE INDEX IF NOT EXISTS supplier_document_chunks_org_embedding_idx
    ON supplier_document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
    WHERE embedding IS NOT NULL;
