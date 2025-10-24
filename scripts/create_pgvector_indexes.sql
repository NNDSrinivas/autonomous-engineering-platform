-- Create pgvector indexes for ANN search (PR-16)
-- 
-- This script creates the appropriate index type based on PGVECTOR_INDEX env variable.
-- 
-- HNSW (Hierarchical Navigable Small World):
--   - Best for: High recall, fast queries
--   - Requires: pgvector >= 0.5.0
--   - Memory: ~200 bytes per vector
--   - Build time: Slower
-- 
-- IVFFLAT (Inverted File with Flat):
--   - Best for: Large datasets (>1M vectors)
--   - Requires: pgvector >= 0.2.0
--   - Memory: Lower than HNSW
--   - Build time: Faster
--   - Tuning: Adjust lists parameter (100 is default)

-- Drop existing indexes (idempotent)
DROP INDEX IF EXISTS idx_memory_chunk_vec_hnsw;
DROP INDEX IF EXISTS idx_memory_chunk_vec_ivf;

-- Create HNSW index (default, recommended for most use cases)
-- Using vector_cosine_ops for cosine distance
CREATE INDEX IF NOT EXISTS idx_memory_chunk_vec_hnsw
  ON memory_chunk USING hnsw (embedding_vec vector_cosine_ops);

-- Alternative: Create IVFFLAT index (uncomment if preferred)
-- Adjust 'lists' parameter based on dataset size:
--   - lists = sqrt(total_rows) is a good starting point
--   - Minimum: 10, Maximum: 32768
-- 
-- CREATE INDEX IF NOT EXISTS idx_memory_chunk_vec_ivf
--   ON memory_chunk USING ivfflat (embedding_vec vector_cosine_ops) 
--   WITH (lists = 100);

-- Performance tuning hints:
-- For IVFFLAT queries, set probes to control accuracy/speed tradeoff:
--   SET ivfflat.probes = 10;  -- Higher = more accurate but slower
--   Default probes = 1 (fastest, lower recall)
--   Recommended: 5-20 depending on use case

-- Vacuum and analyze for optimal query planning
VACUUM ANALYZE memory_chunk;
