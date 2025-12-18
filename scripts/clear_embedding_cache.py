"""Clear embedding cache to force regeneration with new model."""
import sys
sys.path.insert(0, '.')
from pathlib import Path
import shutil

def clear_cache():
    """Clear the embedding cache directory."""
    cache_dir = Path(".embedding_cache")
    
    if cache_dir.exists():
        print(f"Found cache directory: {cache_dir}")
        print(f"Cache size: {sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file()) / 1024 / 1024:.2f} MB")
        
        response = input("\nClear all cached embeddings? (yes/no): ")
        if response.lower() == 'yes':
            shutil.rmtree(cache_dir)
            print("✅ Cache cleared!")
            print("\nNext time you run ingestion, embeddings will be regenerated with the new model.")
        else:
            print("Cache not cleared.")
    else:
        print("No cache directory found. Cache will be created on first run.")

if __name__ == "__main__":
    clear_cache()












