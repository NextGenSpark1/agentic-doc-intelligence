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
      -- Both sides are scoped, not just the chunk. org_id is copied onto each chunk at index
      -- time, so a chunk whose org ever disagreed with its parent document's would otherwise
      -- leak another company's evidence into this org's matches. This is the vault's tenant
      -- isolation boundary, so it is enforced twice.
      AND sd.org_id = p_org_id
      AND sdc.embedding IS NOT NULL
      -- No application code sets superseded_by yet, so today this excludes nothing. It is
      -- kept so a future "replace document" feature only has to set the column. Until then,
      -- a renewed certificate retires the old one only via the expiry filter below.
      AND sd.superseded_by IS NULL
      -- Expired documents are NOT filtered here. They are retrieved and passed to the
      -- adjudicator with `is_expired` / `expires_before_closing` flags, so a matched-but-
      -- lapsed certificate becomes a partial with an explanatory note rather than an
      -- invisible gap. The Python cap in evidence_matching keeps expired evidence below
      -- the MET threshold so it cannot silently satisfy a requirement.
    ORDER BY sdc.embedding <=> p_query_embedding
    LIMIT p_match_count;
$$;

-- 4. ANN index for the supplier chunk search — HNSW, matching the decision schema.sql made
--    for `chunks`. This previously used ivfflat (lists = 100), which had two problems for a
--    vault: ivfflat lists are trained when the index is built, so creating it on an empty table
--    left it untrained; and lists = 100 is sized for ~100k+ rows, so on a vault of a few hundred
--    chunks most probes returned little. HNSW needs no training and no retuning as the vault
--    grows. The DROP is required: CREATE INDEX IF NOT EXISTS will not replace an existing index
--    that has the same name.
DROP INDEX IF EXISTS supplier_document_chunks_org_embedding_idx;
CREATE INDEX IF NOT EXISTS supplier_document_chunks_embedding_idx
    ON supplier_document_chunks
    USING hnsw (embedding vector_cosine_ops);

-- 5. Keyword-based match. Vector similarity is bad at short exact strings — company registration
--    numbers, "SSM", "PMP", "CIDB G7", "REST API", "ISO/IEC 27001". A capability statement that
--    literally contains the SSM number can score well below the 0.35 vector cutoff because the
--    embedding for a specific 12-digit id sits nowhere near the embedding for "SSM
--    registration". This function catches those cases by ILIKE-matching chunk text and document
--    titles against a list of keywords lifted from the requirement, so the adjudicator sees the
--    document even when the semantic search missed it.
--
--    The `similarity` field is the fraction of keywords the chunk (or its parent document title)
--    covers. It is deliberately not a cosine score: a chunk with 3 of 3 keywords is far more
--    interesting than one with 3 of 10, and the caller merges these results with vector hits by
--    ranking rather than by direct comparison.
CREATE OR REPLACE FUNCTION match_supplier_chunks_by_keyword(
    p_org_id      TEXT,
    p_keywords    TEXT[],
    p_match_count INT DEFAULT 6
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
    WITH keyword_matches AS (
        SELECT
            sdc.supplier_document_id,
            sdc.chunk_id,
            sdc.text,
            sdc.page,
            sd.title,
            sd.doc_type,
            sd.expiry_date,
            sd.library_doc_id,
            (
                SELECT COUNT(*)::FLOAT
                FROM unnest(p_keywords) AS kw
                WHERE kw <> ''
                  AND (sdc.text ILIKE '%' || kw || '%'
                       OR sd.title ILIKE '%' || kw || '%')
            ) AS matched_terms,
            GREATEST(COALESCE(array_length(p_keywords, 1), 0), 1) AS total_terms
        FROM supplier_document_chunks sdc
        INNER JOIN supplier_documents sd
            ON sd.supplier_document_id = sdc.supplier_document_id
        WHERE sdc.org_id = p_org_id
          AND sd.org_id = p_org_id
          AND sd.superseded_by IS NULL
    )
    SELECT
        supplier_document_id,
        chunk_id,
        text,
        page,
        title,
        doc_type,
        expiry_date,
        library_doc_id,
        matched_terms / total_terms AS similarity
    FROM keyword_matches
    WHERE matched_terms > 0
    ORDER BY matched_terms DESC, length(text) ASC
    LIMIT p_match_count;
$$;
