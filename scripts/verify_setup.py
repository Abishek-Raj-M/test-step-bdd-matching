#!/usr/bin/env python
"""
Verify Setup Script
Checks all dependencies and configurations are properly installed.
"""

import sys
import os

def check_python_version():
    """Check Python version."""
    print("[1/7] Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"  ❌ Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    print(f"  ✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Check required Python packages."""
    print("\n[2/7] Checking Python dependencies...")
    required = [
        'numpy',
        'psycopg2',
        'yaml',
        'sentence_transformers',
        'sklearn',
        'spacy'
    ]
    
    all_ok = True
    for package in required:
        try:
            if package == 'yaml':
                __import__('yaml')
            elif package == 'psycopg2':
                __import__('psycopg2')
            elif package == 'sklearn':
                __import__('sklearn')
            else:
                __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} not installed")
            all_ok = False
    
    return all_ok

def check_spacy_model():
    """Check spaCy model."""
    print("\n[3/7] Checking spaCy English model...")
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        print("  ✅ en_core_web_sm loaded")
        return True
    except Exception as e:
        print(f"  ❌ Failed to load spaCy model: {e}")
        print("  Run: python -m spacy download en_core_web_sm")
        return False

def check_embedding_model():
    """Check embedding model."""
    print("\n[4/7] Checking embedding model...")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        # Quick test
        embedding = model.encode("test")
        print(f"  ✅ all-MiniLM-L6-v2 loaded (dim={len(embedding)})")
        return True
    except Exception as e:
        print(f"  ❌ Failed to load embedding model: {e}")
        return False

def check_reranker_model():
    """Check reranker model."""
    print("\n[5/7] Checking reranker model...")
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        # Quick test
        score = model.predict([["query", "document"]])
        print(f"  ✅ ms-marco-MiniLM-L-6-v2 loaded")
        return True
    except Exception as e:
        print(f"  ❌ Failed to load reranker model: {e}")
        return False

def check_config():
    """Check configuration file."""
    print("\n[6/7] Checking configuration...")
    try:
        # Add parent directory to path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.config import load_config
        config = load_config()
        print(f"  ✅ config.yaml loaded")
        print(f"     - Embedding model: {config.embedding.model_name}")
        print(f"     - Reranker model: {config.reranker.model_name}")
        print(f"     - Database: {config.database.database}")
        return True
    except FileNotFoundError:
        print("  ❌ config.yaml not found")
        return False
    except Exception as e:
        print(f"  ❌ Failed to load config: {e}")
        return False

def check_database():
    """Check database connection."""
    print("\n[7/7] Checking database connection...")
    try:
        import psycopg2
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.config import load_config
        config = load_config()
        
        conn = psycopg2.connect(
            host=config.database.host,
            port=config.database.port,
            database=config.database.database,
            user=config.database.user,
            password=config.database.password
        )
        
        # Check pgvector extension
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
            if cur.fetchone():
                print("  ✅ Connected to PostgreSQL with pgvector")
            else:
                print("  ⚠️  Connected to PostgreSQL, but pgvector not installed")
                print("     Run: CREATE EXTENSION vector;")
                conn.close()
                return False
        
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        print("     Check your database credentials in config.yaml")
        return False

def main():
    """Run all checks."""
    print("=" * 50)
    print("Setup Verification")
    print("=" * 50)
    
    results = []
    results.append(("Python Version", check_python_version()))
    results.append(("Dependencies", check_dependencies()))
    results.append(("spaCy Model", check_spacy_model()))
    results.append(("Embedding Model", check_embedding_model()))
    results.append(("Reranker Model", check_reranker_model()))
    results.append(("Configuration", check_config()))
    results.append(("Database", check_database()))
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print("")
    if all_passed:
        print("🎉 All checks passed! System is ready to use.")
        print("\nNext step:")
        print("  python main.py --mode ingest --input 'csv files/Already_Automated_Tests_Dashboard.csv'")
        return 0
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())















