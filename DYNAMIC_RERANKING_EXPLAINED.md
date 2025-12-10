# Dynamic Reranking: Detailed Explanation

## 📊 Current Statistics

From your latest run:
- **Total queries**: 1,130
- **Reranker USED**: 0 (0.0%)
- **Reranker SKIPPED**: 1,130 (100.0%)
- **Time saved**: ~113-170 seconds

**Skip reasons:**
- **99.8%** skipped due to "All top 5 above 90th percentile" (Condition 2)
- **0.2%** skipped due to "Cluster separation" (Condition 3)
- **0%** skipped due to "Top score dominance" (Condition 4) - caught by Condition 2 first

---

## 🔍 How to See Reranker Usage

Run the analysis script:
```bash
python analyze_reranker_usage.py
```

This shows:
- Total reranker usage vs skip rate
- Breakdown of skip reasons
- Per-test-case statistics
- Estimated time savings

---

## 🎯 Condition 3: Cluster Separation Explained

### What is a "Cluster"?

A **cluster** is a group of similar scores that are clearly separated from other scores. Think of it like this:

```
Visual Representation:

High Scores (Cluster)          Low Scores (Cluster)
     │                              │
     ▼                              ▼
[0.85, 0.82, 0.78, 0.75, 0.71]  [0.45, 0.42, 0.38, 0.35, ...]
     ▲                              ▲
     │                              │
  Top 5                        Rest of candidates
  (mean: 0.782)                (mean: 0.40)
  
  Gap: 0.782 - 0.40 = 0.382  ← This is the "separation"
```

### How Cluster Separation Works

**Formula:**
```python
top_mean = mean(scores[0:5])      # Average of top 5 scores
rest_mean = mean(scores[5:])      # Average of remaining scores
separation = top_mean - rest_mean # Gap between clusters

if separation > 0.10:  # Threshold from config
    SKIP RERANKER  # Top 5 form a distinct cluster
```

**Logic:**
- If the top 5 scores are **significantly higher** than the rest, they form a "cluster"
- This indicates the top 5 are clearly the best matches
- No need to rerank - the vector search already found the best candidates

### Example 1: Clear Cluster Separation ✅

**Query:** "Set stake to £5.00"

**Vector Search Results (100 candidates):**
```
Top 5 scores:    [0.89, 0.87, 0.85, 0.83, 0.81]
Remaining 95:    [0.65, 0.64, 0.63, 0.62, 0.61, ..., 0.45, 0.44, ...]

Calculation:
  top_mean = (0.89 + 0.87 + 0.85 + 0.83 + 0.81) / 5 = 0.85
  rest_mean = mean([0.65, 0.64, ..., 0.45]) ≈ 0.55
  separation = 0.85 - 0.55 = 0.30

Decision: 0.30 > 0.10 (threshold) → SKIP RERANKER ✅
Reason: "Cluster separation: 0.300 (top mean=0.850, rest mean=0.550)"
```

**Why this works:**
- Top 5 are all very similar (0.81-0.89 range)
- They're clearly separated from the rest (0.45-0.65 range)
- The gap (0.30) is large enough to indicate a distinct cluster
- Reranker won't change the ranking much - top 5 are already the best

### Example 2: No Clear Cluster ❌

**Query:** "Navigate to obscure menu"

**Vector Search Results (100 candidates):**
```
Top 5 scores:    [0.68, 0.67, 0.66, 0.65, 0.64]
Remaining 95:    [0.63, 0.62, 0.61, 0.60, 0.59, ..., 0.55, 0.54, ...]

Calculation:
  top_mean = (0.68 + 0.67 + 0.66 + 0.65 + 0.64) / 5 = 0.66
  rest_mean = mean([0.63, 0.62, ..., 0.55]) ≈ 0.60
  separation = 0.66 - 0.60 = 0.06

Decision: 0.06 < 0.10 (threshold) → USE RERANKER ❌
Reason: Scores too ambiguous, using reranker
```

**Why reranker is needed:**
- Top 5 scores (0.64-0.68) are very close to the rest (0.55-0.63)
- No clear separation - scores are spread out
- Reranker can help distinguish subtle differences

### Example 3: Real Case from Your Data

From your results, 2 queries skipped due to cluster separation:
```
"Cluster separation: 0.125 (top mean=0.854, rest mean=0.729)"
```

**What this means:**
- Top 5 average: 0.854 (very high similarity)
- Rest average: 0.729 (still decent, but lower)
- Gap: 0.125 (above 0.10 threshold)
- **Decision:** Skip reranker - top 5 are clearly the best cluster

---

## 👑 Condition 4: Top Score Dominance Explained

### What is "Top Score Dominance"?

This condition checks if:
1. The **absolute best match** (top score) is exceptionally high
2. **All top 5** are also very high
3. Together, they indicate strong confidence in the matches

**Formula:**
```python
p95 = percentile(all_scores, 95)  # 95th percentile threshold
p85 = percentile(all_scores, 85)  # 85th percentile threshold

if (all_scores[0] >= p95) and (all top 5 >= p85):
    SKIP RERANKER  # Top score is dominant, all top 5 are strong
```

**Logic:**
- If the #1 match is in the top 5% of all scores (very rare/high)
- AND all top 5 are in the top 15% of all scores (very good)
- Then we have a dominant best match with strong supporting matches
- No need to rerank - confidence is already high

### Example 1: Top Score Dominance ✅

**Query:** "Press F8 to navigate to Numbers table"

**Vector Search Results (100 candidates):**
```
All 100 scores: [0.92, 0.88, 0.86, 0.84, 0.82, 0.75, 0.74, 0.73, ..., 0.45, 0.44]

Percentile Calculation:
  p95 = 95th percentile = 0.88  (95% of scores are ≤ 0.88)
  p85 = 85th percentile = 0.80  (85% of scores are ≤ 0.80)

Top 5 scores:
  [0] = 0.92  → 0.92 >= 0.88 (p95) ✅
  [1] = 0.88  → 0.88 >= 0.80 (p85) ✅
  [2] = 0.86  → 0.86 >= 0.80 (p85) ✅
  [3] = 0.84  → 0.84 >= 0.80 (p85) ✅
  [4] = 0.82  → 0.82 >= 0.80 (p85) ✅

Decision: All conditions met → SKIP RERANKER ✅
Reason: "Top score dominant (top=0.920≥0.880, all top 5≥0.800)"
```

**Why this works:**
- Top score (0.92) is exceptional - only 5% of candidates score this high
- All top 5 (0.82-0.92) are in the top 15% - very strong matches
- This indicates a clear winner with strong alternatives
- Reranker won't change much - the ranking is already confident

### Example 2: No Dominance ❌

**Query:** "Click on generic button"

**Vector Search Results (100 candidates):**
```
All 100 scores: [0.72, 0.71, 0.70, 0.69, 0.68, 0.67, 0.66, 0.65, ..., 0.50, 0.49]

Percentile Calculation:
  p95 = 95th percentile = 0.70  (95% of scores are ≤ 0.70)
  p85 = 85th percentile = 0.68  (85% of scores are ≤ 0.68)

Top 5 scores:
  [0] = 0.72  → 0.72 >= 0.70 (p95) ✅
  [1] = 0.71  → 0.71 >= 0.68 (p85) ✅
  [2] = 0.70  → 0.70 >= 0.68 (p85) ✅
  [3] = 0.69  → 0.69 >= 0.68 (p85) ✅
  [4] = 0.68  → 0.68 >= 0.68 (p85) ✅ (borderline)

Decision: Top score (0.72) is NOT >= p95 (0.70) → USE RERANKER ❌
Reason: Top score is not dominant enough
```

**Why reranker is needed:**
- Top score (0.72) is good but not exceptional
- Scores are tightly packed (0.68-0.72) - not much separation
- Reranker can help distinguish subtle differences

### Example 3: Why Condition 4 Rarely Triggers

In your data, **0 queries** skipped due to Condition 4. Why?

**Reason:** Condition 2 (percentile rank) usually catches these cases first!

**Example:**
```
Query with high scores: [0.92, 0.88, 0.86, 0.84, 0.82, ...]

Condition 2 Check:
  p90 = 90th percentile = 0.80
  All top 5 >= 0.80? → YES ✅
  → SKIP RERANKER (Condition 2 triggers first)

Condition 4 Check:
  (Never reached - Condition 2 already skipped reranker)
```

**Why Condition 2 is checked first:**
- Condition 2 is simpler and faster to compute
- It catches most high-confidence cases
- Condition 4 is more specific (requires both top score AND all top 5 to be high)

---

## 🔄 How Clusters Are Formed

### Understanding Score Distribution

Clusters form naturally from the **distribution** of similarity scores. Here's how:

### Step 1: Vector Search Returns Scores

```
Query: "Set stake to £5.00"
→ Vector search compares query embedding to all BDD step embeddings
→ Returns 100 candidates with similarity scores
```

### Step 2: Scores Are Distributed

Scores typically form a **distribution** like this:

```
High Cluster (Top Matches)          Medium Cluster          Low Cluster
     │                                  │                       │
     ▼                                  ▼                       ▼
[0.90, 0.88, 0.86, 0.84, 0.82]  [0.70, 0.68, 0.66, ...]  [0.50, 0.48, ...]
     ▲                                  ▲                       ▲
  Top 5                            Middle candidates        Poor matches
  (mean: 0.86)                      (mean: 0.68)            (mean: 0.49)
```

### Step 3: Cluster Detection

The algorithm detects clusters by:

1. **Calculating means:**
   ```python
   top_mean = mean([0.90, 0.88, 0.86, 0.84, 0.82]) = 0.86
   rest_mean = mean([0.70, 0.68, ..., 0.50, ...]) = 0.62
   ```

2. **Measuring separation:**
   ```python
   separation = 0.86 - 0.62 = 0.24
   ```

3. **Comparing to threshold:**
   ```python
   if separation > 0.10:  # Config threshold
       # Top 5 form a distinct cluster
       SKIP RERANKER
   ```

### Visual Example: Cluster Formation

```
Score Distribution Visualization:

1.0 |                    ●
    |                   ● ●
0.9 |                  ● ● ●
    |                 ● ● ● ●
0.8 |                ● ● ● ● ●  ← Top 5 Cluster (mean: 0.86)
    |               ● ● ● ● ●
0.7 |              ● ● ● ● ● ●
    |             ● ● ● ● ● ● ●
0.6 |            ● ● ● ● ● ● ● ●
    |           ● ● ● ● ● ● ● ● ●
0.5 |          ● ● ● ● ● ● ● ● ● ●  ← Rest Cluster (mean: 0.62)
    |         ● ● ● ● ● ● ● ● ● ●
0.4 |        ● ● ● ● ● ● ● ● ● ● ●
    |       ● ● ● ● ● ● ● ● ● ● ●
0.3 |      ● ● ● ● ● ● ● ● ● ● ● ●
    |
    └─────────────────────────────────
     0    20   40   60   80   100
           Candidate Rank

Separation: 0.86 - 0.62 = 0.24 > 0.10 → CLUSTER DETECTED ✅
```

### When Clusters Don't Form

If scores are **uniformly distributed** (no clear clusters):

```
Score Distribution (No Clusters):

1.0 |
    |
0.9 |
    |
0.8 |  ●
    | ● ●
0.7 |● ● ●
    |● ● ● ●
0.6 |● ● ● ● ●
    |● ● ● ● ● ●
0.5 |● ● ● ● ● ● ●  ← Scores spread evenly
    |● ● ● ● ● ● ● ●
0.4 |● ● ● ● ● ● ● ● ●
    |● ● ● ● ● ● ● ● ●
0.3 |● ● ● ● ● ● ● ● ● ●
    |
    └─────────────────────────────────
     0    20   40   60   80   100
           Candidate Rank

Separation: 0.65 - 0.60 = 0.05 < 0.10 → NO CLUSTER ❌
→ USE RERANKER to distinguish subtle differences
```

---

## 📈 Summary: When Each Condition Triggers

### Condition 1: Too Few Candidates
- **When:** ≤ 5 candidates retrieved
- **Why:** Not enough to rerank
- **Example:** "Very unique query" → Only 3 matches found

### Condition 2: All Top 5 Above 90th Percentile
- **When:** All top 5 scores are in the top 10% of all scores
- **Why:** High confidence in top matches
- **Example:** Scores [0.85, 0.82, 0.78, 0.75, 0.71] all above 90th percentile (0.70)

### Condition 3: Cluster Separation
- **When:** Top 5 mean is significantly higher than rest mean
- **Why:** Top 5 form a distinct cluster of best matches
- **Example:** Top 5 mean (0.85) vs rest mean (0.60) = 0.25 separation

### Condition 4: Top Score Dominance
- **When:** Top score is exceptional (≥95th percentile) AND all top 5 are strong (≥85th percentile)
- **Why:** Clear winner with strong alternatives
- **Example:** Top score (0.92) ≥ p95 (0.88), all top 5 ≥ p85 (0.80)

### Condition 5: Percentile Gap
- **When:** Clear drop-off between 5th and 6th candidate
- **Why:** Top 5 are clearly better than the rest
- **Example:** 5th at 80th percentile, 6th at 65th percentile = 15 point gap

---

## 🎯 Key Takeaways

1. **Clusters form naturally** from score distributions - high scores group together
2. **Cluster detection** measures the gap between top 5 and the rest
3. **Top dominance** requires both exceptional top score AND strong top 5
4. **Conditions are checked in order** - simpler conditions catch most cases first
5. **Your data shows 100% skip rate** - vector search is finding high-quality matches consistently

