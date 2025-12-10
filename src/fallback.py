"""Fallback chain module for alternative retrieval strategies."""
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FallbackResult:
    """Result from fallback chain."""
    success: bool
    candidates: List[Tuple[int, float, Dict[str, Any]]]
    fallback_used: str
    confidence_label: str


class FallbackChain:
    """Implements fallback strategies when primary retrieval fails."""
    
    def __init__(self, database, retrieval, reranker, normalizer, embedder, config):
        self.db = database
        self.retrieval = retrieval
        self.reranker = reranker
        self.normalizer = normalizer
        self.embedder = embedder
        self.config = config
    
    def execute_fallbacks(self, query_text: str, query_normalized: str, query_embedding: np.ndarray,
                         top_reranker_score: float, previous_steps: Optional[List[str]] = None) -> FallbackResult:
        """
        Execute fallback chain until success or all exhausted.
        
        Args:
            query_text: Original query text
            query_normalized: Normalized query text
            query_embedding: Query embedding
            top_reranker_score: Best reranker score from primary retrieval
            previous_steps: Previous steps from same test case (for context expansion)
        
        Returns:
            FallbackResult with success status and candidates
        """
        # Fallback 1: Relaxed ANN Search
        if top_reranker_score < self.config.thresholds.med_conf:
            result = self._relaxed_search(query_text, query_normalized, query_embedding)
            if result.success:
                return result
        
        # Fallback 2: Context Window Expansion
        if self.config.fallbacks.enable_context_expansion and previous_steps:
            result = self._context_expansion(query_text, query_normalized, previous_steps)
            if result.success:
                return result
        
        # Fallback 3: Lexical Search
        if self.config.fallbacks.enable_lexical_search:
            result = self._lexical_search(query_text, query_normalized)
            if result.success:
                return result
        
        # Fallback 4: Cluster Aggregation (Weak Matches)
        result = self._cluster_aggregation_weak(query_text, query_normalized, query_embedding)
        if result.success:
            return result
        
        # Fallback 5: Rule-Based Template Synthesis
        if self.config.fallbacks.enable_rule_synthesis:
            result = self._rule_synthesis(query_text, query_normalized)
            if result.success:
                return result
        
        # Fallback 6: LLM Synthesis (if enabled)
        if self.config.fallbacks.enable_llm_synthesis:
            result = self._llm_synthesis(query_text, query_normalized)
            if result.success:
                return result
        
        # Final: NEW_BDD_REQUIRED
        return FallbackResult(
            success=False,
            candidates=[],
            fallback_used="new_bdd_required",
            confidence_label="NO_MATCH"
        )
    
    def _relaxed_search(self, query_text: str, query_normalized: str, 
                       query_embedding: np.ndarray) -> FallbackResult:
        """Fallback 1: Relaxed ANN search with increased limits."""
        candidates = self.retrieval.retrieve(
            query_embedding,
            query_text,
            limit=self.config.retrieval.relaxed_limit,
            ef_search=self.config.retrieval.ef_relaxed
        )
        
        if not candidates:
            return FallbackResult(False, [], "relaxed_search", "NO_MATCH")
        
        # Rerank candidates
        candidate_dicts = [c[2] for c in candidates]
        reranked = self.reranker.rerank(query_normalized, candidate_dicts, top_k=self.config.reranker.top_k)
        
        if reranked and reranked[0][1] >= self.config.thresholds.med_conf:
            # Convert reranked results to proper format
            formatted_candidates = []
            for candidate_dict, score in reranked:
                candidate_id = candidate_dict.get('id') if isinstance(candidate_dict, dict) else None
                formatted_candidates.append((candidate_id, score, candidate_dict))
            
            return FallbackResult(
                True,
                formatted_candidates,
                "relaxed_search",
                "MED_CONF" if reranked[0][1] >= self.config.thresholds.med_conf else "LOW_CONF"
            )
        
        return FallbackResult(False, [], "relaxed_search", "NO_MATCH")
    
    def _context_expansion(self, query_text: str, query_normalized: str, 
                          previous_steps: List[str]) -> FallbackResult:
        """Fallback 2: Context window expansion."""
        # Combine current query with previous steps
        context_text = " ".join(previous_steps) + " " + query_text
        context_normalized = self.normalizer.normalize(context_text)
        context_embedding = self.embedder.embed(context_normalized.normalized_text)
        
        # Retrieve with expanded context
        candidates = self.retrieval.retrieve(context_embedding, context_text)
        
        if not candidates:
            return FallbackResult(False, [], "context_expansion", "NO_MATCH")
        
        # Rerank
        candidate_dicts = [c[2] for c in candidates]
        reranked = self.reranker.rerank(context_normalized.normalized_text, candidate_dicts, 
                                       top_k=self.config.reranker.top_k)
        
        if reranked and reranked[0][1] >= self.config.thresholds.med_conf:
            formatted_candidates = []
            for candidate_dict, score in reranked:
                candidate_id = candidate_dict.get('id') if isinstance(candidate_dict, dict) else None
                formatted_candidates.append((candidate_id, score, candidate_dict))
            
            return FallbackResult(
                True,
                formatted_candidates,
                "context_expansion",
                "MED_CONF" if reranked[0][1] >= self.config.thresholds.med_conf else "LOW_CONF"
            )
        
        return FallbackResult(False, [], "context_expansion", "NO_MATCH")
    
    def _lexical_search(self, query_text: str, query_normalized: str) -> FallbackResult:
        """Fallback 3: Lexical search using tsvector."""
        candidates = self.db.lexical_search(query_normalized, limit=self.config.retrieval.prefilter_limit)
        
        if not candidates:
            return FallbackResult(False, [], "lexical_search", "NO_MATCH")
        
        # Rerank lexical candidates
        candidate_dicts = [c[2] for c in candidates]
        reranked = self.reranker.rerank(query_normalized, candidate_dicts, top_k=self.config.reranker.top_k)
        
        if reranked and reranked[0][1] >= self.config.thresholds.med_conf:
            formatted_candidates = []
            for candidate_dict, score in reranked:
                candidate_id = candidate_dict.get('id') if isinstance(candidate_dict, dict) else None
                formatted_candidates.append((candidate_id, score, candidate_dict))
            
            return FallbackResult(
                True,
                formatted_candidates,
                "lexical_search",
                "MED_CONF" if reranked[0][1] >= self.config.thresholds.med_conf else "LOW_CONF"
            )
        
        return FallbackResult(False, [], "lexical_search", "NO_MATCH")
    
    def _cluster_aggregation_weak(self, query_text: str, query_normalized: str,
                                  query_embedding: np.ndarray) -> FallbackResult:
        """Fallback 4: Cluster aggregation with weak matches."""
        # Get candidates with relaxed search
        candidates = self.retrieval.retrieve(
            query_embedding,
            query_text,
            limit=self.config.retrieval.relaxed_limit
        )
        
        if not candidates:
            return FallbackResult(False, [], "cluster_aggregation", "NO_MATCH")
        
        # Group by cluster
        cluster_candidates = {}
        for candidate_id, similarity, candidate_dict in candidates:
            cluster_id = candidate_dict.get('cluster_id')
            if cluster_id:
                if cluster_id not in cluster_candidates:
                    cluster_candidates[cluster_id] = []
                cluster_candidates[cluster_id].append((candidate_id, similarity, candidate_dict))
        
        # Find clusters with > 3 weak matches
        for cluster_id, cluster_cands in cluster_candidates.items():
            if len(cluster_cands) > 3:
                # Use cluster's canonical template
                best_candidate = max(cluster_cands, key=lambda x: x[1])
                return FallbackResult(
                    True,
                    [best_candidate],
                    "cluster_aggregation",
                    "LOW_CONF"
                )
        
        return FallbackResult(False, [], "cluster_aggregation", "NO_MATCH")
    
    def _rule_synthesis(self, query_text: str, query_normalized: str) -> FallbackResult:
        """Fallback 5: Rule-based template synthesis."""
        normalized = self.normalizer.normalize(query_text)
        
        if not normalized.action_verb or not normalized.primary_object:
            return FallbackResult(False, [], "rule_synthesis", "NO_MATCH")
        
        # Extract placeholder types
        placeholder_types = [ph.type for ph in normalized.placeholders]
        
        # Generate template
        if placeholder_types:
            template = f"{normalized.action_verb} the {normalized.primary_object} {' '.join(f'<{pt}>' for pt in placeholder_types)}"
        else:
            template = f"{normalized.action_verb} the {normalized.primary_object}"
        
        # Create synthetic candidate
        synthetic_candidate = {
            'id': None,
            'canonical_template': template,
            'normalized_text': normalized.normalized_text,
            'cluster_id': None,
            'usage_count': 0,
            'synthesized': True
        }
        
        return FallbackResult(
            True,
            [(None, 0.5, synthetic_candidate)],  # Low score for synthesized
            "rule_synthesis",
            "LOW_CONF"
        )
    
    def _llm_synthesis(self, query_text: str, query_normalized: str) -> FallbackResult:
        """Fallback 6: LLM-based template synthesis (placeholder)."""
        # This would use an LLM API to generate BDD template
        # For now, return failure as it's disabled by default
        return FallbackResult(False, [], "llm_synthesis", "NO_MATCH")

