"""Metrics calculation module."""
import json
from typing import List, Dict, Any
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import numpy as np

from src.pipeline import MatchResult


@dataclass
class MetricsReport:
    """Metrics report data."""
    run_timestamp: str
    total_queries: int
    action_distribution: Dict[str, Dict[str, float]]
    similarity_scores: Dict[str, Dict[str, float]]
    top_k_coverage: Dict[str, Any]
    latency: Dict[str, Dict[str, float]]


class MetricsCalculator:
    """Calculates metrics from batch results."""
    
    def calculate(self, results: List[MatchResult]) -> MetricsReport:
        """Calculate metrics from results."""
        total_queries = len(results)
        
        # Action distribution (REUSED_TEMPLATE vs NEW_BDD_REQUIRED)
        action_counts = Counter(r.final_action for r in results)
        action_distribution = {
            action: {
                "count": count,
                "percentage": (count / total_queries * 100) if total_queries > 0 else 0.0
            }
            for action, count in action_counts.items()
        }
        
        # Similarity scores (reranker and vector)
        vector_similarities = [r.vector_similarity for r in results if r.vector_similarity is not None]
        reranker_scores = [r.reranker_score for r in results if r.reranker_score is not None]
        
        similarity_scores = {}
        if vector_similarities:
            similarity_scores["vector_cosine"] = {
                "mean": float(np.mean(vector_similarities)),
                "median": float(np.median(vector_similarities)),
                "min": float(np.min(vector_similarities)),
                "max": float(np.max(vector_similarities)),
                "p25": float(np.percentile(vector_similarities, 25)),
                "p75": float(np.percentile(vector_similarities, 75)),
                "std": float(np.std(vector_similarities))
            }
        
        if reranker_scores:
            similarity_scores["reranker"] = {
                "mean": float(np.mean(reranker_scores)),
                "median": float(np.median(reranker_scores)),
                "min": float(np.min(reranker_scores)),
                "max": float(np.max(reranker_scores)),
                "p25": float(np.percentile(reranker_scores, 25)),
                "p75": float(np.percentile(reranker_scores, 75)),
                "std": float(np.std(reranker_scores))
            }
        
        # Top-K coverage stats
        queries_with_matches = sum(1 for r in results if len(r.top_k_candidates) > 0)
        queries_with_no_matches = total_queries - queries_with_matches
        
        # Count how many candidates each query got
        candidate_counts = [len(r.top_k_candidates) for r in results]
        avg_candidates_per_query = np.mean(candidate_counts) if candidate_counts else 0.0
        
        top_k_coverage = {
            "queries_with_matches": queries_with_matches,
            "queries_with_no_matches": queries_with_no_matches,
            "match_rate": (queries_with_matches / total_queries * 100) if total_queries > 0 else 0.0,
            "average_candidates_per_query": float(avg_candidates_per_query),
            "max_candidates_found": int(np.max(candidate_counts)) if candidate_counts else 0,
            "min_candidates_found": int(np.min(candidate_counts)) if candidate_counts else 0
        }
        
        # Latency
        processing_times = [r.processing_time_ms for r in results]
        latency = {
            "processing_time_ms": {
                "mean": float(np.mean(processing_times)),
                "median": float(np.median(processing_times)),
                "min": float(np.min(processing_times)),
                "max": float(np.max(processing_times)),
                "p95": float(np.percentile(processing_times, 95)),
                "p99": float(np.percentile(processing_times, 99))
            },
            "total_time_seconds": {
                "sum": float(np.sum(processing_times) / 1000.0)
            }
        }
        
        return MetricsReport(
            run_timestamp=datetime.utcnow().isoformat() + "Z",
            total_queries=total_queries,
            action_distribution=action_distribution,
            similarity_scores=similarity_scores,
            top_k_coverage=top_k_coverage,
            latency=latency
        )
    
    def save_report(self, report: MetricsReport, output_path: str):
        """Save metrics report to JSON file."""
        report_dict = {
            "run_timestamp": report.run_timestamp,
            "total_queries": report.total_queries,
            "action_distribution": report.action_distribution,
            "similarity_scores": report.similarity_scores,
            "top_k_coverage": report.top_k_coverage,
            "latency": report.latency
        }
        
        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2)
