"""Reranking module using cross-encoder models."""
import numpy as np
from typing import List, Tuple, Dict, Any, Optional, Union
from sentence_transformers import CrossEncoder
from src.normalizer import NormalizedResult, Normalizer


class Reranker:
    """Reranks candidates using cross-encoder models."""
    
    def __init__(self, model_name: str, normalizer: Optional[Normalizer] = None):
        self.model_name = model_name
        self.model = CrossEncoder(model_name)
        self.normalizer = normalizer
    
    def rerank(self, query: Union[str, NormalizedResult], candidates: List[Dict[str, Any]], top_k: Optional[int] = None) -> List[Tuple[Dict[str, Any], float]]:
        """
        Rerank candidates based on query.
        
        Args:
            query: Query text
            candidates: List of candidate dicts with at least 'normalized_text' or 'canonical_template'
            top_k: Number of top candidates to return (None = all)
        
        Returns:
            List of (candidate, score) tuples sorted by score descending
        """
        if not candidates:
            return []
        
        # Prepare pairs for cross-encoder
        pairs = []
        query_text = self._format_query_text(query)
        for candidate in candidates:
            candidate_text = self._format_candidate_text(candidate)
            pairs.append([query_text, candidate_text])
        
        # Get scores from cross-encoder
        scores = self.model.predict(pairs)
        
        # Combine candidates with scores
        scored_candidates = list(zip(candidates, scores))
        
        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k if specified
        if top_k:
            return scored_candidates[:top_k]
        
        return scored_candidates
    
    def rerank_batch(self, queries: List[str], candidates_list: List[List[Dict[str, Any]]], top_k: Optional[int] = None) -> List[List[Tuple[Dict[str, Any], float]]]:
        """Rerank multiple queries in batch."""
        results = []
        for query, candidates in zip(queries, candidates_list):
            results.append(self.rerank(query, candidates, top_k))
        return results

    def _format_query_text(self, query: Union[str, NormalizedResult]) -> str:
        """Format query text with structured cues."""
        if isinstance(query, NormalizedResult):
            parts = []
            if query.action_canonical:
                parts.append(f"Action: {query.action_canonical}")
            if query.domain_terms:
                parts.append(f"Domain: {' '.join(query.domain_terms)}")
            if query.count_phrases:
                parts.append(f"Counts: {' '.join(query.count_phrases)}")
            parts.append(f"Text: {query.normalized_text}")
            return " | ".join(parts)
        return query

    def _format_candidate_text(self, candidate: Dict[str, Any]) -> str:
        """Format candidate text with available metadata."""
        parts = []
        
        # Attempt to pull any structured fields if present
        action_canon = candidate.get("action_canonical")
        domain_terms = candidate.get("domain_terms") or candidate.get("domain_tokens")
        count_phrases = candidate.get("count_phrases")
        
        # If structured fields are missing and we have a normalizer, re-normalize on-the-fly
        if self.normalizer and (not action_canon or not domain_terms or not count_phrases):
            # Get original text (prefer step_text over normalized)
            original_text = (
                candidate.get('step_text') or  # Original individual step text
                candidate.get('bdd_step') or  # Full scenario text
                candidate.get('step_text_normalized') or  # Fallback to normalized
                candidate.get('normalized_text') or
                candidate.get('canonical_template') or
                ''
            )
            
            if original_text:
                # Re-normalize to extract structured fields
                normalized_result = self.normalizer.normalize(original_text)
                
                # Use extracted fields if they weren't already present
                if not action_canon and normalized_result.action_canonical:
                    action_canon = normalized_result.action_canonical
                if not domain_terms and normalized_result.domain_terms:
                    domain_terms = normalized_result.domain_terms
                if not count_phrases and normalized_result.count_phrases:
                    count_phrases = normalized_result.count_phrases

        # Format structured cues
        if action_canon:
            parts.append(f"Action: {action_canon}")
        if domain_terms:
            if isinstance(domain_terms, str):
                parts.append(f"Domain: {domain_terms}")
            else:
                parts.append(f"Domain: {' '.join(domain_terms)}")
        if count_phrases:
            if isinstance(count_phrases, str):
                parts.append(f"Counts: {count_phrases}")
            else:
                parts.append(f"Counts: {' '.join(count_phrases)}")

        # Core text fallbacks
        candidate_text = (
            candidate.get('step_text_normalized') or  # Individual step normalized
            candidate.get('step_text') or  # Individual step text
            candidate.get('normalized_text') or  # Fallback
            candidate.get('bdd_step') or
            candidate.get('canonical_template') or
            ''
        )
        parts.append(f"Text: {candidate_text}")
        return " | ".join(parts)

