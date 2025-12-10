-- Drop v2 tables from old database (teststep_rag)
-- Run this on the old database to clean up the v2 collection
-- BEFORE creating the new database for this feature branch

-- Connect to old database first:
-- psql -U postgres -d teststep_rag

-- Drop v2 tables (in dependency order)
DROP TABLE IF EXISTS bdd_individual_steps_v2 CASCADE;
DROP TABLE IF EXISTS teststep_chunks_v2 CASCADE;
DROP TABLE IF EXISTS feature_steps_v2 CASCADE;

-- Verify tables are dropped
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name LIKE '%_v2';

