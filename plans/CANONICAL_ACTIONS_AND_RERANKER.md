# Canonical Actions and Reranker Usage: Analysis and Improvement Plan

## Overview

This document analyzes how canonical actions are used in the reranker, identifies current limitations, and proposes potential improvements.

---

## What Are Canonical Actions?

### Definition

**Canonical actions** are standardized action verbs that map multiple synonymous verbs to a single canonical form.

**Mapping Examples:**
- `"click" → "press"`
- `"type" → "enter"`
- `"choose" → "select"`
- `"hit" → "press"`
- `"tap" → "press"`

### Purpose

1. **Semantic Equivalence**: Treats "click" and "press" as the same action
2. **Consistent Matching**: Ensures similar actions match even with different verb choices
3. **Reranker Enhancement**: Provides explicit action cues to improve cross-encoder scoring

---

## Current Implementation

### 1. Canonicalization Map

**Location:** `src/normalizer.py` lines 48-55

```python
self.action_canon_map = {
    "press": "press", "click": "press", "hit": "press", "tap": "press", "confirm": "press",
    "enter": "enter", "type": "enter", "input": "enter", "key": "enter",
    "select": "select", "choose": "select", "pick": "select",
    "navigate": "navigate", "go": "navigate", "open": "navigate",
    "verify": "verify", "check": "verify", "assert": "verify",
}
```

### 2. When Canonicalization Happens

**During Normalization:**
1. Extract action verb from text (e.g., "click")
2. Look up in `action_canon_map` → returns "press"
3. Store in `NormalizedResult.action_canonical`
4. Re-inject into normalized text: `"press click the f12 button"`

**Location:** `src/normalizer.py` lines 100-106

### 3. Storage in Database

**Current State:**
- ❌ `action_canonical` is **NOT stored** as a database column
- ✅ Canonicalized action is **embedded in `normalized_text`**
- ✅ Embeddings are computed from canonicalized text
- ✅ `action_verb` is stored (original, not canonical) for test steps only

**Tables:**
- `teststep_chunks`: Has `action_verb` (original), `normalized_chunk` (contains canonical)
- `bdd_individual_steps`: Has `step_text_normalized` (contains canonical), no `action_verb` column

---

## How Reranker Uses Canonical Actions

### 1. Query Formatting

**Location:** `src/reranker.py` lines 59-71

**What Happens:**
```python
# Query: "Click the F12 button"
# After normalization:
#   action_canonical = "press"
#   domain_terms = ["F12"]
#   normalized_text = "press click the f12 button"

# Reranker formats as:
query_text = "Action: press | Domain: F12 | Text: press click the f12 button"
```

**Code:**
```python
def _format_query_text(self, query: Union[str, NormalizedResult]) -> str:
    if isinstance(query, NormalizedResult):
        parts = []
        if query.action_canonical:
            parts.append(f"Action: {query.action_canonical}")  # ← Explicit action cue
        if query.domain_terms:
            parts.append(f"Domain: {' '.join(query.domain_terms)}")
        if query.count_phrases:
            parts.append(f"Counts: {' '.join(query.count_phrases)}")
        parts.append(f"Text: {query.normalized_text}")
        return " | ".join(parts)
    return query
```

### 2. Candidate Formatting

**Location:** `src/reranker.py` lines 73-104

**What Happens:**
```python
# Candidate from DB: "Press F12 key"
#   step_text_normalized = "press f12 key"
#   action_canonical = None (not stored in DB)

# Reranker formats as:
candidate_text = "Text: press f12 key"  # ← Missing "Action: press"
```

**Code:**
```python
def _format_candidate_text(self, candidate: Dict[str, Any]) -> str:
    parts = []
    action_canon = candidate.get("action_canonical")  # ← Will be None for DB candidates
    
    if action_canon:
        parts.append(f"Action: {action_canon}")  # ← Never executed for DB candidates
    
    # Falls back to just normalized text
    candidate_text = candidate.get('step_text_normalized') or ...
    parts.append(f"Text: {candidate_text}")
    return " | ".join(parts)
```

### 3. Cross-Encoder Input

**Location:** `src/reranker.py` lines 30-38

**What Gets Sent to Model:**
```python
pairs = [
    [
        "Action: press | Domain: F12 | Text: press click the f12 button",  # Query (has action)
        "Text: press f12 key"  # Candidate (missing action)
    ],
    # ... more pairs
]

scores = model.predict(pairs)  # Cross-encoder scores each pair
```

---

## Current Limitations

### Problem 1: Asymmetric Input

**Query Side:**
- ✅ Has explicit `action_canonical`
- ✅ Formatted as: `"Action: press | Text: ..."`

**Candidate Side:**
- ❌ Missing `action_canonical` (not stored in DB)
- ❌ Formatted as: `"Text: ..."` (no action cue)

**Impact:**
- Reranker can't directly compare canonical actions
- Less precise matching when verbs differ
- Cross-encoder has to infer action from text alone

### Problem 2: No Action Extraction for Candidates

**Current Flow:**
1. Candidates retrieved from DB with `step_text_normalized`
2. Reranker tries to get `action_canonical` from candidate dict
3. It's `None` (not stored)
4. Falls back to just normalized text

**Missing Step:**
- No extraction of `action_canonical` from `step_text_normalized` at query time
- Could compute it on-the-fly, but currently doesn't

### Problem 3: Inconsistent Structure

**Query:**
```
"Action: press | Domain: F12 | Text: press click the f12 button"
```

**Candidate:**
```
"Text: press f12 key"
```

**Issue:** Different structures make it harder for cross-encoder to align fields

---

## Potential Improvements

### Option 1: Store `action_canonical` in Database

**Pros:**
- ✅ Explicit action available for all candidates
- ✅ Consistent structure (query and candidate both have action)
- ✅ No computation needed at query time
- ✅ Can query/filter by canonical action

**Cons:**
- ❌ Redundant (already in normalized_text)
- ❌ Storage overhead (minimal)
- ❌ Need to update existing data if rules change
- ❌ Requires database migration

**Implementation:**
```sql
ALTER TABLE bdd_individual_steps 
ADD COLUMN action_canonical VARCHAR(50);

ALTER TABLE teststep_chunks 
ADD COLUMN action_canonical VARCHAR(50);

-- Update existing rows
UPDATE bdd_individual_steps 
SET action_canonical = (
    SELECT canonical 
    FROM action_canon_map 
    WHERE verb = extracted_action_verb
);
```

**Code Changes:**
- Update `IndividualBDDStep` dataclass
- Update `insert_individual_bdd_step()` to store `action_canonical`
- Update `vector_search()` to return `action_canonical` in candidate dict

### Option 2: Compute `action_canonical` at Query Time

**Pros:**
- ✅ No database changes needed
- ✅ Always uses latest canonicalization rules
- ✅ No storage overhead
- ✅ Easy to implement

**Cons:**
- ❌ Computation overhead (minimal)
- ❌ Need to extract action verb from normalized text
- ❌ Less efficient than pre-computed

**Implementation:**
```python
# In retrieval.py or pipeline.py, when building candidate dicts:
def _extract_action_from_normalized(self, normalized_text: str) -> Optional[str]:
    """Extract and canonicalize action from normalized text."""
    # Extract first verb (action)
    words = normalized_text.split()
    action_verb = None
    for word in words:
        if word in self.action_verbs:
            action_verb = word
            break
    
    # Canonicalize
    if action_verb:
        return self.action_canon_map.get(action_verb, action_verb)
    return None

# When building candidate dict:
candidate_dict = {
    "id": row[0],
    "step_text": row[1],
    "step_text_normalized": row[2],
    "action_canonical": self._extract_action_from_normalized(row[2]),  # ← Compute on-the-fly
    # ... other fields
}
```

### Option 3: Hybrid Approach

**Store in DB + Compute at Query Time:**
- Store `action_canonical` in database (for efficiency)
- Compute at query time as fallback (if missing)
- Best of both worlds

**Implementation:**
```python
# In _format_candidate_text():
action_canon = (
    candidate.get("action_canonical") or  # From DB
    self._extract_action_from_normalized(candidate.get("step_text_normalized"))  # Fallback
)
```

---

## Recommended Approach

### Short Term: Option 2 (Compute at Query Time)

**Why:**
- ✅ No database migration needed
- ✅ Quick to implement
- ✅ Always uses latest rules
- ✅ Minimal performance impact

**Implementation Steps:**
1. Add `_extract_action_from_normalized()` method to `Retrieval` or `Pipeline` class
2. Update candidate dict building to include computed `action_canonical`
3. Test that reranker now receives action for candidates

### Long Term: Option 1 (Store in Database)

**Why:**
- ✅ More efficient (no computation at query time)
- ✅ Queryable/filterable
- ✅ Consistent with query structure
- ✅ Better for production scale

**Implementation Steps:**
1. Add `action_canonical` column to `bdd_individual_steps` table
2. Add `action_canonical` column to `teststep_chunks` table (optional)
3. Update ingestion to compute and store `action_canonical`
4. Migrate existing data
5. Update retrieval to return `action_canonical` in candidate dicts

---

## Testing Plan

### Test Cases

1. **Action Matching:**
   - Query: "Click F12 button" → Should match "Press F12 key"
   - Verify reranker sees "Action: press" for both

2. **Different Actions:**
   - Query: "Click button" → Should NOT match "Enter text"
   - Verify reranker distinguishes different canonical actions

3. **Missing Action:**
   - Query: "Navigate to page" → Should still work if action not found
   - Verify graceful fallback

4. **Performance:**
   - Measure reranker time with/without action canonical
   - Verify no significant slowdown

### Metrics

- **Reranker Score Improvement**: Compare scores with/without explicit action
- **Match Accuracy**: Test if explicit action improves matching
- **Performance**: Measure computation overhead

---

## Code Locations Reference

### Current Implementation

- **Canonicalization Map**: `src/normalizer.py` lines 48-55
- **Canonicalization Logic**: `src/normalizer.py` lines 271-275
- **Query Formatting**: `src/reranker.py` lines 59-71
- **Candidate Formatting**: `src/reranker.py` lines 73-104
- **Database Schema**: `src/database.py` lines 187-200

### Files to Modify (if implementing improvements)

- `src/database.py` - Add column, update insert/retrieve methods
- `src/retrieval.py` - Compute action_canonical for candidates
- `src/ingestion.py` - Store action_canonical during ingestion
- `src/reranker.py` - Already handles it, just needs data

---

## Questions to Consider

1. **Is the performance improvement worth the database migration?**
   - Current: Works but suboptimal
   - With DB column: More efficient, better matching

2. **Should we store for both test steps and BDD steps?**
   - Currently only test steps have `action_verb`
   - BDD steps would benefit from `action_canonical`

3. **What if canonicalization rules change?**
   - Need migration strategy
   - Or compute at query time (always latest rules)

4. **Is explicit action cue actually improving reranker scores?**
   - Need to test/measure
   - May not be worth the complexity if minimal improvement

---

## Next Steps

1. **Review this document** - Understand current state and limitations
2. **Decide on approach** - Option 1 (DB) vs Option 2 (compute) vs Option 3 (hybrid)
3. **Implement chosen approach** - Make code changes
4. **Test improvements** - Measure impact on reranker scores
5. **Deploy if beneficial** - Roll out to production

---

**Last Updated:** 2025-12-10  
**Status:** Analysis Complete - Awaiting Decision on Implementation Approach

