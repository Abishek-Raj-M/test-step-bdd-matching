# BGE-m3 Normalization Feature Branch

This branch implements the BGE-m3 embedding model with improved normalization (v2.0) for better test step to BDD matching.

## Features

- **BGE-m3 Embeddings**: 1024-dimensional embeddings using `BAAI/bge-m3`
- **BGE Reranker**: `BAAI/bge-reranker-v2-m3` for cross-encoder reranking
- **Normalization v2.0**: Domain-aware normalization preserving F-keys, action verbs, and counts
- **Clean Architecture**: No legacy/fallback code - only bge-m3 + normalization v2.0

## Requirements

- Python 3.8+
- PostgreSQL 12+ with pgvector extension
- spaCy English model (optional, for advanced features)
- `sentence-transformers>=3.0.0`
- `torch>=2.2.0`

## Setup

See `SETUP_NEW_DATABASE.md` for complete setup instructions.

1. Create new database:
```bash
psql -U postgres -c "CREATE DATABASE teststep_rag_bgem3;"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

3. Download models (first time):
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-v2-m3')"
```

4. Update `config.yaml` with your database credentials

## Usage

### Ingest BDD Steps

```bash
python main.py --mode ingest --input "csv files/Already_Automated_Tests_nrm.csv"
```

### Process Test Cases

```bash
python scripts/process_single_testcase.py --input "csv files/new_test_steps_chunked.csv" --limit 4
```

## Configuration

- **Embedding**: `BAAI/bge-m3` (1024 dimensions)
- **Reranker**: `BAAI/bge-reranker-v2-m3`
- **Normalization**: Version 2.0 (domain-aware)
- **Database**: `teststep_rag_bgem3` (new database for this branch)

## Plans

See `plans/bge-m3-normalization.md` for the implementation plan and `plans/problems_to_address.md` for normalization issues addressed.
