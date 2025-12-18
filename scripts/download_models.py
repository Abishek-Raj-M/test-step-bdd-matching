#!/usr/bin/env python
"""
Download all required models for the system.
Run this script to pre-download all models before first use.
"""

import sys
import os

def download_spacy_model():
    """Download spaCy English model."""
    print("=" * 50)
    print("[1/3] Downloading spaCy English model...")
    print("=" * 50)
    
    try:
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
            print("✅ Model already downloaded!")
        except OSError:
            print("Downloading en_core_web_sm...")
            os.system(f"{sys.executable} -m spacy download en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
            print("✅ Downloaded successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    return True

def download_embedding_model():
    """Download sentence transformer embedding model."""
    print("\n" + "=" * 50)
    print("[2/3] Downloading Embedding Model...")
    print("Model: sentence-transformers/all-MiniLM-L6-v2")
    print("Size: ~90 MB")
    print("=" * 50)
    
    try:
        from sentence_transformers import SentenceTransformer
        print("Loading model...")
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # Test the model
        test_embedding = model.encode("This is a test sentence.")
        print(f"✅ Downloaded successfully! (dim={len(test_embedding)})")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def download_reranker_model():
    """Download cross-encoder reranker model."""
    print("\n" + "=" * 50)
    print("[3/3] Downloading Reranker Model...")
    print("Model: cross-encoder/ms-marco-MiniLM-L-6-v2")
    print("Size: ~90 MB")
    print("=" * 50)
    
    try:
        from sentence_transformers import CrossEncoder
        print("Loading model...")
        model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        
        # Test the model
        scores = model.predict([["query", "relevant document"]])
        print(f"✅ Downloaded successfully!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Download all models."""
    print("=" * 50)
    print("Model Downloader")
    print("This will download all required AI models (~200 MB total)")
    print("=" * 50)
    print("")
    
    results = []
    
    # Download models
    results.append(("spaCy (en_core_web_sm)", download_spacy_model()))
    results.append(("Embedding (all-MiniLM-L6-v2)", download_embedding_model()))
    results.append(("Reranker (ms-marco-MiniLM-L-6-v2)", download_reranker_model()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Download Summary")
    print("=" * 50)
    
    all_success = True
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")
        if not success:
            all_success = False
    
    print("")
    if all_success:
        print("🎉 All models downloaded successfully!")
        print("\nYou're ready to use the system!")
    else:
        print("⚠️ Some models failed to download. Please check errors above.")
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())















