# BGE-m3 Reranker + Normalization Overhaul Plan

## Goals
- Reduce NEW_BDD_REQUIRED for high-similarity pairs by fixing normalization gaps called out in `problems_to_address.md`.
- Swap to `BAAI/bge-m3` embeddings and `BAAI/bge-reranker-v2-m3` (or lite fallback) for better cross-encoder matching.
- Preserve domain terms and action intent so reranker sees the critical tokens (F-keys, ENTER, CONFIRM, counts).

## Scope (in this branch)
- New embedding model + reranker wiring, config, and download support.
- Normalization rewrite (versioned) applied to both query chunks and BDD ingest.
- Re-embed and rebuild ANN index with new normalized texts.
- Structured reranker inputs that surface domain terms/action canon.
- Evaluation runs comparing old vs new on existing result sets.

## Model Stack Changes
- Embeddings: `BAAI/bge-m3` (dim=1024). Update `config.yaml`, `download_models.py`, embedder, and cache/index paths.
- Reranker: `BAAI/bge-reranker-v2-m3` primary; fallback option `bge-reranker-base-v1.5` if size/latency a concern. Make model selectable via config.
- Ensure `sentence-transformers`/torch versions compatible; pin in `requirements.txt`.

## Normalization Overhaul (versioned)
- Domain whitelist: keep tokens like F1–F12, ENTER, TAB, BACKSPACE, ARROW keys, CONFIRM, GREEN ARROW, PURPLE ARROW, etc. Do not lowercase these away; preserve repetitions (e.g., “F8 4 times”).
- Action verb canonicalization: map {press|click|use|confirm}→`press`; {enter|type|input}→`enter`; {select|choose|pick}→`select`; apply symmetrically to queries and BDD steps.
- Placeholder refinement: avoid replacing counts and keypress counts with `<NUMBER>`; keep adjacent units (e.g., “4 times”, “2 selections”). Keep monetary/ID patterns but add type tags to placeholders.
- Structured normalized output: include `normalized_text`, `domain_terms`, `action_canon`, `count_phrases`, and placeholder metadata to feed reranker formatting.
- Version bump (e.g., normalization_version: "2.0") and keep old path accessible via config flag for A/B.

## Reranker Input Formatting
- Build pair text with structured cues, e.g.: `Action: <canon>; Domain: <terms>; Text: <normalized>`.
- Ensure candidate-side uses the same new normalization fields (re-normalize stored BDD steps).

## Data Regeneration
- Re-normalize all BDD individual steps with new normalizer; store both raw and normalized variants.
- Re-embed using `bge-m3` and rebuild ANN index; version index path to avoid clobbering old one.
- Update ingestion/migration scripts to run with the new normalization pipeline.

## Evaluation Plan
- Run existing metrics scripts on saved result sets (e.g., `output/2025-12-08_*`) comparing old vs new.
- Track: REUSED_TEMPLATE rate, reranker score lift on high-similarity cases, reduction in “domain term missing” cases.
- Spot-check failure modes in `problems_to_address.md` examples (F8, ENTER, CONFIRM, phrasing).

## Rollout / Controls
- Config flag to switch between old/new normalizer and reranker.
- Keep `top_k_results` and `min_score_threshold` tunable; expect new score scale with m3 reranker.

## Risks / Mitigations
- Model size/latency: keep fallback reranker; allow CPU/GPU selection.
- Token drift: ensure domain whitelist is exhaustive for F-keys and arrows; add tests for preservation.
- Index incompatibility: versioned cache/index paths to avoid collisions.

## Deliverables in this branch
- Code changes for models, normalization, reranker formatting, ingestion/index rebuild hooks.
- Plan and config updates; documented switches for A/B.

