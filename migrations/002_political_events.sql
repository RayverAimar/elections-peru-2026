-- 002_political_events.sql
-- Political events that voters should know about

CREATE TABLE IF NOT EXISTS political_events (
    id VARCHAR(100) PRIMARY KEY,
    title TEXT NOT NULL,
    event_date DATE,
    category VARCHAR(30) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    description TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    sources TEXT[] DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS event_party_stances (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL REFERENCES political_events(id) ON DELETE CASCADE,
    party_name VARCHAR(200) NOT NULL,
    stance VARCHAR(20) NOT NULL,
    detail TEXT,
    UNIQUE(event_id, party_name)
);

CREATE TABLE IF NOT EXISTS event_chunks (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL REFERENCES political_events(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    sources TEXT[] DEFAULT '{}',
    token_count INTEGER,
    embedding vector(1024) NOT NULL,
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('spanish', content)) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_events_category ON political_events(category);
CREATE INDEX IF NOT EXISTS idx_events_severity ON political_events(severity);
CREATE INDEX IF NOT EXISTS idx_events_date ON political_events(event_date DESC);

CREATE INDEX IF NOT EXISTS idx_event_stances_event ON event_party_stances(event_id);
CREATE INDEX IF NOT EXISTS idx_event_stances_party ON event_party_stances(party_name);

CREATE INDEX IF NOT EXISTS idx_event_chunks_event ON event_chunks(event_id);
CREATE INDEX IF NOT EXISTS idx_event_chunks_embedding
    ON event_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_event_chunks_tsv
    ON event_chunks USING gin(content_tsv);
