"""Main entry point for test step to BDD matching system."""
import argparse
from pathlib import Path
import sys
from datetime import datetime

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
from src.ingestion import IngestionPipeline
from src.clustering import Clustering
from src.batch_processor import BatchProcessor
from src.metrics import MetricsCalculator


def setup_pipeline(config):
    """Set up the matching pipeline."""
    # Initialize components
    db = Database(config)
    normalizer = Normalizer(config.normalization_version)
    chunker = Chunker()
    embedding_model = (
        config.embedding.legacy_model_name
        if getattr(config.embedding, "use_legacy", False)
        else config.embedding.model_name
    )
    embedder = Embedder(embedding_model)
    retrieval = Retrieval(db, config)
    reranker_model = (
        config.reranker.fallback_model_name
        if getattr(config.reranker, "use_fallback", False)
        else config.reranker.model_name
    )
    reranker = Reranker(reranker_model)
    placeholder_mapper = PlaceholderMapper()
    fallback_chain = FallbackChain(db, retrieval, reranker, normalizer, embedder, config)
    
    pipeline = MatchingPipeline(
        config, db, normalizer, chunker, embedder, retrieval, reranker,
        placeholder_mapper, fallback_chain
    )
    
    return pipeline, db, normalizer, chunker, embedder


def ingest_data(config, csv_files):
    """Ingest data from CSV files."""
    pipeline, db, normalizer, chunker, embedder = setup_pipeline(config)
    
    ingestion = IngestionPipeline(config, db, normalizer, chunker, embedder)
    
    total_bdd = 0
    total_chunks = 0
    
    for csv_file in csv_files:
        bdd_count, chunk_count = ingestion.ingest_csv(csv_file)
        total_bdd += bdd_count
        total_chunks += chunk_count
    
    print(f"\n{'='*60}")
    print("INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"Total BDD Steps (feature_steps): {total_bdd}")
    print(f"Total Manual Step chunks: {total_chunks}")
    print(f"{'='*60}\n")
    
    db.close()


def process_batch(config, input_file, output_file=None, metrics_output=None, limit=None):
    """Process a batch of test steps."""
    pipeline, db, normalizer, chunker, embedder = setup_pipeline(config)
    
    batch_processor = BatchProcessor(pipeline, verbose=True)
    
    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = Path("output") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set default output paths if not provided
    if not output_file:
        output_file = str(output_dir / "results.csv")
    else:
        # If output_file is provided, use it but still create timestamped directory
        output_file = str(output_dir / Path(output_file).name)
    
    if not metrics_output:
        metrics_output = str(output_dir / "metrics.json")
    else:
        metrics_output = str(output_dir / Path(metrics_output).name)
    
    print(f"\n{'='*60}")
    print(f"Output Directory: {output_dir}")
    if limit:
        print(f"Processing limit: {limit} rows")
    print(f"{'='*60}\n")
    
    # Determine file type
    input_path = Path(input_file)
    if input_path.suffix.lower() == '.csv':
        results = batch_processor.process_csv(input_file, output_file, limit=limit)
    elif input_path.suffix.lower() == '.json':
        results = batch_processor.process_json(input_file, output_file, limit=limit)
    else:
        print(f"Unsupported file type: {input_path.suffix}")
        sys.exit(1)
    
    # Calculate metrics
    metrics_calc = MetricsCalculator()
    report = metrics_calc.calculate(results)
    metrics_calc.save_report(report, metrics_output)
    print(f"\nMetrics saved to {metrics_output}")
    
    db.close()


def main():
    parser = argparse.ArgumentParser(description="Test Step to BDD Matching System")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--mode", choices=["ingest", "process"], required=True,
                       help="Mode: ingest data or process queries")
    parser.add_argument("--input", help="Input file(s) for ingestion or processing")
    parser.add_argument("--output", help="Output file for processing results")
    parser.add_argument("--metrics", help="Output file for metrics report")
    parser.add_argument("--limit", type=int, help="Limit number of rows to process (e.g., --limit 5 for first 5 rows)")
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config)
    
    if args.mode == "ingest":
        if not args.input:
            print("Error: --input required for ingest mode")
            sys.exit(1)
        
        # Support multiple CSV files
        input_files = args.input.split(",")
        ingest_data(config, input_files)
    
    elif args.mode == "process":
        if not args.input:
            print("Error: --input required for process mode")
            sys.exit(1)
        
        # Output files are optional - will be created in timestamped directory
        process_batch(config, args.input, args.output, args.metrics, args.limit)


if __name__ == "__main__":
    main()

