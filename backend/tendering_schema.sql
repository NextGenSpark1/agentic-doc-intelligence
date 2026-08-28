-- Tendering Platform Schema
-- Run this in the Supabase SQL editor after schema.sql has been applied.

-- 1. Tender workspaces (one per RFP/tender a team is tracking)
CREATE TABLE IF NOT EXISTS tender_workspaces (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          TEXT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    reference       TEXT DEFAULT '',
    buyer           TEXT DEFAULT '',
    category        TEXT DEFAULT '',
    closing_date    DATE,
    contract_value  NUMERIC(15, 2) DEFAULT 0,
    currency        TEXT DEFAULT 'USD',
    stage           TEXT DEFAULT 'new'     CHECK (stage IN ('new','analysing','preparing','submitted','awarded','lost','no_bid')),
    bid_decision    TEXT DEFAULT 'pending' CHECK (bid_decision IN ('pending','bid','no_bid')),
    readiness_score INTEGER DEFAULT 0      CHECK (readiness_score >= 0 AND readiness_score <= 100),
    description     TEXT DEFAULT '',
    team_members    TEXT[] DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Documents attached to a workspace (the RFP + supporting docs)
CREATE TABLE IF NOT EXISTS workspace_documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES tender_workspaces(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    category     TEXT DEFAULT 'supporting' CHECK (category IN ('rfp','supporting')),
    file_type    TEXT DEFAULT '',
    size_bytes   BIGINT DEFAULT 0,
    url          TEXT DEFAULT '',
    uploaded_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Requirements extracted from workspace documents
CREATE TABLE IF NOT EXISTS workspace_requirements (
    req_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES tender_workspaces(id) ON DELETE CASCADE,
    description     TEXT NOT NULL,
    category        TEXT DEFAULT 'other'     CHECK (category IN ('technical','financial','legal','experience','personnel','certification','other')),
    status          TEXT DEFAULT 'unchecked' CHECK (status IN ('met','gap','partial','unchecked')),
    owner           TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    source_doc      TEXT DEFAULT '',
    source_page     INTEGER,
    clause          TEXT DEFAULT '',
    mandatory       BOOLEAN DEFAULT TRUE,
    confidence      INTEGER DEFAULT 100 CHECK (confidence >= 0 AND confidence <= 100),
    matched_doc_ids TEXT[] DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Bid decision reports (one per workspace, latest wins)
CREATE TABLE IF NOT EXISTS workspace_bid_decisions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   UUID NOT NULL REFERENCES tender_workspaces(id) ON DELETE CASCADE,
    recommendation TEXT DEFAULT 'pending' CHECK (recommendation IN ('bid','no_bid','pending')),
    score          INTEGER DEFAULT 0 CHECK (score >= 0 AND score <= 100),
    rationale      TEXT DEFAULT '',
    strengths      TEXT[] DEFAULT '{}',
    risks          TEXT[] DEFAULT '{}',
    generated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Organisation document library (certificates, financials, CVs, etc.)
CREATE TABLE IF NOT EXISTS library_documents (
    doc_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              TEXT NOT NULL REFERENCES organisations(org_id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    filename            TEXT DEFAULT '',
    category            TEXT DEFAULT 'other' CHECK (category IN ('registration','certification','financial','technical','personnel','other')),
    file_type           TEXT DEFAULT '',
    issue_date          DATE,
    expiry_date         DATE,
    verification_status TEXT DEFAULT 'pending' CHECK (verification_status IN ('verified','pending','expired','missing')),
    tags                TEXT[] DEFAULT '{}',
    used_in_tenders     INTEGER DEFAULT 0,
    uploaded_at         TIMESTAMPTZ DEFAULT NOW()
);
