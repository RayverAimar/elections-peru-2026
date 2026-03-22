-- 001_schema.sql
-- Complete database schema for Peru 2026 Elections Platform
--
-- Tables:
--   parties            Political parties (source of truth)
--   candidates         All candidates across all election types
--   government_plans   One plan de gobierno per party
--   plan_chunks        Chunked plan text with embeddings for RAG
--   news_articles      News articles from media sources
--   news_mentions      Links between articles and parties
--   news_chunks        Chunked article text with embeddings for RAG

CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════ Parties & Candidates ═══════════════════

CREATE TABLE IF NOT EXISTS parties (
    id SERIAL PRIMARY KEY,
    jne_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(200) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    election_type VARCHAR(30) NOT NULL,     -- presidential, senator, representative, andean_parliament
    constituency VARCHAR(100),              -- NULL for national elections (presidential, senate, andean)
    full_name VARCHAR(300) NOT NULL,
    position VARCHAR(200),                  -- cargo
    document_number VARCHAR(20),
    status VARCHAR(50),
    photo_url TEXT,
    jne_profile_id INTEGER,
    candidate_number INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candidates_party ON candidates(party_id);
CREATE INDEX IF NOT EXISTS idx_candidates_type ON candidates(election_type);
CREATE INDEX IF NOT EXISTS idx_candidates_constituency
    ON candidates(constituency) WHERE constituency IS NOT NULL;

-- ═══════════════════ Government Plans ═══════════════════

CREATE TABLE IF NOT EXISTS government_plans (
    id SERIAL PRIMARY KEY,
    party_key VARCHAR(100) UNIQUE NOT NULL,
    party_name VARCHAR(200) NOT NULL,
    candidate_name VARCHAR(200),
    pdf_path TEXT NOT NULL,
    total_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS plan_chunks (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES government_plans(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_title TEXT,
    content TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    token_count INTEGER,
    embedding vector(1024) NOT NULL,
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('spanish', content)) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(plan_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_plan_chunks_plan ON plan_chunks(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_chunks_embedding
    ON plan_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_plan_chunks_tsv
    ON plan_chunks USING gin(content_tsv);

-- ═══════════════════ News ═══════════════════

CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    source_name VARCHAR(200) NOT NULL,
    source_feed VARCHAR(50) DEFAULT 'google_news',
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    sentiment_label VARCHAR(20) DEFAULT 'neutral',
    adverse_categories TEXT[] DEFAULT '{}',
    author VARCHAR(200),
    image_url TEXT,
    total_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_mentions (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    party_name VARCHAR(200) NOT NULL,
    candidate_name VARCHAR(200),
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    UNIQUE(article_id, party_name)
);

CREATE TABLE IF NOT EXISTS news_chunks (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_url TEXT,
    token_count INTEGER,
    embedding vector(1024) NOT NULL,
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('spanish', content)) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(article_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_news_url_hash ON news_articles(url_hash);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_source ON news_articles(source_name);
CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news_articles(sentiment_label);

CREATE INDEX IF NOT EXISTS idx_news_mentions_article ON news_mentions(article_id);
CREATE INDEX IF NOT EXISTS idx_news_mentions_party ON news_mentions(party_name);

CREATE INDEX IF NOT EXISTS idx_news_chunks_article ON news_chunks(article_id);
CREATE INDEX IF NOT EXISTS idx_news_chunks_embedding
    ON news_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_news_chunks_tsv
    ON news_chunks USING gin(content_tsv);
