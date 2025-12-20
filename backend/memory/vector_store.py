"""
Vector Store for Navi Long-Term Memory
Advanced embedding-based storage for persistent learning and context retrieval.
Equivalent to Gemini's long-term memory but optimized for engineering tasks.
"""

import sys
import pickle
from typing import List, Dict, Any, Optional, cast
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore
np = cast(Any, np)
from pathlib import Path
import logging
from datetime import datetime, timedelta

try:
    import faiss  # type: ignore  # Optional dependency
    FAISS_AVAILABLE = True
except ImportError:
    faiss = cast(Any, None)
    FAISS_AVAILABLE = False
    logging.warning("FAISS not available, using fallback similarity search")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("SentenceTransformers not available, using basic embeddings")

class VectorStore:
    """
    Advanced vector storage and retrieval system for Navi's long-term memory.
    Supports both FAISS (high-performance) and fallback (basic) modes.
    """
    
    def __init__(self, 
                 storage_path: str = "data/memory",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 dimension: int = 384):
        """
        Initialize vector store with embedding model and storage configuration.
        
        Args:
            storage_path: Path to store vector index and metadata
            embedding_model: SentenceTransformer model name
            dimension: Vector dimension (384 for MiniLM, 768 for others)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.dimension = dimension
        self.metadata: List[Dict[str, Any]] = []
        self.texts: List[str] = []
        
        # Initialize embedding model
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.encoder = SentenceTransformer(embedding_model)
                self.dimension = self.encoder.get_sentence_embedding_dimension()
            except Exception as e:
                logging.warning(f"Failed to load {embedding_model}: {e}, using fallback")
                self.encoder = None
        else:
            self.encoder = None
            
        # Initialize FAISS index (use only when library is available)
        self.use_faiss = FAISS_AVAILABLE and faiss is not None
        if self.use_faiss:
            try:
                self.index = faiss.IndexFlatL2(self.dimension)
            except Exception as exc:  # Defensive: fall back if initialization fails
                logging.warning(f"Failed to initialize FAISS index: {exc}. Falling back to in-memory vectors.")
                self.use_faiss = False
                self.index = None
        else:
            self.index = None

        # Fallback storage when FAISS is unavailable
        if not self.use_faiss:
            self.vectors: List[Any] = []  # List of numpy arrays
            
        # Load existing data
        self._load_persistent_data()
        
        logging.info(f"VectorStore initialized: FAISS={self.use_faiss}, "
                    f"SentenceTransformers={SENTENCE_TRANSFORMERS_AVAILABLE}, "
                    f"dimension={self.dimension}")
    
    def _encode_text(self, text: str):
        """
        Encode text to vector using available embedding method.
        
        Args:
            text: Text to encode
            
        Returns:
            Embedding vector as numpy array
        """
        if self.encoder is not None:
            # Use SentenceTransformers for high-quality embeddings
            return self.encoder.encode([text])[0].astype('float32')
        else:
            # Fallback: simple hash-based pseudo-embedding
            hash_val = hash(text.lower())
            # Create a pseudo-random vector based on text hash
            import numpy.random as np_random
            np_random.seed(abs(hash_val) % (2**31))
            vector = np_random.normal(0, 1, self.dimension).astype('float32')
            # np.random.seed()  # Reset seed - not needed
            return vector
    
    def add(self, 
            text: str, 
            metadata: Dict[str, Any], 
            vector: Optional[Any] = None) -> int:
        """
        Add text and metadata to vector store.
        
        Args:
            text: Text content to add
            metadata: Associated metadata (timestamp, type, tags, etc.)
            vector: Pre-computed vector (optional)
            
        Returns:
            Index of added item
        """
        if vector is None:
            vector = self._encode_text(text)
        elif np is not None and not isinstance(vector, np.ndarray):  # type: ignore[attr-defined]
            vector = np.asarray(vector, dtype="float32")  # type: ignore[attr-defined]
    
        norm_val = 0.0
        if np is not None and isinstance(vector, np.ndarray):  # type: ignore[attr-defined]
            from numpy.linalg import norm as np_norm
            norm_val = float(np_norm(vector))  # type: ignore[arg-type]
            if norm_val > 0:
                vector = vector / norm_val  # type: ignore[operator]
    
        # Add to storage
        if self.use_faiss and FAISS_AVAILABLE and self.index is not None:
            if np is not None:
                vector_array = np.array([vector], dtype="float32")  # type: ignore[attr-defined]
            else:
                vector_array = [vector]
            self.index.add(vector_array)
        else:
            self.vectors.append(vector)
        
        self.texts.append(text)
        self.metadata.append({
            **metadata,
            'added_at': datetime.utcnow().isoformat(),
            'text_length': len(text),
            'vector_norm': float(norm_val)
        })
        
        index = len(self.texts) - 1
        
        # Persist changes periodically
        if index % 100 == 0:
            self._save_persistent_data()
        
        logging.debug(f"Added item {index}: {text[:50]}...")
        return index
    
    def search(self, 
              query: str, 
              k: int = 5,
              filters: Optional[Dict[str, Any]] = None,
              min_similarity: float = 0.1) -> List[Dict[str, Any]]:
        """
        Search for similar items in vector store.
        
        Args:
            query: Search query text
            k: Number of results to return
            filters: Optional filters for metadata
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of matching items with metadata and similarity scores
        """
        if len(self.texts) == 0:
            return []
        
        query_vector = self._encode_text(query)
        
        # Normalize query vector
        norm_val = 0.0
        if np is not None and isinstance(query_vector, np.ndarray):  # type: ignore[attr-defined]
            from numpy.linalg import norm as np_norm
            norm_val = float(np_norm(query_vector))  # type: ignore[arg-type]
            if norm_val > 0:
                query_vector = query_vector / norm_val  # type: ignore[operator]
        
        if self.use_faiss and FAISS_AVAILABLE and self.index is not None:
            # Use FAISS for efficient search
            if np is not None:
                query_array = np.array([query_vector], dtype="float32")  # type: ignore[attr-defined]
            else:
                query_array = [query_vector]
            distances, indices = self.index.search(query_array, min(k * 2, len(self.texts)))
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx >= len(self.metadata):
                    continue
                    
                # Convert L2 distance to cosine similarity
                similarity = 1.0 - (dist / 2.0)
                
                if similarity < min_similarity:
                    continue
                    
                item = {
                    'text': self.texts[idx],
                    'metadata': self.metadata[idx],
                    'similarity': float(similarity),
                    'index': int(idx)
                }
                
                # Apply filters if provided
                if self._passes_filters(item['metadata'], filters):
                    results.append(item)
        else:
            # Fallback: compute similarities manually
            similarities = []
            for i, vector in enumerate(self.vectors):
                # Cosine similarity
                if np is None:
                    similarity = 0.0
                else:
                    similarity = float(np.dot(query_vector, vector))  # type: ignore[attr-defined]
                similarities.append((similarity, i))
            
            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[0], reverse=True)
            
            results = []
            for similarity, idx in similarities[:k * 2]:
                if similarity < min_similarity:
                    continue
                    
                item = {
                    'text': self.texts[idx],
                    'metadata': self.metadata[idx],
                    'similarity': float(similarity),
                    'index': int(idx)
                }
                
                # Apply filters if provided
                if self._passes_filters(item['metadata'], filters):
                    results.append(item)
        
        # Return top k results
        return results[:k]
    
    def _passes_filters(self, metadata: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
        """
        Check if metadata passes filter criteria.
        
        Args:
            metadata: Item metadata
            filters: Filter criteria
            
        Returns:
            True if item passes filters
        """
        if filters is None:
            return True
        
        for key, value in filters.items():
            if key not in metadata:
                return False
            
            meta_value = metadata[key]
            
            if isinstance(value, list):
                # Check if metadata value is in the list
                if meta_value not in value:
                    return False
            elif isinstance(value, dict):
                # Range or comparison filters
                if 'min' in value and meta_value < value['min']:
                    return False
                if 'max' in value and meta_value > value['max']:
                    return False
            else:
                # Exact match
                if meta_value != value:
                    return False
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        
        Returns:
            Dictionary with store statistics
        """
        if len(self.texts) == 0:
            return {
                'total_items': 0,
                'storage_size_mb': 0,
                'avg_text_length': 0,
                'unique_types': [],
                'date_range': None
            }
        
        # Calculate storage size
        storage_size = 0
        for file_path in self.storage_path.glob('*'):
            if file_path.is_file():
                storage_size += file_path.stat().st_size
        
        # Analyze metadata
        types = set()
        dates = []
        text_lengths = []
        
        for meta, text in zip(self.metadata, self.texts):
            if 'type' in meta:
                types.add(meta['type'])
            if 'added_at' in meta:
                try:
                    dates.append(datetime.fromisoformat(meta['added_at']))
                except Exception:
                    pass
            text_lengths.append(len(text))
        
        return {
            'total_items': len(self.texts),
            'storage_size_mb': storage_size / (1024 * 1024),
            'avg_text_length': sum(text_lengths) / len(text_lengths) if text_lengths else 0,
            'unique_types': list(types),
            'date_range': {
                'earliest': min(dates).isoformat() if dates else None,
                'latest': max(dates).isoformat() if dates else None
            },
            'use_faiss': self.use_faiss,
            'dimension': self.dimension
        }
    
    def cleanup_old_entries(self, days_old: int = 30, max_items: Optional[int] = None):
        """
        Remove old entries to manage storage size.
        
        Args:
            days_old: Remove entries older than this many days
            max_items: Keep only the most recent max_items entries
        """
        if len(self.texts) == 0:
            return
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        indices_to_keep = []
        
        for i, meta in enumerate(self.metadata):
            if 'added_at' in meta:
                try:
                    added_date = datetime.fromisoformat(meta['added_at'])
                    if added_date >= cutoff_date:
                        indices_to_keep.append(i)
                except Exception:
                    indices_to_keep.append(i)  # Keep if date parsing fails
            else:
                indices_to_keep.append(i)  # Keep if no date
        
        # Apply max_items limit
        if max_items is not None and len(indices_to_keep) > max_items:
            indices_to_keep = indices_to_keep[-max_items:]
        
        # Rebuild store with kept indices
        if len(indices_to_keep) < len(self.texts):
            old_count = len(self.texts)
            self._rebuild_from_indices(indices_to_keep)
            new_count = len(self.texts)
            logging.info(f"Cleaned up vector store: {old_count} -> {new_count} items")
    
    def _rebuild_from_indices(self, indices_to_keep: List[int]):
        """
        Rebuild vector store keeping only specified indices.
        
        Args:
            indices_to_keep: List of indices to keep
        """
        new_texts = [self.texts[i] for i in indices_to_keep]
        new_metadata = [self.metadata[i] for i in indices_to_keep]
        
        if self.use_faiss and FAISS_AVAILABLE and faiss is not None:
            # Rebuild FAISS index
            new_index = faiss.IndexFlatL2(self.dimension)
            for i in indices_to_keep:
                # Re-encode text to rebuild vectors
                vector = self._encode_text(self.texts[i])
                if np is not None:
                    vector_array = np.array([vector], dtype="float32")  # type: ignore[attr-defined]
                    new_index.add(vector_array)
                else:
                    new_index.add([vector])  # type: ignore[arg-type]
            self.index = new_index
        else:
            # Rebuild vector list
            new_vectors = []
            for i in indices_to_keep:
                # Re-encode text to rebuild vectors
                vector = self._encode_text(self.texts[i])
                new_vectors.append(vector)
            self.vectors = new_vectors
        
        self.texts = new_texts
        self.metadata = new_metadata
    
    def _save_persistent_data(self):
        """Save vector store data to disk for persistence."""
        try:
            # Save metadata and texts
            with open(self.storage_path / 'metadata.pkl', 'wb') as f:
                pickle.dump(self.metadata, f)
            
            with open(self.storage_path / 'texts.pkl', 'wb') as f:
                pickle.dump(self.texts, f)
            
            # Save FAISS index or vectors
            if self.use_faiss:
                faiss.write_index(self.index, str(self.storage_path / 'faiss.index'))
            else:
                with open(self.storage_path / 'vectors.pkl', 'wb') as f:
                    pickle.dump(self.vectors, f)
            
            logging.debug(f"Saved vector store to {self.storage_path}")
        except Exception as e:
            logging.error(f"Failed to save vector store: {e}")
    
    def _load_persistent_data(self):
        """Load vector store data from disk if available."""
        try:
            # Load metadata and texts
            metadata_path = self.storage_path / 'metadata.pkl'
            texts_path = self.storage_path / 'texts.pkl'
            
            if metadata_path.exists() and texts_path.exists():
                with open(metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                
                with open(texts_path, 'rb') as f:
                    self.texts = pickle.load(f)
                
                # Load FAISS index or vectors
                if self.use_faiss and faiss is not None:
                    index_path = self.storage_path / 'faiss.index'
                    if index_path.exists():
                        self.index = faiss.read_index(str(index_path))
                    else:
                        # Rebuild index from texts
                        if self.index is not None:
                            for text in self.texts:
                                vector = self._encode_text(text)
                                if np is not None:
                                    vector_array = np.array([vector], dtype="float32")  # type: ignore[attr-defined]
                                    self.index.add(vector_array)
                                else:
                                    self.index.add([vector])  # type: ignore[arg-type]
                else:
                    vectors_path = self.storage_path / 'vectors.pkl'
                    if vectors_path.exists():
                        with open(vectors_path, 'rb') as f:
                            self.vectors = pickle.load(f)
                    else:
                        # Rebuild vectors from texts
                        self.vectors = [self._encode_text(text) for text in self.texts]
                
                logging.info(f"Loaded {len(self.texts)} items from {self.storage_path}")
        except Exception as e:
            logging.warning(f"Failed to load existing vector store: {e}")
            # Initialize empty store
            self.metadata = []
            self.texts = []
            if not self.use_faiss:
                self.vectors = []
    
    def __del__(self):
        """Save data on destruction."""
        try:
            # Avoid saving while the interpreter is shutting down because numpy may be unloaded
            if sys.is_finalizing():
                return
            self._save_persistent_data()
        except Exception:
            pass  # Ignore errors during cleanup
