"""Main pipeline for test step to BDD matching."""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import time


@dataclass
class MatchResult:
    """Result of matching a query to BDD step."""
    query_id: str
    parent_testcase_id: str
    chunk_index: int
    original_chunk: str
    full_testcase_text: str  # Original full test case for AI context
    normalized_text: str
    top_k_candidates: List[Dict[str, Any]]  # Top-K matches with scores
    selected_candidate_id: Optional[int]
    selected_template: str
    final_action: str  # REUSED_TEMPLATE or NEW_BDD_REQUIRED
    reranker_score: Optional[float]  # Score of top match
    vector_similarity: Optional[float]  # Vector similarity of top match
    processing_time_ms: float
    notes: str


class MatchingPipeline:
    """Main pipeline for matching test steps to BDD steps."""
    
    def __init__(self, config, database, normalizer, chunker, embedder, retrieval, reranker, 
                 placeholder_mapper, fallback_chain):
        self.config = config
        self.db = database
        self.normalizer = normalizer
        self.chunker = chunker
        self.embedder = embedder
        self.retrieval = retrieval
        self.reranker = reranker
        self.placeholder_mapper = placeholder_mapper
        self.fallback_chain = fallback_chain
    
    def _should_skip_reranker(self, candidates: List[Tuple[int, float, Dict[str, Any]]]) -> Tuple[bool, str]:
        """
        Determine if reranker should be skipped based on percentile-based analysis.
        
        Args:
            candidates: List of (candidate_id, similarity_score, candidate_dict) tuples
        
        Returns:
            Tuple of (should_skip: bool, reason: str)
        """
        if not self.config.dynamic_reranking.enabled:
            return False, "Dynamic reranking disabled"
        
        target_top_k = self.config.dynamic_reranking.target_top_k
        
        # Condition 1: Too few candidates - skip reranker
        if len(candidates) <= target_top_k:
            return True, f"Only {len(candidates)} candidates (≤{target_top_k}), skipping reranker"
        
        all_scores = [c[1] for c in candidates]  # Extract all similarity scores
        top_k_scores = all_scores[:target_top_k]  # Top 5 scores
        
        # Condition 2: Percentile rank check - all top 5 above Xth percentile
        p_threshold = np.percentile(all_scores, self.config.dynamic_reranking.min_percentile_rank)
        if all(score >= p_threshold for score in top_k_scores):
            return True, f"All top {target_top_k} above {self.config.dynamic_reranking.min_percentile_rank}th percentile ({p_threshold:.3f})"
        
        # Condition 3: Percentile gap between 5th and 6th
        def get_percentile_rank(score: float, all_scores: List[float]) -> float:
            """Calculate percentile rank (0-100) for a score."""
            return (sum(1 for s in all_scores if s <= score) / len(all_scores)) * 100
        
        if len(all_scores) > target_top_k:
            p5_rank = get_percentile_rank(all_scores[target_top_k - 1], all_scores)
            p6_rank = get_percentile_rank(all_scores[target_top_k], all_scores)
            gap = p5_rank - p6_rank
            if gap >= self.config.dynamic_reranking.percentile_gap_threshold:
                return True, f"Percentile gap: {gap:.1f} points (5th={p5_rank:.1f}th, 6th={p6_rank:.1f}th)"
        
        # Condition 4: Cluster separation
        top_mean = np.mean(top_k_scores)
        rest_scores = all_scores[target_top_k:]
        if rest_scores:
            rest_mean = np.mean(rest_scores)
            separation = top_mean - rest_mean
            if separation > self.config.dynamic_reranking.cluster_separation:
                return True, f"Cluster separation: {separation:.3f} (top mean={top_mean:.3f}, rest mean={rest_mean:.3f})"
        
        # Condition 5: Top dominance
        p95 = np.percentile(all_scores, self.config.dynamic_reranking.top_percentile_threshold)
        p85 = np.percentile(all_scores, self.config.dynamic_reranking.top_k_min_percentile)
        if all_scores[0] >= p95 and all(score >= p85 for score in top_k_scores):
            return True, f"Top score dominant (top={all_scores[0]:.3f}≥{p95:.3f}, all top {target_top_k}≥{p85:.3f})"
        
        return False, "Scores too ambiguous, using reranker"
    
    def match(self, query_text: str, query_id: str, parent_testcase_id: str, 
             chunk_index: int, full_testcase_text: str,
             previous_steps: Optional[List[str]] = None) -> MatchResult:
        """
        Match a query test step to BDD step.
        
        Args:
            query_text: Original query text (single atomic step)
            query_id: Unique query identifier
            parent_testcase_id: Parent test case identifier
            chunk_index: Index of chunk in original test case
            full_testcase_text: Full original test case for context
            previous_steps: Previous steps from same test case (for context)
        
        Returns:
            MatchResult with top-K matches and scores
        """
        start_time = time.time()
        
        try:
            # Step 1: Normalize query
            normalized = self.normalizer.normalize(query_text)
            
            # Step 2: Embed query
            query_embedding = self.embedder.embed(normalized.normalized_text)
            
            # Step 3: Vector ANN Search
            candidates = self.retrieval.retrieve(
                query_embedding,
                normalized.normalized_text,
                limit=self.config.retrieval.prefilter_limit,
                ef_search=self.config.retrieval.ef_search
            )
            
            if not candidates:
                # No candidates found
                processing_time = (time.time() - start_time) * 1000
                return MatchResult(
                    query_id=query_id,
                    parent_testcase_id=parent_testcase_id,
                    chunk_index=chunk_index,
                    original_chunk=query_text,
                    full_testcase_text=full_testcase_text,
                    normalized_text=normalized.normalized_text,
                    top_k_candidates=[],
                    selected_candidate_id=None,
                    selected_template="",
                    final_action="NEW_BDD_REQUIRED",
                    reranker_score=None,
                    vector_similarity=None,
                    processing_time_ms=processing_time,
                    notes="No candidates found in vector search"
                )
            
            vector_similarity = candidates[0][1]
            
            # Step 4: Dynamic Reranking Decision (Percentile-Based)
            should_skip, skip_reason = self._should_skip_reranker(candidates)
            
            if should_skip:
                # Skip reranker - use vector search results directly
                target_top_k = self.config.dynamic_reranking.target_top_k
                top_k = min(target_top_k, len(candidates))
                
                # Build top-K candidates from vector search results
                top_k_candidates = []
                for c_id, v_sim, c_dict in candidates[:top_k]:
                    top_k_candidates.append({
                        "individual_step_id": c_id,
                        "step_type": c_dict.get('step_type'),
                        "step_text": c_dict.get('step_text'),
                        "step_index": c_dict.get('step_index'),
                        "scenario_id": c_dict.get('scenario_id'),
                        "scenario_name": c_dict.get('scenario_name'),
                        "scenario_full_text": c_dict.get('scenario_full_text'),
                        "scenario_given_steps": c_dict.get('scenario_given_steps'),
                        "scenario_when_steps": c_dict.get('scenario_when_steps'),
                        "scenario_then_steps": c_dict.get('scenario_then_steps'),
                        "reranker_score": None,  # No reranker score
                        "vector_similarity": float(v_sim)
                    })
                
                # Select top candidate
                top_candidate_id = candidates[0][0]
                top_candidate_dict = candidates[0][2]
                top_reranker_score = None
                top_vector_sim = candidates[0][1]
                
            else:
                # Use reranker
                candidate_dicts = [c[2] for c in candidates[:self.config.reranker.top_k]]
                reranked = self.reranker.rerank(normalized, candidate_dicts, 
                                               top_k=self.config.reranker.top_k)
                
                if not reranked:
                    processing_time = (time.time() - start_time) * 1000
                    return MatchResult(
                        query_id=query_id,
                        parent_testcase_id=parent_testcase_id,
                        chunk_index=chunk_index,
                        original_chunk=query_text,
                        full_testcase_text=full_testcase_text,
                        normalized_text=normalized.normalized_text,
                        top_k_candidates=[],
                        selected_candidate_id=None,
                        selected_template="",
                        final_action="NEW_BDD_REQUIRED",
                        reranker_score=None,
                        vector_similarity=vector_similarity,
                        processing_time_ms=processing_time,
                        notes="Reranking returned no results"
                    )
                
                # Build top-K candidates list from reranked results
                top_k = min(self.config.top_k_results, len(reranked))
                top_k_candidates = []
                
                for candidate_dict, reranker_score in reranked[:top_k]:
                    # Get vector similarity for this candidate
                    candidate_id = candidate_dict.get('id')
                    candidate_vector_sim = None
                    for c_id, v_sim, c_dict in candidates:
                        if c_dict.get('id') == candidate_id:
                            candidate_vector_sim = v_sim
                            break
                    
                    top_k_candidates.append({
                        "individual_step_id": candidate_id,
                        "step_type": candidate_dict.get('step_type'),
                        "step_text": candidate_dict.get('step_text'),
                        "step_index": candidate_dict.get('step_index'),
                        "scenario_id": candidate_dict.get('scenario_id'),
                        "scenario_name": candidate_dict.get('scenario_name'),
                        "scenario_full_text": candidate_dict.get('scenario_full_text'),
                        "scenario_given_steps": candidate_dict.get('scenario_given_steps'),
                        "scenario_when_steps": candidate_dict.get('scenario_when_steps'),
                        "scenario_then_steps": candidate_dict.get('scenario_then_steps'),
                        "reranker_score": float(reranker_score) if reranker_score is not None else None,
                        "vector_similarity": float(candidate_vector_sim) if candidate_vector_sim is not None else None
                    })
                
                # Select top candidate
                top_candidate = reranked[0]
                top_reranker_score = top_candidate[1]
                top_candidate_dict = top_candidate[0]
                top_vector_sim = vector_similarity
            
            # Step 5: Select top candidate (for display/usage tracking)
            top_candidate_id = top_candidate_dict.get('id')
            
            # Display: step_type + step_text, with scenario context
            step_type = top_candidate_dict.get('step_type', '')
            step_text = top_candidate_dict.get('step_text', '')
            scenario_name = top_candidate_dict.get('scenario_name', '')
            
            if step_type and step_text:
                selected_template = f"{step_type}: {step_text}"
            elif scenario_name:
                selected_template = scenario_name
            else:
                selected_template = ""
            
            # Determine final action: 1-to-many matching
            # If ANY of the top-K matches is >= threshold, mark as REUSED_TEMPLATE
            if should_skip:
                # When skipping reranker, use vector similarity threshold
                # Since reranker can accept scores as low as -2.0, we need a more lenient
                # vector threshold. Vector similarity of 0.65+ typically corresponds to
                # reranker scores > -1.0, which are acceptable matches.
                # Using 0.65 as threshold (more lenient than 0.7) to match reranker behavior
                vector_threshold = 0.65  # Lenient threshold to match reranker acceptance
                has_good_match = any(
                    cand.get('vector_similarity', 0) >= vector_threshold
                    for cand in top_k_candidates
                )
            else:
                # When using reranker, use reranker score threshold
                has_good_match = any(
                    cand.get('reranker_score', -999) >= self.config.min_score_threshold
                    for cand in top_k_candidates
                )
            
            if has_good_match:
                final_action = "REUSED_TEMPLATE"
                # Increment usage count for top match
                if top_candidate_id:
                    self.db.increment_individual_step_usage(top_candidate_id)
            else:
                final_action = "NEW_BDD_REQUIRED"
            
            processing_time = (time.time() - start_time) * 1000
            
            # Build notes with skip reason if applicable
            notes = skip_reason if should_skip else ""
            
            return MatchResult(
                query_id=query_id,
                parent_testcase_id=parent_testcase_id,
                chunk_index=chunk_index,
                original_chunk=query_text,
                full_testcase_text=full_testcase_text,
                normalized_text=normalized.normalized_text,
                top_k_candidates=top_k_candidates,
                selected_candidate_id=top_candidate_id,
                selected_template=selected_template,
                final_action=final_action,
                reranker_score=float(top_reranker_score) if top_reranker_score is not None else None,
                vector_similarity=float(top_vector_sim) if top_vector_sim is not None else None,
                processing_time_ms=processing_time,
                notes=notes
            )
        
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return MatchResult(
                query_id=query_id,
                parent_testcase_id=parent_testcase_id,
                chunk_index=chunk_index,
                original_chunk=query_text,
                full_testcase_text=full_testcase_text,
                normalized_text="",
                top_k_candidates=[],
                selected_candidate_id=None,
                selected_template="",
                final_action="NEW_BDD_REQUIRED",
                reranker_score=None,
                vector_similarity=None,
                processing_time_ms=processing_time,
                notes=f"Error: {str(e)}"
            )
