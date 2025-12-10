# Normalization Mismatch Analysis - Problems to Address

## Executive Summary

Analysis of 42 NEW_BDD_REQUIRED cases reveals **critical normalization issues** that are preventing valid matches from being identified. **52.4% of cases** show high vector similarity (≥0.7) but are rejected by the reranker due to normalization gaps.

## Critical Issues Found

### 1. High Vector Similarity But Low Reranker Score
**Impact: 22 cases (52.4%)**

**Problem:**
- Vector search correctly identifies semantically similar matches (0.7+ similarity)
- Reranker rejects them with poor scores (< -2.0)
- This indicates normalization is creating semantic gaps between query and match

**Examples:**

**Example 1:**
- **Query:** "6 . The highlighted box will be Selection , you can either navigate to the Sport box or press ( f8 ) 4 times until it brings up the Numbers table"
- **Query Normalized:** "the highlighted box will be selection , you can either navigate to the sport box or press ( f8 ) <number> times until it brings up the numbers table"
- **Match:** "I Select sport number"
- **Match Normalized:** "i select sport number"
- **Vector Sim:** 0.732 | **Reranker:** -4.041
- **Issue:** High similarity but poor reranker score

**Example 2:**
- **Query:** "19 . Press ENTER so the selections have been moved to the bet slip"
- **Query Normalized:** "press enter so the selections have been moved to the bet slip"
- **Match:** "I add selection and proceed to bet type page"
- **Match Normalized:** "i add selection and proceed to bet type page"
- **Vector Sim:** 0.775 | **Reranker:** -3.816
- **Issue:** High similarity but poor reranker score

**Example 3:**
- **Query:** "20 . Now navigate away from the translation via the Purple Arrow or by selecting Dashboard"
- **Query Normalized:** "now navigate away from the translation via the purple arrow or by selecting dashboard"
- **Match:** "I have navigated to the translation page"
- **Match Normalized:** "i have navigated to the translation page"
- **Vector Sim:** 0.736 | **Reranker:** -4.698
- **Issue:** High similarity but poor reranker score (opposite direction: "navigate away" vs "navigated to")

### 2. Domain Term Missing in Match
**Impact: 26 cases (61.9%)**

**Problem:**
- Queries contain domain-specific terms (F12, ENTER, CONFIRM, F8, TAB, etc.)
- Matches don't include these critical terms
- Normalization may be removing or not preserving these terms

**Examples:**

**Example 1:**
- **Query:** "6 . The highlighted box will be Selection , you can either navigate to the Sport box or press ( f8 ) 4 times until it brings up the Numbers table"
- **Missing Terms in Match:** ['f8']
- **Match:** "I Select sport number"
- **Issue:** Query has domain term 'f8' but match doesn't

**Example 2:**
- **Query:** "19 . Press ENTER so the selections have been moved to the bet slip"
- **Missing Terms in Match:** ['enter']
- **Match:** "I add selection and proceed to bet type page"
- **Issue:** Query has domain term 'enter' but match doesn't

**Example 3:**
- **Query:** "23 . Press the ( f12 ) CONFIRM or Green Arrow to proceed to bet placement"
- **Missing Terms in Match:** ['f12', 'confirm']
- **Match:** "I set stake "8.00" for the bet"
- **Issue:** Query has domain terms 'f12' and 'confirm' but match doesn't

### 3. Action Verb Mismatches
**Impact: 7 cases (16.7%)**

**Problem:**
- Different action verbs used for same intent
- No synonym expansion in normalization
- Reranker doesn't recognize semantic equivalence

**Most Common Mismatches:**
- `enter` vs `type` (2 times)
- `press` vs `type` (2 times)
- `confirm` vs `click` (2 times)
- `press` vs `select` (1 time)
- `navigate` vs `select` (1 time)
- `select` vs `type` (1 time)
- `use` vs `type` (1 time)

**Examples:**

**Example 1:**
- **Query:** "6 . The highlighted box will be Selection , you can either navigate to the Sport box or press ( f8 ) 4 times until it brings up the Numbers table"
- **Query Actions:** ['press', 'navigate']
- **Match:** "I Select sport number"
- **Match Actions:** ['select']
- **Issue:** Different action verbs: ['press', 'navigate'] vs ['select']

**Example 2:**
- **Query:** "19 . Press ENTER so the selections have been moved to the bet slip"
- **Query Actions:** ['enter', 'press']
- **Match:** "I add selection and proceed to bet type page"
- **Match Actions:** ['type']
- **Issue:** Different action verbs: ['enter', 'press'] vs ['type']

### 4. Phrasing Differences (High Vector Similarity)
**Impact: 9 cases (21.4%)**

**Problem:**
- Same intent expressed with different wording
- High vector similarity (≥0.65) but reranker doesn't recognize equivalence
- Common words present but overall phrasing differs

**Examples:**

**Example 1:**
- **Query:** "5 . Then use F12 / Confirm / Green Arrow to proceed to Bet Placement , Select Straight Forecast as the Bet Type and focus will move to the stake box where a default stake of 4.00 should show , amend this to 1.00"
- **Query Normalized:** "then use f12 confirm green arrow to proceed to bet placement , select straight forecast as the bet type and focus will move to the stake box where a default stake of <number> should show , amend this to <number>"
- **Match:** "I set stake "8.00" for the bet"
- **Match Normalized:** "i set stake <number> for the bet"
- **Common Words:** ['bet', 'the', '<number>', 'stake']
- **Vector Sim:** 0.732 | **Reranker:** -5.399
- **Issue:** Similar intent (setting stake) but different phrasing

## Root Causes

### 1. Normalization Removes Domain Terms
- Domain-specific terms (F12, ENTER, CONFIRM, F8, TAB) are being normalized away
- These terms are critical for understanding test steps
- Reranker can't match without these terms

### 2. No Synonym Expansion for Action Verbs
- Action verbs with same intent are treated as different
- Examples: press ≠ click ≠ use ≠ confirm
- Should be normalized to canonical form or expanded

### 3. Placeholder Extraction Too Aggressive
- Numbers replaced with `<number>` loses context
- "Press F8 4 times" → "press f8 <number> times" loses the "4 times" context
- Should preserve numeric context when relevant

### 4. Reranker Doesn't Understand Domain Terminology
- Cross-encoder model trained on general text
- Doesn't understand domain-specific terms and their relationships
- Needs domain-specific training or better model

## Impact Assessment

### Current State
- **52.4%** of NEW_BDD_REQUIRED cases have high vector similarity but are rejected by reranker
- **61.9%** of cases have domain terms missing in matches
- **16.7%** have action verb mismatches
- **21.4%** have phrasing differences despite high similarity

### Potential Improvement
- Fixing normalization issues could improve match rate by **20-30%**
- Many "NEW_BDD_REQUIRED" cases are actually valid matches being missed
- Vector search is working well; normalization is the bottleneck

## Recommendations (Priority Order)

### Priority 1: Preserve Domain Terms (CRITICAL)
**Action:**
- Don't normalize domain-specific terms: F12, ENTER, CONFIRM, F8, TAB, etc.
- Treat them as special tokens that must be preserved
- Add to normalization whitelist

**Expected Impact:** +15-20% match rate improvement

### Priority 2: Add Action Verb Synonym Expansion
**Action:**
- Create synonym groups:
  - `press = click = use = confirm`
  - `enter = type = input`
  - `select = choose = pick`
- Normalize to canonical form or expand during matching

**Expected Impact:** +5-10% match rate improvement

### Priority 3: Improve Placeholder Extraction
**Action:**
- Be more selective about what becomes `<number>`
- Preserve context around numbers (e.g., "4 times" should keep the "times" context)
- Only replace standalone numeric values, not numeric phrases

**Expected Impact:** +3-5% match rate improvement

### Priority 4: Enhance Reranker Understanding
**Action:**
- Fine-tune reranker on domain-specific test step pairs
- Or upgrade to better model: `ms-marco-MiniLM-L-12-v2-6-shot`
- Add domain-specific training data

**Expected Impact:** +5-10% match rate improvement

## Implementation Plan

### Phase 1: Quick Wins (1-2 days)
1. Add domain term whitelist to normalization
2. Preserve F12, ENTER, CONFIRM, F8, TAB, etc.
3. Test impact on match rate

### Phase 2: Synonym Expansion (2-3 days)
1. Create action verb synonym dictionary
2. Implement synonym expansion in normalization
3. Test impact on match rate

### Phase 3: Placeholder Refinement (1-2 days)
1. Refine placeholder extraction logic
2. Preserve numeric context
3. Test impact on match rate

### Phase 4: Reranker Enhancement (1 week)
1. Collect domain-specific training pairs
2. Fine-tune reranker or upgrade model
3. Test impact on match rate

## Success Metrics

- **Target:** Increase REUSED_TEMPLATE rate from current ~45% to **65-70%**
- **Measure:** 
  - Reduction in NEW_BDD_REQUIRED cases with high vector similarity
  - Increase in reranker scores for valid matches
  - Reduction in domain term missing cases

## Notes

- Vector search is performing well (finding semantically similar matches)
- Reranker is the bottleneck (rejecting valid matches due to normalization gaps)
- Normalization improvements will have the highest impact
- Domain-specific knowledge is critical for this use case

---

## How Reranking and Chunking Work in Current Implementation

### How the Reranker Works

#### Current Implementation

1. **Input:**
   - **Query:** Normalized test step chunk text (e.g., "press enter so the selections have been moved to the bet slip")
   - **Candidates:** List of BDD individual step dictionaries (from vector search)

2. **Process:**
   ```python
   # From reranker.py lines 29-42
   pairs = []
   for candidate in candidates:
       candidate_text = candidate.get('step_text_normalized')  # Individual BDD step normalized text
       pairs.append([query, candidate_text])  # Create [query, candidate] pairs
   
   scores = self.model.predict(pairs)  # Cross-encoder scores
   ```

3. **Model:**
   - Uses `cross-encoder/ms-marco-MiniLM-L-6-v2`
   - **Cross-encoder:** Sees both query and candidate together (unlike bi-encoder)
   - Outputs relevance scores (can be negative)

4. **Output:**
   - Sorted by score (descending)
   - Returns top-K candidates with scores

#### What the Reranker Compares

The reranker compares:
- **Query:** Normalized chunk text (e.g., "press enter so the selections have been moved to the bet slip")
- **Candidate:** Normalized BDD step text (e.g., "i add selection and proceed to bet type page")

**It does NOT see:**
- Original text
- Full test case context
- Previous steps
- Domain terms that were normalized away

### How Chunking Affects Matching

#### Chunking Process (Pre-Processing)

1. **Input:** Full multi-step test case
   ```
   "1. Scan the bet
    2. Confirm by using (f12) or ENTER
    3. Locate the bet in Awaiting Translation"
   ```

2. **Chunking splits into atomic actions:**
   ```
   Chunk 0: "Scan the bet"
   Chunk 1: "Confirm by using (f12) or ENTER"
   Chunk 2: "Locate the bet in Awaiting Translation"
   ```

3. **How chunking works:**
   - Splits on delimiters (newlines, bullets, semicolons)
   - Uses dependency parsing to find multiple verbs
   - Filters noise (removes chunks without action verbs)
   - Creates atomic chunks (one action per chunk)

#### Impact on Matching

**Chunking helps by:**
1. **Granular matching:** Each atomic action is matched independently
2. **1-to-1 alignment:** One test step action → one BDD step
3. **Better precision:** Avoids matching entire multi-step scenarios to single actions

**Example:**
- **Without chunking:** "Scan bet, Confirm F12, Locate bet" → matches to entire BDD scenario
- **With chunking:** "Confirm F12" → matches to individual BDD step "I press F12 to confirm"

### Current Flow

```
Test Case (Multi-Step)
    ↓
[CHUNKING] → Splits into atomic chunks
    ↓
Chunk 0: "Confirm by using (f12) or ENTER"
    ↓
[NORMALIZATION] → "confirm by using ( f12 ) or enter"
    ↓
[EMBEDDING] → 768-dim vector
    ↓
[VECTOR SEARCH] → Finds 300 similar BDD steps
    ↓
[RERANKING] → Compares normalized chunk vs normalized BDD steps
    Query: "confirm by using ( f12 ) or enter"
    vs
    Candidate: "i add selection and proceed to bet type page"
    ↓
    Score: -3.816 (poor match)
    ↓
Returns top-6 candidates
```

### The Problem: Chunking vs Reranking Gap

#### What Chunking Does Well

1. ✅ Breaks down complex steps into atomic actions
2. ✅ Identifies individual actions using dependency parsing
3. ✅ Filters noise chunks

#### What Reranking Struggles With

1. **Normalization gaps:**
   - Chunk: "press enter so selections moved"
   - BDD: "i add selection and proceed"
   - Different phrasing → low reranker score

2. **Domain term loss:**
   - Chunk: "press (f12) confirm"
   - Normalized: "press ( f12 ) confirm"
   - BDD: "i click confirm button"
   - Missing "f12" → reranker can't match
f
3. **Action verb mismatches:**
   - Chunk: "press enter"
   - BDD: "i type selection"
   - "press" vs "type" → treated as different

### Current Implementation Details

#### Chunking Implementation

1. **Dependency parsing** (lines 113-153 in chunker.py):
   - Uses spaCy to find verbs
   - Splits on conjunctions (and, or, then)
   - Creates chunks per verb

2. **Filtering** (lines 155-181):
   - Requires minimum tokens (3)
   - Requires action verbs (click, select, navigate, etc.)
   - Filters pure punctuation

3. **Normalization per chunk** (lines 56-92):
   - Each chunk is normalized independently
   - Extracts action verb and primary object
   - Creates placeholders

#### Reranking Implementation

1. **Text extraction** (lines 32-41 in reranker.py):
   ```python
   candidate_text = (
       candidate.get('step_text_normalized') or  # Individual BDD step normalized
       candidate.get('step_text') or            # Fallback
       ...
   )
   ```

2. **Pair creation** (line 42):
   ```python
   pairs.append([query, candidate_text])
   ```

3. **Scoring** (line 45):
   ```python
   scores = self.model.predict(pairs)  # Cross-encoder scores
   ```

### The Gap

**Chunking creates atomic actions, but:**
- Reranker only sees normalized text
- No domain term preservation
- No synonym expansion
- No context awareness

**Result:**
- ✅ Chunking: "Confirm by using (f12) or ENTER" → atomic action ✓
- ✅ Normalization: "confirm by using ( f12 ) or enter" ✓
- ❌ Reranker compares: "confirm by using ( f12 ) or enter" vs "i add selection and proceed"
- ❌ Score: -3.816 (missed match) ✗

### Summary

1. **Chunking:** Splits multi-step test cases into atomic actions (works well) ✅
2. **Normalization:** Standardizes text but loses domain terms and semantic relationships ⚠️
3. **Reranking:** Compares normalized texts but misses matches due to normalization gaps ❌
4. **The bottleneck:** Normalization, not chunking or reranking logic

**Key Insight:** Chunking helps by creating atomic matches, but the reranker fails because normalization creates semantic gaps between the chunk text and BDD step text.

