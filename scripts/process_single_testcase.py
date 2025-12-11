"""Process one or more test cases and return top 5-6 BDD step matches for each step."""
import sys
import json
import csv
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, '.')
from src.config import load_config
from src.database import Database
from src.normalizer import Normalizer
from src.chunker import Chunker
from src.embedder import Embedder
from src.retrieval import Retrieval
from src.reranker import Reranker
from src.placeholder_mapper import PlaceholderMapper
from src.fallback import FallbackChain
from src.pipeline import MatchingPipeline
from tqdm import tqdm


def process_single_testcase(testcase_id: str, manual_steps: str, pipeline: MatchingPipeline, 
                            output_dir: Path = None, verbose: bool = True):
    """
    Process a single test case and return matches for each step.
    
    Args:
        testcase_id: Test case ID
        manual_steps: Full manual steps text (multi-step)
        pipeline: Pre-initialized MatchingPipeline
        output_dir: Output directory
        verbose: Whether to print detailed output
    
    Returns:
        Dict with testcase_id, results, and summary
    """
    normalizer = Normalizer(pipeline.config.normalization_version)
    chunker = Chunker()
    
    # Chunk the manual steps into atomic steps
    if verbose:
        print(f"\n{'='*70}")
        print(f"Processing Test Case: {testcase_id}")
        print(f"{'='*70}")
        print(f"\nManual Steps:\n{manual_steps[:200]}..." if len(manual_steps) > 200 else f"\nManual Steps:\n{manual_steps}")
    
    chunks = chunker.chunk(manual_steps, testcase_id, normalizer)
    if verbose:
        print(f"\nChunked into {len(chunks)} atomic steps")
        print(f"{'='*70}\n")
    
    # Process each chunk
    results = []
    for chunk in tqdm(chunks, desc=f"Processing {testcase_id}", unit="step", disable=not verbose):
        result = pipeline.match(
            chunk.original_chunk,
            f"{testcase_id}_chunk_{chunk.chunk_index}",
            testcase_id,
            chunk.chunk_index,
            manual_steps,  # Full test case for context
            previous_steps=None
        )
        results.append(result)
    
    # Convert results to JSON-serializable format
    results_data = []
    for result in results:
        results_data.append({
            'query_id': result.query_id,
            'parent_testcase_id': result.parent_testcase_id,
            'chunk_index': result.chunk_index,
            'original_chunk': result.original_chunk,
            'full_testcase_text': result.full_testcase_text,
            'normalized_text': result.normalized_text,
            'top_k_candidates': result.top_k_candidates,  # Top 5-6 matches
            'selected_candidate_id': result.selected_candidate_id,
            'selected_template': result.selected_template,
            'final_action': result.final_action,
            'reranker_score': result.reranker_score,
            'vector_similarity': result.vector_similarity,
            'processing_time_ms': result.processing_time_ms,
            'notes': result.notes
        })
    
    reused_count = sum(1 for r in results if r.final_action == 'REUSED_TEMPLATE')
    new_required_count = sum(1 for r in results if r.final_action == 'NEW_BDD_REQUIRED')
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"COMPLETE: {testcase_id}")
        print(f"{'='*70}")
        print(f"Total steps: {len(results)}")
        print(f"REUSED_TEMPLATE: {reused_count}")
        print(f"NEW_BDD_REQUIRED: {new_required_count}")
    
    return {
        'testcase_id': testcase_id,
        'total_steps': len(results),
        'reused_count': reused_count,
        'new_required_count': new_required_count,
        'results': results_data
    }


def parse_limit(limit_str: Optional[str], total_count: int) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse limit string into start and end indices.
    
    Supports:
    - Single number: "4" -> process first 4 (0-3)
    - Range: "4-8" or "4 to 8" -> process indices 4-8 (inclusive, 0-based)
    
    Args:
        limit_str: Limit string from command line
        total_count: Total number of test cases available
    
    Returns:
        Tuple of (start_index, end_index) or (None, count) for single number
    """
    if limit_str is None:
        return None, None
    
    limit_str = limit_str.strip().lower()
    
    # Check for range format: "4-8" or "4 to 8"
    if '-' in limit_str or ' to ' in limit_str:
        # Replace " to " with "-"
        limit_str = limit_str.replace(' to ', '-')
        try:
            parts = limit_str.split('-')
            if len(parts) == 2:
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                # Validate range
                if start < 0:
                    start = 0
                if end >= total_count:
                    end = total_count - 1
                if start > end:
                    raise ValueError(f"Start index ({start}) must be <= end index ({end})")
                return start, end + 1  # end+1 because slicing is exclusive
        except ValueError as e:
            raise ValueError(f"Invalid range format: {limit_str}. Use 'START-END' or 'START to END' (e.g., '4-8')")
    else:
        # Single number: process first N
        try:
            count = int(limit_str)
            if count < 0:
                count = 0
            if count > total_count:
                count = total_count
            return None, count
        except ValueError:
            raise ValueError(f"Invalid limit format: {limit_str}. Use a number (e.g., '4') or range (e.g., '4-8')")


def process_multiple_testcases(csv_file: str, limit: Optional[str] = None, 
                               testcase_id_col: str = "ID", 
                               steps_col: str = "Manual Steps",
                               output_dir: Optional[str] = None,
                               verbose: bool = True):
    """
    Process multiple test cases from a CSV file.
    
    Args:
        csv_file: Path to CSV file with test cases
        limit: Maximum number of test cases to process (None = all)
        testcase_id_col: Column name for test case ID
        steps_col: Column name for manual steps
        output_dir: Optional output directory (default: output/timestamp/)
        verbose: Whether to print detailed output
    
    Returns:
        List of result dictionaries, one per test case
    """
    # Setup pipeline once (shared across all test cases)
    config = load_config()
    db = Database(config)
    normalizer = Normalizer(config.normalization_version)
    chunker = Chunker()
    embedder = Embedder(config.embedding.model_name, cache_dir=config.embedding.cache_dir)
    retrieval = Retrieval(db, config)
    reranker = Reranker(config.reranker.model_name, normalizer)
    placeholder_mapper = PlaceholderMapper()
    fallback_chain = FallbackChain(db, retrieval, reranker, normalizer, embedder, config)
    
    pipeline = MatchingPipeline(
        config, db, normalizer, chunker, embedder, retrieval, reranker,
        placeholder_mapper, fallback_chain
    )
    
    # Read test cases from CSV
    testcases = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        first_row = next(reader, None)
        if first_row is None:
            if verbose:
                print("CSV file is empty!")
            return []
        
        # Check if this is a chunked CSV (already preprocessed)
        is_chunked = 'parent_testcase_id' in first_row and 'original_chunk' in first_row and 'full_testcase_text' in first_row
        
        if is_chunked:
            # Chunked format: group by parent_testcase_id
            if verbose:
                print("Detected chunked CSV format - grouping by parent_testcase_id...")
            
            # Reset file pointer
            f.seek(0)
            reader = csv.DictReader(f)
            
            # Group chunks by parent_testcase_id
            testcase_dict = {}
            for row in reader:
                parent_id = row.get('parent_testcase_id', '').strip()
                full_text = row.get('full_testcase_text', '').strip()
                
                if parent_id and full_text:
                    # Use the full_testcase_text (same for all chunks of same test case)
                    if parent_id not in testcase_dict:
                        testcase_dict[parent_id] = full_text
            
            # Convert to list
            testcases = [{'id': tid, 'steps': steps} for tid, steps in testcase_dict.items()]
            
            if verbose:
                print(f"Grouped into {len(testcases)} unique test cases")
        else:
            # Regular format: one test case per row
            # Add first row back
            testcase_id = first_row.get(testcase_id_col, '').strip()
            manual_steps = first_row.get(steps_col, '').strip()
            if testcase_id and manual_steps:
                testcases.append({'id': testcase_id, 'steps': manual_steps})
            
            # Read remaining rows
            for row in reader:
                testcase_id = row.get(testcase_id_col, '').strip()
                manual_steps = row.get(steps_col, '').strip()
                if testcase_id and manual_steps:
                    testcases.append({'id': testcase_id, 'steps': manual_steps})
    
    # Parse and apply limit
    total_available = len(testcases)
    start_idx, end_idx = parse_limit(limit, total_available)
    
    if start_idx is not None and end_idx is not None:
        # Range: process testcases[start_idx:end_idx]
        testcases = testcases[start_idx:end_idx]
        limit_display = f"indices {start_idx} to {end_idx-1} ({len(testcases)} test cases)"
    elif end_idx is not None:
        # Single number: process first N
        testcases = testcases[:end_idx]
        limit_display = f"first {end_idx} test cases"
    else:
        # No limit: process all
        limit_display = "all test cases"
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"PROCESSING {len(testcases)} TEST CASE(S)")
        print(f"{'='*70}")
        print(f"Input file: {csv_file}")
        print(f"Total available: {total_available}")
        print(f"Limit: {limit_display}")
        if start_idx is not None:
            print(f"Range: [{start_idx}:{end_idx}] (0-based indexing)")
        print(f"{'='*70}\n")
    
    # Process each test case
    all_results = []
    for i, testcase in enumerate(tqdm(testcases, desc="Processing test cases", unit="testcase", disable=not verbose), 1):
        if verbose:
            print(f"\n[{i}/{len(testcases)}] Processing: {testcase['id']}")
        
        result = process_single_testcase(
            testcase['id'],
            testcase['steps'],
            pipeline,
            output_dir=None,  # Will be set later
            verbose=verbose
        )
        all_results.append(result)
    
    # Create output directory
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path(f"output/{timestamp}")
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save combined results
    output_file = output_dir / "testcases_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_testcases': len(all_results),
            'total_steps': sum(r['total_steps'] for r in all_results),
            'total_reused': sum(r['reused_count'] for r in all_results),
            'total_new_required': sum(r['new_required_count'] for r in all_results),
            'testcases': all_results
        }, f, indent=2, ensure_ascii=False)
    
    # Save individual test case results
    for result in all_results:
        individual_file = output_dir / f"{result['testcase_id']}_results.json"
        with open(individual_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    
    if verbose:
        print(f"\n{'='*70}")
        print("ALL TEST CASES COMPLETE")
        print(f"{'='*70}")
        print(f"\nTotal test cases: {len(all_results)}")
        print(f"Total steps: {sum(r['total_steps'] for r in all_results)}")
        print(f"Total REUSED_TEMPLATE: {sum(r['reused_count'] for r in all_results)}")
        print(f"Total NEW_BDD_REQUIRED: {sum(r['new_required_count'] for r in all_results)}")
        print(f"\nResults saved to: {output_dir}")
        print(f"  - Combined: {output_file}")
        print(f"  - Individual files: {result['testcase_id']}_results.json (one per test case)")
        print(f"{'='*70}\n")
    
    db.close()
    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process one or more test cases and return top 5-6 BDD step matches for each step."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to CSV file with test cases (columns: ID, Manual Steps) or 'single' for single test case"
    )
    parser.add_argument(
        "--limit",
        type=str,
        default=None,
        help="Limit test cases: single number (e.g., '4') or range (e.g., '4-8' or '4 to 8'). Default: all"
    )
    parser.add_argument(
        "--id-col",
        type=str,
        default="ID",
        help="Column name for test case ID (default: ID)"
    )
    parser.add_argument(
        "--steps-col",
        type=str,
        default="Manual Steps",
        help="Column name for manual steps (default: Manual Steps)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: output/timestamp/)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce verbose output"
    )
    
    args = parser.parse_args()
    
    # Process multiple test cases from CSV
    process_multiple_testcases(
        csv_file=args.input,
        limit=args.limit,
        testcase_id_col=args.id_col,
        steps_col=args.steps_col,
        output_dir=args.output,
        verbose=not args.quiet
    )

