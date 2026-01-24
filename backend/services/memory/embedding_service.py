"""
Embedding Service for NAVI Memory System.

Generates vector embeddings for semantic search across all memory types
using OpenAI's text-embedding-3-small model (or configurable alternatives).

Features:
- Batch embedding generation for efficiency
- Caching to avoid redundant API calls
- Configurable embedding dimensions
- Support for multiple text types (code, conversation, documentation)
"""

import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple

import tiktoken

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating vector embeddings for semantic search.

    Uses OpenAI's embedding API by default, with support for
    configurable models and dimensions.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        dimensions: int = 1536,
        max_tokens: int = 8191,
    ):
        """
        Initialize the embedding service.

        Args:
            model: Embedding model name (default: text-embedding-3-small)
            dimensions: Embedding vector dimensions
            max_tokens: Maximum tokens per embedding request
        """
        settings = get_settings()
        self.model = model or getattr(
            settings, "embedding_model", "text-embedding-3-small"
        )
        self.dimensions = dimensions
        self.max_tokens = max_tokens
        self._client = None
        self._tokenizer = None

        # In-memory cache for embeddings (LRU cache)
        self._cache: Dict[str, List[float]] = {}
        self._cache_max_size = 10000

    @property
    def client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI

                settings = get_settings()
                self._client = OpenAI(api_key=settings.openai_api_key)
            except ImportError:
                logger.error("OpenAI package not installed. Run: pip install openai")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise
        return self._client

    @property
    def tokenizer(self):
        """Lazy-load tokenizer for token counting."""
        if self._tokenizer is None:
            try:
                self._tokenizer = tiktoken.encoding_for_model(self.model)
            except Exception:
                # Fallback to cl100k_base for newer models
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
        return self._tokenizer

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def truncate_text(self, text: str, max_tokens: Optional[int] = None) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens (default: self.max_tokens)

        Returns:
            Truncated text
        """
        max_tokens = max_tokens or self.max_tokens
        tokens = self.tokenizer.encode(text)

        if len(tokens) <= max_tokens:
            return text

        # Truncate and decode
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)

    async def embed_text(
        self,
        text: str,
        use_cache: bool = True,
    ) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings

        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            return [0.0] * self.dimensions

        # Check cache
        cache_key = self._get_cache_key(text)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        # Truncate if needed
        text = self.truncate_text(text)

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )
            embedding = response.data[0].embedding

            # Cache result
            if use_cache:
                self._add_to_cache(cache_key, embedding)

            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Return zero vector on error
            return [0.0] * self.dimensions

    async def embed_texts(
        self,
        texts: List[str],
        use_cache: bool = True,
        batch_size: int = 100,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cached embeddings
            batch_size: Maximum texts per API call

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        texts_to_embed: List[Tuple[int, str]] = []

        # Check cache first
        for i, text in enumerate(texts):
            if not text or not text.strip():
                results[i] = [0.0] * self.dimensions
                continue

            cache_key = self._get_cache_key(text)
            if use_cache and cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                texts_to_embed.append((i, self.truncate_text(text)))

        # Batch embed remaining texts
        if texts_to_embed:
            for batch_start in range(0, len(texts_to_embed), batch_size):
                batch = texts_to_embed[batch_start : batch_start + batch_size]
                batch_texts = [t[1] for t in batch]

                try:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=batch_texts,
                        dimensions=self.dimensions,
                    )

                    for j, embedding_data in enumerate(response.data):
                        original_idx = batch[j][0]
                        embedding = embedding_data.embedding
                        results[original_idx] = embedding

                        # Cache result
                        if use_cache:
                            cache_key = self._get_cache_key(texts[original_idx])
                            self._add_to_cache(cache_key, embedding)

                except Exception as e:
                    logger.error(f"Batch embedding failed: {e}")
                    # Fill failed embeddings with zeros
                    for idx, _ in batch:
                        if results[idx] is None:
                            results[idx] = [0.0] * self.dimensions

        # Ensure all results are filled
        for i in range(len(results)):
            if results[i] is None:
                results[i] = [0.0] * self.dimensions

        return results  # type: ignore

    def _add_to_cache(self, key: str, embedding: List[float]) -> None:
        """Add embedding to cache with LRU eviction."""
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entries (simple FIFO, not true LRU)
            keys_to_remove = list(self._cache.keys())[:1000]
            for k in keys_to_remove:
                del self._cache[k]

        self._cache[key] = embedding

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    async def embed_code(
        self,
        code: str,
        language: str,
        context: Optional[str] = None,
    ) -> List[float]:
        """
        Generate embedding for code with optional context.

        Prepends language and context information to improve
        code embedding quality.

        Args:
            code: Code to embed
            language: Programming language
            context: Optional context (function name, class, etc.)

        Returns:
            Embedding vector
        """
        # Build enhanced text for better code embeddings
        parts = [f"Language: {language}"]
        if context:
            parts.append(f"Context: {context}")
        parts.append(f"Code:\n{code}")

        enhanced_text = "\n".join(parts)
        return await self.embed_text(enhanced_text)

    async def embed_conversation(
        self,
        messages: List[Dict[str, str]],
        max_messages: int = 10,
    ) -> List[float]:
        """
        Generate embedding for a conversation segment.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_messages: Maximum messages to include

        Returns:
            Embedding vector
        """
        # Take last N messages
        recent_messages = messages[-max_messages:]

        # Format conversation
        formatted = []
        for msg in recent_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")

        conversation_text = "\n".join(formatted)
        return await self.embed_text(conversation_text)

    def serialize_embedding(self, embedding: List[float]) -> str:
        """
        Serialize embedding to string for database storage.

        Args:
            embedding: Embedding vector

        Returns:
            JSON string representation
        """
        return json.dumps(embedding)

    def deserialize_embedding(self, embedding_str: str) -> List[float]:
        """
        Deserialize embedding from database storage.

        Args:
            embedding_str: JSON string representation

        Returns:
            Embedding vector
        """
        if not embedding_str:
            return [0.0] * self.dimensions
        return json.loads(embedding_str)

    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score [-1, 1]
        """
        import math

        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have same dimensions")

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = math.sqrt(sum(a * a for a in embedding1))
        magnitude2 = math.sqrt(sum(b * b for b in embedding2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the singleton embedding service."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
