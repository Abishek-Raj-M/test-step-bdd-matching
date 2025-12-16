-- ===========================================
-- Database Initialization Script
-- ===========================================
-- Run this script as PostgreSQL superuser to set up the database
--
-- psql -U postgres -f scripts/init_database.sql
-- ===========================================

-- Create database (run this first if database doesn't exist)
-- Note: You may need to run this command separately or connect to 'postgres' database first
-- CREATE DATABASE teststep_rag;

-- Connect to the database
\c teststep_rag

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify pgvector is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Create teststep_chunks table
CREATE TABLE IF NOT EXISTS teststep_chunks (
    chunk_id SERIAL PRIMARY KEY,
    parent_testcase_id VARCHAR(255),
    original_chunk TEXT NOT NULL,
    normalized_chunk TEXT NOT NULL,
    action_verb VARCHAR(100),
    primary_object VARCHAR(255),
    placeholders JSONB,
    embedding vector(384),  -- Dimension matches all-MiniLM-L6-v2
    cluster_id INTEGER,
    chunk_index INTEGER,
    normalization_version VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create HNSW index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON teststep_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Create indexes for joins
CREATE INDEX IF NOT EXISTS idx_chunks_cluster_id ON teststep_chunks(cluster_id);
CREATE INDEX IF NOT EXISTS idx_chunks_parent_id ON teststep_chunks(parent_testcase_id);

-- Create feature_steps table (canonical BDD templates)
CREATE TABLE IF NOT EXISTS feature_steps (
    id SERIAL PRIMARY KEY,
    canonical_template TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    cluster_id INTEGER UNIQUE NOT NULL,
    embedding vector(384),  -- Dimension matches all-MiniLM-L6-v2
    doc_tsv TSVECTOR,  -- For lexical search
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create HNSW index for feature_steps
CREATE INDEX IF NOT EXISTS idx_feature_steps_embedding ON feature_steps 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Create GIN index for lexical search
CREATE INDEX IF NOT EXISTS idx_feature_steps_tsv ON feature_steps 
    USING GIN (doc_tsv);

-- Create index for cluster_id
CREATE INDEX IF NOT EXISTS idx_feature_steps_cluster_id ON feature_steps(cluster_id);

-- Verify tables were created
\dt

-- Show table structure
\d teststep_chunks
\d feature_steps

-- Success message
SELECT 'Database initialized successfully!' as status;












