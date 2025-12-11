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

**Location:** `src/reranker.py` lines 74-131

**What Happens (UPDATED - On-the-Fly Extraction):**
```python
# Candidate from DB: "Press F12 key"
#   step_text = "Press F12 key" (original)
#   step_text_normalized = "press f12 key"
#   action_canonical = None (not stored in DB)

# Reranker re-normalizes on-the-fly:
#   1. Gets original step_text
#   2. Re-normalizes to extract: action_canonical="press", domain_terms=["F12"]
#   3. Formats with structured cues

# Reranker formats as:
candidate_text = "Action: press | Domain: F12 | Text: press f12 key"  # ✅ Now has structured cues
```

**Code:**
```python
def _format_candidate_text(self, candidate: Dict[str, Any]) -> str:
    parts = []
    action_canon = candidate.get("action_canonical")
    domain_terms = candidate.get("domain_terms") or candidate.get("domain_tokens")
    count_phrases = candidate.get("count_phrases")
    
    # ✅ NEW: If structured fields are missing and we have a normalizer, re-normalize on-the-fly
    if self.normalizer and (not action_canon or not domain_terms or not count_phrases):
        original_text = candidate.get('step_text') or candidate.get('bdd_step') or ...
        if original_text:
            normalized_result = self.normalizer.normalize(original_text)
            # Extract structured fields from normalized result
            if not action_canon and normalized_result.action_canonical:
                action_canon = normalized_result.action_canonical
            if not domain_terms and normalized_result.domain_terms:
                domain_terms = normalized_result.domain_terms
            if not count_phrases and normalized_result.count_phrases:
                count_phrases = normalized_result.count_phrases
    
    # Format with structured cues (now available)
    if action_canon:
        parts.append(f"Action: {action_canon}")
    if domain_terms:
        parts.append(f"Domain: {' '.join(domain_terms)}")
    if count_phrases:
        parts.append(f"Counts: {' '.join(count_phrases)}")
    
    candidate_text = candidate.get('step_text_normalized') or ...
    parts.append(f"Text: {candidate_text}")
    return " | ".join(parts)
```

### 3. Cross-Encoder Input

**Location:** `src/reranker.py` lines 30-38

**What Gets Sent to Model (UPDATED):**
```python
pairs = [
    [
        "Action: press | Domain: F12 | Text: press click the f12 button",  # Query (has action)
        "Action: press | Domain: F12 | Text: press f12 key"  # Candidate (now has action too!)
    ],
    # ... more pairs
]

scores = model.predict(pairs)  # Cross-encoder scores each pair
```

**Note:** Both query and candidate now have symmetric structured cues, improving matching accuracy.

---

## Current Implementation Status

### ✅ RESOLVED: Asymmetric Input (Fixed via On-the-Fly Extraction)

**Query Side:**
- ✅ Has explicit `action_canonical`
- ✅ Formatted as: `"Action: press | Domain: F12 | Text: ..."`

**Candidate Side (UPDATED):**
- ✅ Now extracts `action_canonical` on-the-fly via re-normalization
- ✅ Formatted as: `"Action: press | Domain: F12 | Text: ..."` (symmetric with query)

**Solution Implemented:**
- Reranker now re-normalizes candidate's original text when structured fields are missing
- Extracts `action_canonical`, `domain_terms`, and `count_phrases` on-the-fly
- No database changes required
- Always uses latest normalization rules

**Impact:**
- ✅ Reranker can now directly compare canonical actions
- ✅ More precise matching when verbs differ
- ✅ Cross-encoder receives symmetric structured input
- ✅ Better alignment between query and candidate structures

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

## Implementation Status

### ✅ IMPLEMENTED: Option 2 (Compute at Query Time via On-the-Fly Re-normalization)

**Implementation Completed:**
- ✅ Reranker now accepts `normalizer` parameter
- ✅ `_format_candidate_text()` re-normalizes candidates when structured fields are missing
- ✅ Extracts `action_canonical`, `domain_terms`, and `count_phrases` on-the-fly
- ✅ No database migration needed
- ✅ Always uses latest normalization rules
- ✅ Minimal performance impact (only re-normalizes when needed)

**Code Changes Made:**
1. ✅ Updated `Reranker.__init__()` to accept optional `normalizer` parameter
2. ✅ Enhanced `_format_candidate_text()` to re-normalize when structured fields missing
3. ✅ Updated all `Reranker` instantiations to pass `normalizer`
4. ✅ Both query and candidate now have symmetric structured cues

**Result:**
- Query: `"Action: press | Domain: F12 | Text: press click the f12 button"`
- Candidate: `"Action: press | Domain: F12 | Text: press f12 key"` ✅

### Future Consideration: Option 1 (Store in Database)

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
- **Query Formatting**: `src/reranker.py` lines 60-72
- **Candidate Formatting (with on-the-fly extraction)**: `src/reranker.py` lines 74-131
- **Database Schema**: `src/database.py` lines 187-200

### Files Modified (Implementation Complete)

- ✅ `src/reranker.py` - Added on-the-fly re-normalization in `_format_candidate_text()`
- ✅ `main.py` - Updated to pass `normalizer` to `Reranker`
- ✅ `scripts/process_single_testcase.py` - Updated to pass `normalizer` to `Reranker`

**Note:** No database changes needed - solution uses on-the-fly extraction

---

## Questions to Consider

1. ✅ **Is the performance improvement worth the database migration?**
   - **RESOLVED:** Implemented on-the-fly extraction - no migration needed
   - Performance impact is minimal (only re-normalizes when structured fields missing)

2. **Should we store for both test steps and BDD steps?**
   - Currently only test steps have `action_verb`
   - BDD steps now benefit from on-the-fly extraction (no storage needed)

3. ✅ **What if canonicalization rules change?**
   - **RESOLVED:** On-the-fly extraction always uses latest normalization rules
   - No migration needed when rules change

4. **Is explicit action cue actually improving reranker scores?**
   - ✅ Now implemented - can test/measure impact
   - Both query and candidate have symmetric structured cues

---

## Next Steps

1. ✅ **Review this document** - Understand current state and limitations
2. ✅ **Decide on approach** - Chose Option 2 (on-the-fly extraction)
3. ✅ **Implement chosen approach** - Code changes completed
4. **Test improvements** - Measure impact on reranker scores (recommended)
5. **Deploy if beneficial** - Ready for production use

**Current Status:** Implementation complete, ready for testing and validation

---

**Last Updated:** 2025-12-10  
**Status:** ✅ IMPLEMENTED - On-the-Fly Extraction via Re-normalization

**Implementation Date:** 2025-12-10  
**Solution:** Option 2 (Compute at Query Time) - Re-normalize candidates in reranker when structured fields are missing



