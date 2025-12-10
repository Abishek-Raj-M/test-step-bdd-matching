# BGE-m3 Normalization Branch - Structure & Changes Summary

## New Structure

```
feature/bge-m3-normalization/
├── plans/
│   ├── bge-m3-normalization.md          # Implementation plan
│   └── problems_to_address.md            # Normalization issues addressed
├── src/
│   ├── normalizer.py                     # Normalization v2.0 (domain-aware)
│   ├── embedder.py                       # BGE-m3 embeddings (1024-d)
│   ├── reranker.py                       # BGE reranker v2-m3
│   ├── database.py                       # Clean table names (no suffix)
│   ├── pipeline.py                       # Matching pipeline
│   ├── ingestion.py                      # Data ingestion
│   ├── chunker.py                        # Step chunking
│   ├── retrieval.py                     # Vector search
│   ├── batch_processor.py                # Batch processing
│   ├── metrics.py                        # Evaluation metrics
│   └── [other core modules]
├── scripts/
│   ├── process_single_testcase.py       # Process individual test cases
│   ├── drop_v2_tables.sql                # Cleanup old v2 tables
│   ├── init_database.sql                 # Database initialization
│   ├── download_models.py                # Model download helper
│   └── [utility scripts]
├── config.yaml                           # Clean config (no legacy options)
├── main.py                               # Entry point
├── requirements.txt                      # Dependencies
├── README.md                             # Updated for bge-m3 branch
└── SETUP_NEW_DATABASE.md                 # Setup instructions
```

## What Changed

### 1. **Removed Legacy Code**
   - ❌ Removed `use_legacy_embedding` toggle
   - ❌ Removed `reranker_use_fallback` toggle
   - ❌ Removed `table_suffix` logic (no more `_v2` tables)
   - ❌ Removed all fallback/legacy model options

### 2. **New Database**
   - ✅ New database: `teststep_rag_bgem3` (completely separate)
   - ✅ Clean table names: `feature_steps`, `bdd_individual_steps`, `teststep_chunks`
   - ✅ No version suffixes needed (fresh start)

### 3. **Model Stack**
   - ✅ Embedding: `BAAI/bge-m3` (1024 dimensions)
   - ✅ Reranker: `BAAI/bge-reranker-v2-m3`
   - ✅ Cache: `.embedding_cache_bgem3`

### 4. **Normalization v2.0**
   - ✅ Domain token preservation (F-keys, ENTER, arrows, etc.)
   - ✅ Action verb canonicalization
   - ✅ Count phrase preservation
   - ✅ Structured output for reranker

### 5. **Code Simplification**
   - ✅ Removed all conditional logic for legacy/fallback models
   - ✅ Single code path: bge-m3 + normalization v2.0 only
   - ✅ Cleaner config structure

## Example: Before vs After Normalization

### Input Test Step:
```
"Press F8 4 times until it brings up the Numbers table"
```

### OLD Normalization (v1.0):
```python
normalized_text: "press <NUMBER> times until it brings up the numbers table"
action_verb: "press"
primary_object: None
# Problems:
# - Lost "F8" (critical domain term)
# - Lost "4" (became generic <NUMBER>)
# - Lost "times" context
# - Reranker can't see domain-specific cues
```

### NEW Normalization (v2.0):
```python
normalized_text: "press f8 <COUNT> times until it brings up the numbers table"
action_verb: "press"
action_canonical: "press"  # Canonicalized from "press"
primary_object: "numbers"
domain_terms: ["F8"]  # Preserved!
count_phrases: ["4 times"]  # Preserved!
placeholders: [
    Placeholder(type="COUNT", value="4 times", position=...)
]
# Benefits:
# - F8 preserved in domain_terms
# - "4 times" preserved as count phrase
# - Reranker sees structured cues: "Action: press | Domain: F8 | Counts: 4 times | Text: ..."
```

## Reranker Input Format

### Query Side:
```
Action: press | Domain: F8 | Counts: 4 times | Text: press f8 <COUNT> times until it brings up the numbers table
```

### Candidate Side:
```
Action: press | Domain: F8 | Counts: 4 times | Text: press f8 <COUNT> times until numbers table appears
```

The reranker now sees:
- **Action canonicalization**: Both use "press" (even if one said "click")
- **Domain terms**: Both have "F8" explicitly
- **Count phrases**: Both have "4 times"
- **Normalized text**: Clean comparison

## Database Schema

### New Database: `teststep_rag_bgem3`

**Tables:**
- `feature_steps` - BDD scenarios (1024-d embeddings)
- `bdd_individual_steps` - Individual Given/When/Then steps (1024-d embeddings)
- `teststep_chunks` - Manual step chunks (1024-d embeddings)

**No version suffixes** - clean table names in a new database.

## Configuration Example

```yaml
# config.yaml
embedding_model_name: "BAAI/bge-m3"
embedding_dim: 1024
normalization_version: "2.0"
database:
  database: "teststep_rag_bgem3"  # New database
```

## Processing Flow Example

1. **Input**: "Press F8 4 times"
2. **Normalize (v2.0)**:
   - Extract: `domain_terms=["F8"]`, `count_phrases=["4 times"]`
   - Canonicalize: `action_canonical="press"`
   - Normalize text: `"press f8 <COUNT> times"`
3. **Embed**: Generate 1024-d vector with bge-m3
4. **Retrieve**: Vector search in `bdd_individual_steps` table
5. **Rerank**: Format query/candidate with structured cues, rerank with bge-reranker-v2-m3
6. **Output**: Top-K matches with scores

## Key Improvements

1. **Domain Term Preservation**: F-keys, ENTER, arrows preserved
2. **Action Canonicalization**: "click" → "press", "type" → "enter"
3. **Count Preservation**: "4 times" not lost to generic `<NUMBER>`
4. **Structured Reranker Input**: Reranker sees action/domain/count cues
5. **Better Embeddings**: 1024-d bge-m3 vs 768-d all-mpnet-base-v2
6. **Better Reranker**: bge-reranker-v2-m3 optimized for bge-m3 embeddings

