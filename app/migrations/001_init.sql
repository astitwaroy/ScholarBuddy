CREATE EXTENSION IF NOT EXISTS vector;

-- One row per official source document listed in data/catalog.json.
CREATE TABLE documents (
  id          text PRIMARY KEY,
  title       text NOT NULL,
  url         text NOT NULL,
  version     text NOT NULL DEFAULT '',
  scheme_ids  text[] NOT NULL,
  kind        text NOT NULL DEFAULT 'guidelines',
  -- pending | ok | no_text (scanned image) | failed
  status      text NOT NULL DEFAULT 'pending',
  error       text,
  pages       integer,
  text_pages  integer,
  sha256      text,
  ingested_at timestamptz
);

-- Passages used for retrieval. Each knows its document, schemes, pages and section heading.
CREATE TABLE chunks (
  id          bigserial PRIMARY KEY,
  doc_id      text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  scheme_ids  text[] NOT NULL,
  ord         integer NOT NULL,
  page_start  integer NOT NULL,
  page_end    integer NOT NULL,
  section     text NOT NULL DEFAULT '',
  text        text NOT NULL,
  tsv         tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('english', section), 'A') || to_tsvector('english', text)
              ) STORED,
  embedding   vector(768)
);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX chunks_scheme_idx ON chunks USING gin (scheme_ids);
CREATE INDEX chunks_doc_idx ON chunks (doc_id, ord);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
