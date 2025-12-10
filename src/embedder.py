"""Embedding module for generating vector representations."""
import numpy as np
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import hashlib
import pickle
from pathlib import Path


class Embedder:
    """Generates embeddings for text chunks."""
    
    def __init__(self, model_name: str, cache_dir: Optional[str] = None):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.cache_dir = Path(cache_dir) if cache_dir else Path(".embedding_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self._cache: Dict[str, np.ndarray] = {}
    
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        # Check cache
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check disk cache
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                embedding = pickle.load(f)
                self._cache[cache_key] = embedding
                return embedding
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)
        
        # Cache it
        self._cache[cache_key] = embedding
        with open(cache_file, 'wb') as f:
            pickle.dump(embedding, f)
        
        return embedding
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts."""
        # Separate cached and uncached texts
        uncached_texts = []
        uncached_indices = []
        embeddings = [None] * len(texts)
        
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                embeddings[i] = self._cache[cache_key]
            else:
                cache_file = self.cache_dir / f"{cache_key}.pkl"
                if cache_file.exists():
                    with open(cache_file, 'rb') as f:
                        embedding = pickle.load(f)
                        self._cache[cache_key] = embedding
                        embeddings[i] = embedding
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        
        # Generate embeddings for uncached texts in batches
        if uncached_texts:
            for i in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[i:i + batch_size]
                batch_indices = uncached_indices[i:i + batch_size]
                
                batch_embeddings = self.model.encode(
                    batch,
                    convert_to_numpy=True,
                    batch_size=len(batch),
                    show_progress_bar=False
                )
                
                # Cache and store embeddings
                for j, embedding in enumerate(batch_embeddings):
                    text = batch[j]
                    idx = batch_indices[j]
                    cache_key = self._get_cache_key(text)
                    
                    self._cache[cache_key] = embedding
                    embeddings[idx] = embedding
                    
                    # Save to disk
                    cache_file = self.cache_dir / f"{cache_key}.pkl"
                    with open(cache_file, 'wb') as f:
                        pickle.dump(embedding, f)
        
        return embeddings
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()







