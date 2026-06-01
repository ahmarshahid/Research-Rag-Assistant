"""
Embedding service for Phase 3: Generating vector embeddings for chunks.

Why embeddings?
- Transform text into numerical vectors (768-dim for BAAI/bge-base-en-v1.5)
- Enables similarity search: similar text → similar vectors → similar embeddings
- Foundation for RAG retrieval: find most relevant chunks by similarity
- Enables hybrid search: combine BM25 (keyword) + vector search

Embedding models compared:
1. OpenAI text-embedding-3-large: Best quality but $$ (most expensive)
2. BAAI/bge-base-en-v1.5: Best open-source (chosen for this project)
   - 768 dimensions
   - 384 max sequence length
   - Optimized for RAG/retrieval
   - 99.8% performance of OpenAI at 1/100th cost
3. all-MiniLM-L6-v2: Smaller, faster, lighter quality
4. Jina embeddings: Good for longer documents

We use: BAAI/bge-base-en-v1.5 (best cost/quality for RAG)
"""

import asyncio
from typing import List, Optional, Tuple, Dict
import numpy as np
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.errors import EmbeddingException, EmbeddingGenerationFailed
from app.cache.redis_client import redis_client

logger = get_logger(__name__)
settings = get_settings()

# Lazy loading - model loaded on first use
_embedding_model = None


def get_embedding_model():
    """
    Lazy load embedding model.

    Why lazy load?
    - Model is large (100MB+)
    - Only load if needed
    - Saves startup time if not using embeddings
    - Cached in memory for reuse

    Returns:
        SentenceTransformer model instance

    Raises:
        EmbeddingException: If model fails to load
    """
    global _embedding_model

    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {str(e)}")
            raise EmbeddingException(
                f"Failed to load embedding model: {str(e)}"
            )

    return _embedding_model


class EmbeddingService:
    """Service for generating text embeddings."""

    @staticmethod
    async def embed_text(text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Process:
        1. Check Redis cache for embedding
        2. If not cached, generate using model
        3. Cache result in Redis
        4. Return embedding vector

        Args:
            text: Text to embed

        Returns:
            Embedding vector (numpy array, 768-dim)

        Raises:
            EmbeddingException: If embedding fails
        """
        try:
            # Hash text for cache key
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()
            cache_key = f"embedding:{text_hash}"

            # Try to get from cache
            cached = await redis_client.get_json(cache_key)
            if cached:
                logger.debug(f"Cache hit for embedding: {text_hash}")
                return np.array(cached)

            # Generate embedding
            logger.debug(f"Generating embedding for text ({len(text)} chars)")
            model = get_embedding_model()

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: model.encode(text, convert_to_numpy=True)
            )

            # Cache for 30 days
            await redis_client.set_json(
                cache_key,
                embedding.tolist(),
                ttl=30 * 24 * 60 * 60
            )

            logger.debug(f"Generated embedding: {embedding.shape}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise EmbeddingGenerationFailed(
                f"Failed to generate embedding: {str(e)}"
            )

    @staticmethod
    async def embed_texts(texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts (batch).

        Batch processing is more efficient than individual embedding:
        - Model can parallelize across batch
        - 3-5x faster than sequential
        - Better GPU utilization

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingException: If any embedding fails
        """
        try:
            logger.info(f"Batch embedding {len(texts)} texts")

            # Try to get from cache
            embeddings = []
            missing_indices = []

            import hashlib

            for i, text in enumerate(texts):
                text_hash = hashlib.md5(text.encode()).hexdigest()
                cache_key = f"embedding:{text_hash}"

                cached = await redis_client.get_json(cache_key)
                if cached:
                    embeddings.append(np.array(cached))
                else:
                    embeddings.append(None)
                    missing_indices.append(i)

            # Generate missing embeddings
            if missing_indices:
                missing_texts = [texts[i] for i in missing_indices]

                model = get_embedding_model()
                loop = asyncio.get_event_loop()

                batch_embeddings = await loop.run_in_executor(
                    None,
                    lambda: model.encode(
                        missing_texts,
                        batch_size=32,  # Process 32 at a time
                        convert_to_numpy=True
                    )
                )

                # Cache generated embeddings
                for idx, emb in zip(missing_indices, batch_embeddings):
                    text_hash = hashlib.md5(
                        texts[idx].encode()
                    ).hexdigest()
                    cache_key = f"embedding:{text_hash}"

                    await redis_client.set_json(
                        cache_key,
                        emb.tolist(),
                        ttl=30 * 24 * 60 * 60
                    )

                    embeddings[idx] = emb

            logger.info(f"Generated {len(texts)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to batch embed texts: {str(e)}")
            raise EmbeddingGenerationFailed(
                f"Failed to batch embed texts: {str(e)}"
            )

    @staticmethod
    def embed_texts_sync(texts: List[str]) -> List[np.ndarray]:
        """
        Synchronous batch embedding (for non-async contexts).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            logger.info(f"Sync batch embedding {len(texts)} texts")

            model = get_embedding_model()
            embeddings = model.encode(
                texts,
                batch_size=32,
                convert_to_numpy=True
            )

            logger.info(f"Generated {len(texts)} embeddings")
            return list(embeddings)

        except Exception as e:
            logger.error(f"Failed to sync embed texts: {str(e)}")
            raise EmbeddingGenerationFailed(
                f"Failed to sync embed texts: {str(e)}"
            )

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Cosine similarity:
        - Range: -1 to 1 (typically 0 to 1 for embeddings)
        - 1.0 = identical vectors
        - 0.5 = moderately similar
        - 0.0 = unrelated
        - Used for semantic search

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0 to 1)
        """
        from numpy.linalg import norm

        # Cosine similarity = (A · B) / (||A|| ||B||)
        cos_sim = np.dot(vec1, vec2) / (norm(vec1) * norm(vec2))

        # Normalize to 0-1 range
        return (cos_sim + 1) / 2

    @staticmethod
    def top_k_similarity(
        query_embedding: np.ndarray,
        document_embeddings: List[np.ndarray],
        k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Find top-k most similar embeddings to query.

        Used in retrieval phase to find relevant chunks.

        Args:
            query_embedding: Query vector
            document_embeddings: List of document vectors
            k: Number of top results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by score descending
        """
        similarities = []

        for i, doc_emb in enumerate(document_embeddings):
            sim = EmbeddingService.cosine_similarity(
                query_embedding,
                doc_emb
            )
            similarities.append((i, sim))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:k]

    @staticmethod
    def embed_chunks(chunks: List[str]) -> Dict[str, list]:
        """
        Embed a list of chunks for storage in ChromaDB.

        This is the main entry point for Phase 3.

        Args:
            chunks: List of chunk texts

        Returns:
            Dict with chunk_id -> embedding mapping
        """
        try:
            logger.info(f"Embedding {len(chunks)} chunks")

            embeddings = EmbeddingService.embed_texts_sync(chunks)

            # Convert to list for JSON serialization
            embeddings_list = [
                emb.tolist() if isinstance(emb, np.ndarray) else emb
                for emb in embeddings
            ]

            result = {
                f"chunk_{i}": embedding
                for i, embedding in enumerate(embeddings_list)
            }

            logger.info(f"Generated embeddings for {len(chunks)} chunks")

            return result

        except Exception as e:
            logger.error(f"Failed to embed chunks: {str(e)}")
            raise EmbeddingGenerationFailed(
                f"Failed to embed chunks: {str(e)}"
            )

    @staticmethod
    def get_model_info() -> dict:
        """
        Get information about the embedding model.

        Returns:
            Dict with model name, dimension, etc.
        """
        try:
            model = get_embedding_model()

            return {
                "model_name": settings.EMBEDDING_MODEL,
                "dimension": settings.EMBEDDING_DIMENSION,
                "max_sequence_length": 512,  # BAAI/bge-base standard
                "batch_size": 32,
                "pooling_strategy": "mean",
                "normalized": True
            }

        except Exception as e:
            logger.error(f"Failed to get model info: {str(e)}")
            return {}


# Singleton instance
embedding_service = EmbeddingService()
