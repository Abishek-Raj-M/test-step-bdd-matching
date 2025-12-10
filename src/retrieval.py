"""Retrieval module for finding matching BDD templates."""
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict


class Retrieval:
    """Retrieves relevant BDD templates for queries."""
    
    def __init__(self, database, config):
        self.db = database
        self.config = config
    
    def retrieve(self, query_embedding: np.ndarray, query_text: str, 
                 limit: Optional[int] = None, ef_search: Optional[int] = None) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Retrieve candidates using vector search.
        
        Args:
            query_embedding: Query embedding vector
            query_text: Query text (for logging)
            limit: Number of candidates to retrieve
            ef_search: HNSW ef_search parameter
        
        Returns:
            List of (candidate_id, similarity_score, candidate_dict) tuples
        """
        limit = limit or self.config.retrieval.prefilter_limit
        ef_search = ef_search or self.config.retrieval.ef_search
        
        candidates = self.db.vector_search(query_embedding, limit, ef_search)
        return candidates
    
    def cluster_aggregation(self, candidates: List[Tuple[int, float, Dict[str, Any]]]) -> Dict[int, Dict[str, Any]]:
        """
        Aggregate candidates by cluster_id and compute hybrid scores.
        
        Args:
            candidates: List of (id, similarity, candidate_dict) tuples
        
        Returns:
            Dictionary mapping cluster_id to aggregated cluster info
        """
        cluster_scores = defaultdict(list)
        cluster_candidates = defaultdict(list)
        
        for candidate_id, similarity, candidate_dict in candidates:
            cluster_id = candidate_dict.get('cluster_id')
            if cluster_id is not None:
                cluster_scores[cluster_id].append(similarity)
                cluster_candidates[cluster_id].append((candidate_id, similarity, candidate_dict))
        
        # Compute hybrid scores for each cluster
        cluster_info = {}
        for cluster_id, similarities in cluster_scores.items():
            max_similarity = max(similarities)
            avg_similarity = np.mean(similarities)
            cluster_size = len(similarities)
            usage_count = cluster_candidates[cluster_id][0][2].get('usage_count', 0)
            
            # Hybrid score: 60% max similarity, 20% cluster popularity, 20% lexical (not computed here)
            cluster_popularity_score = min(usage_count / 100.0, 1.0)  # Normalize to 0-1
            hybrid_score = (
                0.6 * max_similarity +
                0.2 * cluster_popularity_score +
                0.2 * avg_similarity  # Using avg as proxy for lexical
            )
            
            cluster_info[cluster_id] = {
                'cluster_id': cluster_id,
                'hybrid_score': hybrid_score,
                'max_similarity': max_similarity,
                'avg_similarity': avg_similarity,
                'cluster_size': cluster_size,
                'usage_count': usage_count,
                'candidates': cluster_candidates[cluster_id]
            }
        
        return cluster_info
    
    def get_best_cluster_candidate(self, cluster_info: Dict[int, Dict[str, Any]]) -> Optional[Tuple[int, float, Dict[str, Any]]]:
        """
        Get the best candidate from the best cluster.
        
        Args:
            cluster_info: Dictionary from cluster_aggregation
        
        Returns:
            Best (candidate_id, score, candidate_dict) tuple or None
        """
        if not cluster_info:
            return None
        
        # Sort clusters by hybrid score
        sorted_clusters = sorted(cluster_info.items(), key=lambda x: x[1]['hybrid_score'], reverse=True)
        
        if not sorted_clusters:
            return None
        
        # Get best candidate from best cluster
        best_cluster_id, best_cluster_info = sorted_clusters[0]
        best_candidates = best_cluster_info['candidates']
        
        # Return candidate with highest similarity
        best_candidates.sort(key=lambda x: x[1], reverse=True)
        return best_candidates[0]







