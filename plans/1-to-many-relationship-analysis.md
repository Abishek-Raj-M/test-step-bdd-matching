# 1-to-Many Relationship Analysis: Test Step to BDD Steps

## Current State: 1-to-Many Relationship Support

### What We Have ✅

1. **Multiple Matches Per Test Step**
   - `top_k_results: 5` returns up to 5 matches per query
   - Each match is in `top_k_candidates` with scores

2. **Scenario Grouping Information**
   - Each candidate includes:
     - `scenario_id`: Links individual steps to their parent scenario
     - `scenario_name`: Name of the scenario
     - `scenario_full_text`: Full scenario text
     - `scenario_given_steps`, `scenario_when_steps`, `scenario_then_steps`: Grouped steps

3. **Individual Step Details**
   - `individual_step_id`: Unique ID for each step
   - `step_type`: Given/When/Then
   - `step_index`: Order within scenario
   - `step_text`: The actual step text

### What an AI Solution Can Figure Out

#### ✅ 1. 1-to-Many Relationship
- **Yes**: Multiple candidates in `top_k_candidates` indicate multiple matches
- **Yes**: Scores show relative confidence

#### ✅ 2. Which Steps Belong to Same Scenario
- **Yes**: Candidates with same `scenario_id` are from same scenario
- **Yes**: `scenario_name` and `scenario_full_text` provide context

#### ✅ 3. Step Ordering Within Scenario
- **Yes**: `step_index` shows order
- **Yes**: `step_type` (Given/When/Then) shows structure

### What Might Be Unclear

#### ⚠️ 1. Scenario Grouping
- Candidates are NOT explicitly grouped by scenario
- AI would need to group by `scenario_id` itself
- Example: If 3 candidates have `scenario_id: 621`, they belong together

#### ⚠️ 2. Complete Scenario Sets
- We return individual steps, not full scenario sets
- AI would need to infer: "These 3 steps form one complete scenario"

#### ⚠️ 3. Multiple Scenarios
- If one test step matches steps from 2 different scenarios, they appear as separate candidates
- AI can identify this via different `scenario_id` values

### Example Output Structure

```json
{
  "query_id": "C60092679_chunk_0",
  "top_k_candidates": [
    {
      "individual_step_id": 10806,
      "scenario_id": 621,  // ← Same scenario
      "step_index": 3,
      "step_type": "When",
      "step_text": "I set stake '100' for the bet"
    },
    {
      "individual_step_id": 10399,
      "scenario_id": 608,  // ← Different scenario
      "step_index": 17,
      "step_type": "When",
      "step_text": "I set stake '1.00' for the bet"
    }
  ]
}
```

### Can an AI Figure It Out?

**Yes, but with some processing:**

#### 1. Grouping by Scenario
```python
# AI can do this:
scenarios = {}
for candidate in top_k_candidates:
    scenario_id = candidate['scenario_id']
    if scenario_id not in scenarios:
        scenarios[scenario_id] = []
    scenarios[scenario_id].append(candidate)
```

#### 2. Identifying Complete Sets
- AI can check if all steps from a scenario are present
- AI can use `scenario_full_text` to see the complete scenario

#### 3. Understanding Relationships
- AI can see: "Test step X matches scenario 621 (steps 3, 4, 5)"
- AI can see: "Test step X also matches scenario 608 (step 17)"

### What Could Be Improved

#### 1. Explicit Scenario Grouping
- Group candidates by `scenario_id` in the output
- Add a `scenario_groups` field showing which candidates belong together

#### 2. Scenario Completeness Indicator
- Mark if all steps from a scenario are matched
- Indicate partial vs complete scenario matches

#### 3. Relationship Metadata
- Add field like `match_type: "single_step" | "partial_scenario" | "complete_scenario"`
- Add `related_steps` to show other steps in same scenario

### Current Answer

**Yes, an AI solution CAN figure it out**, but it requires:
- Grouping candidates by `scenario_id`
- Inferring relationships from metadata
- Understanding scenario structure from `scenario_full_text`

**The data is there**, it just needs to be processed and grouped.

### Recommendation

The current structure is **sufficient** for an AI to:
1. ✅ Identify 1-to-many relationships
2. ✅ Group steps by scenario
3. ✅ Understand which steps belong together

However, adding **explicit scenario grouping** would make it:
- **Easier** for AI to process
- **More reliable** (less inference needed)
- **Clearer** for human review

The current approach requires AI to do the grouping, which is **feasible but adds complexity**.

---

## Summary

**Question:** Can an AI solution figure out the 1-to-many relationship and uniquely identify which set of feature steps correspond to which test step?

**Answer:** **Yes**, with the current structure, but it requires:
1. Grouping candidates by `scenario_id`
2. Using `scenario_full_text` to understand complete scenarios
3. Processing the metadata to infer relationships

**Improvement Opportunity:** Add explicit scenario grouping to make it easier and more reliable for downstream AI processing.

