# Setting Up New Database for BGE-m3 Feature Branch

This feature branch uses a **completely new database** separate from the old implementation.

## Cleanup Steps

### 1. Drop v2 Tables from Old Database (if they exist)

If you previously ran ingestion with `_v2` table suffix, clean them up:

```bash
psql -U postgres -d teststep_rag -f scripts/drop_v2_tables.sql
```

Or manually:
```sql
DROP TABLE IF EXISTS bdd_individual_steps_v2 CASCADE;
DROP TABLE IF EXISTS teststep_chunks_v2 CASCADE;
DROP TABLE IF EXISTS feature_steps_v2 CASCADE;
```

### 2. Create New Database

```bash
psql -U postgres -c "CREATE DATABASE teststep_rag_bgem3;"
```

### 3. Verify Configuration

Check `config.yaml`:
- `database.database: "teststep_rag_bgem3"` (new database name)
- `embedding_model_name: "BAAI/bge-m3"` (no legacy options)
- `reranker_model_name: "BAAI/bge-reranker-v2-m3"` (no fallback options)
- `normalization_version: "2.0"` (only v2)

### 4. Run Ingestion

```bash
python main.py --mode ingest --input "csv files/Already_Automated_Tests_nrm.csv"
```

This will:
- Create fresh tables in `teststep_rag_bgem3`
- Use normalization v2.0
- Generate 1024-d embeddings with BAAI/bge-m3
- Store embeddings in pgvector (no local cache for stored data)

## What's Different in This Branch

- **No legacy/fallback options**: Only bge-m3 and normalization v2.0
- **Clean table names**: No `_v2` suffix (it's a new database)
- **New database**: `teststep_rag_bgem3` (completely separate)
- **Simplified code**: Removed all toggle/fallback logic

## Files Changed

- `config.yaml`: Removed legacy/fallback options, new DB name
- `src/config.py`: Removed legacy/fallback config fields
- `src/database.py`: Removed table_suffix logic
- `main.py`: Removed legacy embedding/reranker switches
- `scripts/process_single_testcase.py`: Uses clean model names

