"""
Batch Embedding Service

Optimizes embedding generation by batching multiple requests and using caching.
Reduces API calls and improves performance for memory operations.
"""

import logging
from typing import List
from openai import AsyncOpenAI
from backend.services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class BatchEmbeddingService:
    """Optimized embedding service with batching and caching"""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str = "text-embedding-3-large",
        dimensions: int = 1536,
        batch_size: int = 100,  # OpenAI allows up to 2048 inputs per request
    ):
        self.client = client
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text with caching"""
        # Check cache first
        cached_embeddings, uncached_texts = cache_manager.get_cached_embeddings([text])
        if cached_embeddings[0] is not None:
            logger.debug(f"[EMBED] Cache HIT for text: {text[:50]}...")
            return cached_embeddings[0]

        # Generate embedding via API
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        Uses caching and batching to minimize API calls.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (same order as input texts)
        """
        if not texts:
            return []

        # Check cache for existing embeddings
        cached_embeddings, uncached_texts = cache_manager.get_cached_embeddings(texts)

        if not uncached_texts:
            # All embeddings found in cache
            logger.info(f"[EMBED] All {len(texts)} embeddings found in cache")
            return [emb for emb in cached_embeddings if emb is not None]

        logger.info(
            f"[EMBED] Cache hit: {len(texts) - len(uncached_texts)}/{len(texts)}, generating {len(uncached_texts)} new embeddings"
        )

        # Generate embeddings for uncached texts in batches
        new_embeddings = []
        for i in range(0, len(uncached_texts), self.batch_size):
            batch_texts = uncached_texts[i : i + self.batch_size]
            batch_embeddings = await self._generate_embeddings_batch(batch_texts)
            new_embeddings.extend(batch_embeddings)

        # Cache the newly generated embeddings
        if new_embeddings:
            cache_manager.cache_embeddings(uncached_texts, new_embeddings)
            logger.debug(f"[EMBED] Cached {len(new_embeddings)} new embeddings")

        # Merge cached and new embeddings in original order
        result = []
        new_idx = 0

        for cached_emb in cached_embeddings:
            if cached_emb is not None:
                result.append(cached_emb)
            else:
                result.append(new_embeddings[new_idx])
                new_idx += 1

        return result

    async def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via OpenAI API in a single batch request"""
        try:
            logger.debug(f"[EMBED] API call for batch of {len(texts)} texts")
            response = await self.client.embeddings.create(
                model=self.model, input=texts, dimensions=self.dimensions
            )

            embeddings = [item.embedding for item in response.data]
            logger.debug(f"[EMBED] Successfully generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"[EMBED] Batch embedding generation failed: {e}")
            # Fallback to individual requests if batch fails
            logger.info("[EMBED] Falling back to individual embedding requests")
            return await self._generate_embeddings_individual(texts)

    async def _generate_embeddings_individual(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Fallback: generate embeddings one by one"""
        embeddings = []

        for text in texts:
            try:
                response = await self.client.embeddings.create(
                    model=self.model, input=text, dimensions=self.dimensions
                )
                embeddings.append(response.data[0].embedding)

            except Exception as e:
                logger.error(
                    f"[EMBED] Individual embedding failed for text: {text[:50]}... Error: {e}"
                )
                # Return zero vector as fallback
                embeddings.append([0.0] * self.dimensions)

        return embeddings

    async def embed_chunks_for_node(self, chunks: List[str]) -> List[str]:
        """
        Generate embeddings for node chunks and return PostgreSQL-formatted strings.

        Args:
            chunks: List of text chunks

        Returns:
            List of PostgreSQL array strings for embeddings
        """
        embeddings = await self.embed_batch(chunks)

        # Convert to PostgreSQL array format
        embedding_strs = []
        for embedding in embeddings:
            embedding_str = f"[{','.join(map(str, embedding))}]"
            embedding_strs.append(embedding_str)

        return embedding_strs


# Factory function to create batch embedding service
def create_batch_embedding_service(client: AsyncOpenAI) -> BatchEmbeddingService:
    """Create a configured batch embedding service"""
    return BatchEmbeddingService(
        client=client,
        model="text-embedding-3-large",
        dimensions=1536,
        batch_size=50,  # Conservative batch size to avoid rate limits
    )
