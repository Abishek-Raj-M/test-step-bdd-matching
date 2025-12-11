# What We Need: Future Improvements and Enhancements

## Overview

This document outlines the key areas for improvement and enhancement needed for the RAG-based test step to BDD matching system. These items represent the next phase of development to make the system more robust, flexible, and production-ready.

---

## 1. Determine Maximum BDD Steps per Test Step

### Objective
Find a number that loosely relates to the maximum number of BDD steps that one test step might have.

### Why This Matters
- Currently returns top 5 matches (`top_k_results: 5`)
- Need to understand the actual distribution of BDD steps per test step
- Helps determine optimal `top_k_results` configuration
- Important for understanding 1-to-many relationship patterns

### Tasks
1. **Analyze existing results** to find:
   - Maximum number of BDD steps matched per test step
   - Average number of BDD steps per test step
   - Distribution of match counts (1, 2, 3, 4, 5+ matches)
   - Cases where multiple BDD steps from same scenario are matched

2. **Review test case data** to understand:
   - How many BDD steps typically correspond to one manual test step
   - Whether 5 is sufficient or if we need more/less
   - Patterns in multi-step scenarios

3. **Update configuration** based on findings:
   - Adjust `top_k_results` if needed
   - Consider dynamic `top_k` based on scenario grouping

### Expected Outcome
- Data-driven decision on optimal `top_k_results` value
- Understanding of 1-to-many relationship patterns
- Better configuration for downstream AI processing

---

## 2. Canonical Mapping Update Mechanism

### Objective
Create a way to update canonical action mappings if required, without code changes.

### Current State
- Canonical mappings are hardcoded in `src/normalizer.py` (lines 48-55)
- Changes require code modification and redeployment
- No easy way to add new mappings or adjust existing ones

### Why This Matters
- Domain-specific actions may need custom mappings
- New action verbs may be discovered over time
- Different projects may need different canonicalization rules
- Need flexibility without code changes

### Proposed Solutions

#### Option A: Configuration File
- Move canonical mappings to `config.yaml`
- Load mappings at runtime
- Easy to update without code changes

#### Option B: Database Table
- Store mappings in database
- Admin interface to update mappings
- Version history and audit trail

#### Option C: Hybrid Approach
- Default mappings in config
- Override/extend via database
- Best of both worlds

### Tasks
1. **Design mapping structure** (JSON/YAML format)
2. **Implement loading mechanism** (config or database)
3. **Create update interface** (config file or admin UI)
4. **Add validation** to ensure mappings are valid
5. **Test backward compatibility** with existing mappings

### Expected Outcome
- Flexible canonical mapping system
- Easy updates without code changes
- Support for project-specific mappings

---

## 3. AI Solution Leeway Mechanism

### Objective
Instruct the AI solution to have a leeway mechanism instead of strictly using retrieved BDD steps. The AI should understand vector similarity or reranker scores and ask for human-in-the-loop intervention.

### Current Behavior
- System returns top matches with scores
- Downstream AI likely uses matches directly
- No mechanism for uncertainty handling

### Desired Behavior
- AI should evaluate confidence based on scores
- When confidence is low, request human intervention
- Human can either:
  - Choose from provided BDD options
  - Explicitly request new BDD creation
  - Provide feedback to improve matching

### Implementation Approach

#### 3.1 Confidence Thresholds
- **High Confidence**: Vector similarity > 0.75 AND reranker score > 0.5
  - AI can use match directly
  - No human intervention needed

- **Medium Confidence**: Vector similarity 0.65-0.75 OR reranker score 0.0-0.5
  - AI should present options to human
  - Show top 3-5 matches with scores
  - Human selects best match or requests new BDD

- **Low Confidence**: Vector similarity < 0.65 OR reranker score < 0.0
  - AI should flag for human review
  - Suggest creating new BDD
  - Show why match is uncertain (low scores, multiple weak matches)

#### 3.2 Human-in-the-Loop Interface
- **Display matches** with scores and context
- **Show confidence indicators** (high/medium/low)
- **Allow selection** from provided matches
- **Request new BDD** option
- **Feedback mechanism** to improve future matches

#### 3.3 AI Instructions
- Document how to interpret scores
- Provide decision tree for confidence levels
- Include examples of when to request human help
- Guidelines for presenting options to users

### Tasks
1. **Define confidence thresholds** based on score analysis
2. **Design human-in-the-loop interface** (UI or API)
3. **Create AI instruction documentation** for downstream systems
4. **Implement score interpretation logic**
5. **Build feedback mechanism** for continuous improvement
6. **Test with real scenarios** to validate thresholds

### Expected Outcome
- AI system that intelligently requests human help when uncertain
- Better user experience with confidence-aware matching
- Reduced false positives through human validation
- Continuous improvement through feedback

---

## 4. Score Threshold Calibration

### Objective
Fix the score threshold - it's a little lenient now but cannot argue with the results.

### Current State
- **Vector similarity threshold**: 0.65 (when skipping reranker)
- **Reranker score threshold**: 0.0 (when using reranker)
- **Results**: 97.5% match rate (excellent, but may be too lenient)

### Concerns
- Current thresholds may accept matches that are too loose
- 97.5% match rate is high, but quality vs quantity trade-off
- Need to balance match rate with match quality

### Analysis Needed
1. **Review false positives**:
   - Cases that matched but shouldn't have
   - Low-quality matches that passed threshold
   - User feedback on match quality

2. **Analyze score distributions**:
   - Distribution of accepted matches
   - Distribution of rejected matches
   - Gap between accepted and rejected

3. **Test different thresholds**:
   - 0.70, 0.75 for vector similarity
   - 0.1, 0.2 for reranker scores
   - Measure impact on match rate and quality

### Tasks
1. **Collect user feedback** on match quality
2. **Analyze false positives** in current results
3. **Test stricter thresholds** (0.70, 0.75)
4. **Measure trade-offs** (match rate vs quality)
5. **Calibrate thresholds** based on findings
6. **Document threshold rationale**

### Expected Outcome
- Optimized thresholds balancing match rate and quality
- Better match quality with acceptable match rate
- Clear documentation of threshold decisions

---

## 5. Reranker Testing and Validation

### Objective
Test reranker to see if it works - right now vector similarity is doing all the heavy lifting.

### Current State
- **100% reranker skip rate** in full dataset
- Dynamic reranking always skips reranker
- Vector similarity alone achieving 97.5% match rate
- Reranker may not be getting tested/used

### Concerns
- Reranker may not be working correctly
- We may be missing benefits of reranking
- Need to validate reranker is functioning properly
- May need to adjust dynamic reranking conditions

### Testing Plan

#### 5.1 Force Reranker Usage
- Temporarily disable dynamic reranking
- Force all queries through reranker
- Compare results with/without reranker
- Measure score improvements

#### 5.2 Reranker Score Analysis
- Analyze reranker score distributions
- Check if reranker scores align with vector similarity
- Identify cases where reranker improves ordering
- Find cases where reranker disagrees with vector search

#### 5.3 Dynamic Reranking Conditions Review
- Review skip conditions (may be too aggressive)
- Test with relaxed conditions
- Find optimal balance between speed and quality
- Consider hybrid approach (rerank top 10, not all 100)

#### 5.4 Reranker Model Validation
- Test reranker with known good/bad pairs
- Verify reranker can distinguish quality matches
- Check if reranker model is loaded correctly
- Validate reranker input formatting

### Tasks
1. **Disable dynamic reranking** temporarily for testing
2. **Run full dataset** with reranker enabled
3. **Compare results** (with vs without reranker)
4. **Analyze reranker score distributions**
5. **Test reranker on edge cases**
6. **Review dynamic reranking conditions**
7. **Optimize reranker usage** (when to use, when to skip)

### Expected Outcome
- Validated reranker functionality
- Understanding of reranker's impact on matching
- Optimized dynamic reranking strategy
- Better balance between speed and quality

---

## 6. Explicit Scenario Grouping

### Objective
Add explicit scenario grouping to match results to make it easier for downstream AI to understand which matches belong together.

### Current State
- Matches are returned as a flat list with `scenario_id` in each match
- All scenario context is available (`scenario_name`, `scenario_full_text`, `scenario_given_steps`, etc.)
- AI can manually group by `scenario_id` but must iterate through the list

### Why This Matters
When multiple matches come from the same scenario, they form a complete workflow. The AI should recognize:
- Which steps belong together
- Whether a full scenario matches or just individual steps
- Match completeness (all steps vs partial)

### Proposed Solution
Add explicit scenario grouping structure to results:

```json
{
  "top_k_candidates": [...],  // Keep flat list for backward compatibility
  "scenario_groups": {
    "724": {
      "scenario_name": "OTC- Ante Post Option",
      "matches": [candidate1, candidate2],
      "completeness": "partial",  // or "complete"
      "coverage": "2 of 4 steps"
    }
  }
}
```

### Key Features
- **Scenario Groups**: Organized by `scenario_id` with all matches from that scenario
- **Completeness Indicator**: "complete" if all scenario steps matched, "partial" otherwise
- **Coverage Percentage**: Shows how many steps from scenario were matched
- **Backward Compatible**: Flat list still available

### Tasks
1. Analyze match results to identify scenario grouping patterns
2. Design grouping structure and completeness calculation
3. Implement grouping logic in pipeline
4. Add completeness and coverage indicators
5. Update result JSON structure
6. Test with downstream AI to validate improvements

### Expected Outcome
- Easier downstream processing (no manual grouping needed)
- Better AI decision-making (awareness of scenario completeness)
- More reliable matching (explicit structure reduces errors)
- Improved user experience (clearer match relationships)

---

## 7. Model Upgrade Consideration

### Objective
Evaluate if a better model is needed for embeddings or reranking.

### Current Models
- **Embedding**: `BAAI/bge-m3` (1024 dimensions)
- **Reranker**: `BAAI/bge-reranker-v2-m3`

### When to Consider Upgrade
- If match quality is insufficient
- If reranker scores are not meaningful
- If domain-specific understanding is poor
- If multilingual support is needed
- If newer models show significant improvements

### Evaluation Criteria

#### 6.1 Embedding Model
- **Semantic understanding**: Better domain term handling
- **Multilingual support**: If needed for project
- **Dimension size**: Balance between quality and speed
- **Model size**: Memory and inference time
- **Benchmark performance**: On similar tasks

#### 6.2 Reranker Model
- **Cross-encoder performance**: Better pair scoring
- **Alignment with embedding**: Should match embedding model
- **Speed**: Inference time impact
- **Score distribution**: Meaningful score ranges

### Potential Alternatives
- **Embedding**: `BAAI/bge-large-en-v1.5`, `sentence-transformers/all-MiniLM-L6-v2`
- **Reranker**: `BAAI/bge-reranker-large-v2`, `cross-encoder/ms-marco-MiniLM-L-12-v2`

### Tasks
1. **Benchmark current models** on test dataset
2. **Research newer models** and their improvements
3. **Test alternative models** on sample data
4. **Compare performance** (quality, speed, memory)
5. **Evaluate cost/benefit** of upgrading
6. **Make recommendation** based on findings

### Expected Outcome
- Evaluation of whether model upgrade is needed
- Recommendation on best models for the use case
- Understanding of trade-offs (quality vs speed vs cost)

---

## Implementation Priority

### High Priority
1. **Score Threshold Calibration** - Affects match quality directly
2. **Reranker Testing** - Need to validate core functionality
3. **AI Leeway Mechanism** - Critical for production use

### Medium Priority
4. **Maximum BDD Steps Analysis** - Optimize configuration
5. **Canonical Mapping Updates** - Improve flexibility
6. **Explicit Scenario Grouping** - Improve downstream AI processing

### Low Priority
7. **Model Upgrade** - Only if current models insufficient

---

## Success Metrics

### For Each Improvement
- **Maximum BDD Steps**: Data-driven `top_k_results` value
- **Canonical Mapping**: Easy updates without code changes
- **AI Leeway**: Reduced false positives, better user experience
- **Score Thresholds**: Optimal balance of match rate and quality
- **Reranker Validation**: Confirmed functionality and optimal usage
- **Scenario Grouping**: Explicit structure for easier downstream processing
- **Model Evaluation**: Clear recommendation on model upgrade

### Overall System
- **Match Quality**: User satisfaction with matches
- **False Positive Rate**: Reduced incorrect matches
- **Human Intervention Rate**: Appropriate use of human-in-the-loop
- **System Performance**: Maintained speed with improved quality

---

## Next Steps

1. **Prioritize improvements** based on business needs
2. **Create detailed implementation plans** for each item
3. **Allocate resources** for development and testing
4. **Set timelines** for each improvement
5. **Begin with high-priority items** (thresholds, reranker testing)

---

**Last Updated:** 2025-12-10  
**Status:** Planning Phase - Awaiting Prioritization and Implementation

