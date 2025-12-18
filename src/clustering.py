"""Clustering module for grouping similar chunks."""
import numpy as np
from typing import List, Tuple, Dict, Any
from sklearn.cluster import AgglomerativeClustering
from collections import Counter


class Clustering:
    """Clusters semantically similar chunks."""
    
    def __init__(self, method: str = "agglomerative", threshold: float = 0.22, min_cluster_size: int = 3):
        self.method = method
        self.threshold = threshold
        self.min_cluster_size = min_cluster_size
    
    def cluster(self, embeddings: List[np.ndarray], chunks: List[Dict[str, Any]]) -> Dict[int, List[int]]:
        """
        Cluster embeddings and return cluster assignments.
        
        Args:
            embeddings: List of embedding vectors
            chunks: List of chunk metadata dicts
        
        Returns:
            Dictionary mapping cluster_id to list of chunk indices
        """
        if len(embeddings) < 2:
            return {}
        
        embeddings_array = np.array(embeddings)
        
        if self.method == "agglomerative":
            return self._agglomerative_cluster(embeddings_array, chunks)
        else:
            raise ValueError(f"Unknown clustering method: {self.method}")
    
    def _agglomerative_cluster(self, embeddings: np.ndarray, chunks: List[Dict[str, Any]]) -> Dict[int, List[int]]:
        """Perform agglomerative clustering."""
        # Compute pairwise cosine distances
        # Cosine distance = 1 - cosine similarity
        # We'll use sklearn's AgglomerativeClustering with cosine distance
        
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.threshold,
            linkage='average',
            metric='cosine'
        )
        
        cluster_labels = clustering.fit_predict(embeddings)
        
        # Group chunks by cluster
        clusters: Dict[int, List[int]] = {}
        for idx, label in enumerate(cluster_labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)
        
        # Filter clusters by min_cluster_size
        filtered_clusters = {}
        for cluster_id, indices in clusters.items():
            if len(indices) >= self.min_cluster_size:
                filtered_clusters[cluster_id] = indices
        
        return filtered_clusters
    
    def select_canonical_template(self, cluster_chunks: List[Dict[str, Any]]) -> str:
        """
        Select the most frequent chunk as canonical template.
        
        Args:
            cluster_chunks: List of chunk dicts with 'normalized_chunk' or 'original_chunk'
        
        Returns:
            Canonical template text
        """
        if not cluster_chunks:
            return ""
        
        # Count occurrences of normalized chunks
        normalized_texts = [chunk.get('normalized_chunk', chunk.get('original_chunk', '')) 
                           for chunk in cluster_chunks]
        counter = Counter(normalized_texts)
        
        # Return most frequent
        most_common = counter.most_common(1)[0][0]
        
        # Get original chunk text for the most common normalized text
        for chunk in cluster_chunks:
            if chunk.get('normalized_chunk') == most_common:
                return chunk.get('original_chunk', most_common)
        
        return most_common















