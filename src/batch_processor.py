"""Batch processing module for processing multiple test steps."""
import csv
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import Counter
from tqdm import tqdm
import numpy as np
from src.pipeline import MatchingPipeline, MatchResult


def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


class BatchProcessor:
    """Processes multiple test steps in batch."""
    
    def __init__(self, pipeline: MatchingPipeline, verbose: bool = True):
        self.pipeline = pipeline
        self.verbose = verbose
    
    def process_csv(self, csv_path: str, output_path: str, limit: Optional[int] = None):
        """
        Process chunked CSV file (one step per row).
        
        Expected input columns:
        - parent_testcase_id: Original test case ID
        - chunk_index: Position in original test case
        - original_chunk: The atomic step text
        - full_testcase_text: Full original test case for context
        
        Args:
            csv_path: Path to input CSV file (already chunked)
            output_path: Path to output CSV file
            limit: Optional limit on number of rows to process
        """
        results = []
        action_counts = Counter()
        
        # First pass: count total rows
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            total_rows = sum(1 for _ in csv.DictReader(f))
        
        # Apply limit if specified
        rows_to_process = min(total_rows, limit) if limit else total_rows
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Total rows in file: {total_rows}")
            if limit:
                print(f"Processing limit: {limit} rows")
            print(f"Processing {rows_to_process} chunks (steps) from: {csv_path}")
            print(f"Mode: Input already chunked (one step per row)")
            print(f"{'='*60}\n")
        
        # Second pass: process with progress bar
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            pbar = tqdm(total=rows_to_process, desc="Processing", 
                       unit="step", ncols=100,
                       bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
            
            for row_idx, row in enumerate(reader):
                # Stop if limit reached
                if limit and row_idx >= limit:
                    break
                parent_testcase_id = row.get('parent_testcase_id', '')
                chunk_index = int(row.get('chunk_index', 0))
                original_chunk = row.get('original_chunk', '')
                full_testcase_text = row.get('full_testcase_text', '')
                
                if not original_chunk or not parent_testcase_id:
                    continue
                
                # Generate query ID
                query_id = f"{parent_testcase_id}_chunk_{chunk_index}"
                
                # Match this chunk (no chunking needed - input already chunked)
                result = self.pipeline.match(
                    original_chunk,
                    query_id,
                    parent_testcase_id,
                    chunk_index,
                    full_testcase_text,
                    previous_steps=None  # Could add context from previous chunks if needed
                )
                
                results.append(result)
                
                # Track stats
                action_counts[result.final_action] += 1
                
                # Update progress bar
                pbar.update(1)  # Increment progress bar
                pbar.set_postfix({
                    'action': result.final_action[:4],
                    'score': f"{result.reranker_score:.2f}" if result.reranker_score else "N/A"
                })
                
                # Verbose output every 50 items
                if self.verbose and len(results) % 50 == 0:
                    reused = action_counts.get('REUSED_TEMPLATE', 0)
                    new_req = action_counts.get('NEW_BDD_REQUIRED', 0)
                    tqdm.write(f"\n  [Progress] Processed {len(results)} steps | "
                              f"REUSED: {reused} | NEW_REQUIRED: {new_req}")
            
            # Close progress bar
            pbar.close()
        
        # Write results
        self._write_results_csv(results, output_path)
        
        # Print summary
        if self.verbose:
            print(f"\n{'='*60}")
            print("PROCESSING COMPLETE")
            print(f"{'='*60}")
            print(f"\nTotal chunks processed: {len(results)}")
            print(f"\nAction Distribution:")
            for action, count in sorted(action_counts.items()):
                pct = (count / len(results) * 100) if results else 0
                print(f"  {action}: {count} ({pct:.1f}%)")
            print(f"\nResults saved to: {output_path}")
        
        return results
    
    def process_json(self, json_path: str, output_path: str, limit: Optional[int] = None):
        """Process test steps from JSON file (chunked format)."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        results = []
        
        # Apply limit if specified
        items_to_process = data[:limit] if limit else data
        
        for item in items_to_process:
            parent_testcase_id = item.get('parent_testcase_id', '')
            chunk_index = item.get('chunk_index', 0)
            original_chunk = item.get('original_chunk', '')
            full_testcase_text = item.get('full_testcase_text', '')
            
            if not original_chunk or not parent_testcase_id:
                continue
            
            query_id = f"{parent_testcase_id}_chunk_{chunk_index}"
            
            result = self.pipeline.match(
                original_chunk,
                query_id,
                parent_testcase_id,
                chunk_index,
                full_testcase_text,
                previous_steps=None
            )
            
            results.append(result)
        
        # Write results
        self._write_results_csv(results, output_path)
        
        return results
    
    def _write_results_csv(self, results: List[MatchResult], output_path: str):
        """Write results to CSV file."""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'query_id', 'parent_testcase_id', 'chunk_index', 'original_chunk',
                'full_testcase_text', 'normalized_text', 'top_k_candidates',
                'selected_candidate_id', 'selected_template', 'final_action',
                'reranker_score', 'vector_similarity', 'processing_time_ms', 'notes'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                # Convert numpy types before JSON serialization
                top_k_candidates = convert_numpy_types(result.top_k_candidates)
                
                writer.writerow({
                    'query_id': result.query_id,
                    'parent_testcase_id': result.parent_testcase_id,
                    'chunk_index': result.chunk_index,
                    'original_chunk': result.original_chunk,
                    'full_testcase_text': result.full_testcase_text,
                    'normalized_text': result.normalized_text,
                    'top_k_candidates': json.dumps(top_k_candidates),
                    'selected_candidate_id': result.selected_candidate_id,
                    'selected_template': result.selected_template,
                    'final_action': result.final_action,
                    'reranker_score': result.reranker_score,
                    'vector_similarity': result.vector_similarity,
                    'processing_time_ms': result.processing_time_ms,
                    'notes': result.notes
                })
