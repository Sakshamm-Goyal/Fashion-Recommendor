-- Enable pgvector in the default database
CREATE EXTENSION IF NOT EXISTS vector;

-- Optional: speed-friendly defaults for ivfflat indexes when the table arrives
-- (You still create the index in code; this just ensures the extension is available)
