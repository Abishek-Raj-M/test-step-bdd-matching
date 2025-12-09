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
            
            # Step 4: Reranking (MANDATORY)
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
            
            # Step 5: Build top-K candidates list
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
                    # Full scenario context
                    "scenario_id": candidate_dict.get('scenario_id'),
                    "scenario_name": candidate_dict.get('scenario_name'),
                    "scenario_full_text": candidate_dict.get('scenario_full_text'),
                    "scenario_given_steps": candidate_dict.get('scenario_given_steps'),
                    "scenario_when_steps": candidate_dict.get('scenario_when_steps'),
                    "scenario_then_steps": candidate_dict.get('scenario_then_steps'),
                    "reranker_score": float(reranker_score) if reranker_score is not None else None,
                    "vector_similarity": float(candidate_vector_sim) if candidate_vector_sim is not None else None
                })
            
            # Step 6: Select top candidate (for display/usage tracking)
            top_candidate = reranked[0]
            top_reranker_score = top_candidate[1]
            top_candidate_dict = top_candidate[0]
            
            selected_candidate_id = top_candidate_dict.get('id')
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
            # This allows one test step to match multiple BDD steps
            has_good_match = any(
                score >= self.config.min_score_threshold 
                for _, score in reranked[:min(self.config.top_k_results, len(reranked))]
            )
            
            if has_good_match:
                final_action = "REUSED_TEMPLATE"
                # Increment usage count for top match (could increment all good matches if desired)
                if selected_candidate_id:
                    self.db.increment_individual_step_usage(selected_candidate_id)
            else:
                final_action = "NEW_BDD_REQUIRED"
            
            processing_time = (time.time() - start_time) * 1000
            
            return MatchResult(
                query_id=query_id,
                parent_testcase_id=parent_testcase_id,
                chunk_index=chunk_index,
                original_chunk=query_text,
                full_testcase_text=full_testcase_text,
                normalized_text=normalized.normalized_text,
                top_k_candidates=top_k_candidates,
                selected_candidate_id=selected_candidate_id,
                selected_template=selected_template,
                final_action=final_action,
                reranker_score=float(top_reranker_score) if top_reranker_score is not None else None,
                vector_similarity=float(vector_similarity) if vector_similarity is not None else None,
                processing_time_ms=processing_time,
                notes=""
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
