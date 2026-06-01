"""
Cross-Encoder Reranking Service - Phase 8: Advanced Retrieval

Uses cross-encoder models to rerank search results for better relevance.
Cross-encoders directly predict the relevance of a text pair (query, document).

Models:
- cross-encoder/ms-marco-MiniLM-L-12-v2 (fast, ~60MB)
- cross-encoder/qnli-distilroberta-base (QNLI-specific)
- cross-encoder/stsb-distilroberta-base (general similarity)

Workflow:
1. Get candidates from BM25 or semantic search
2. Score each candidate with cross-encoder
3. Rerank by cross-encoder scores
4. Return top results
"""

import asyncio
from typing import Any, Dict, List, Optional

from sentence_transformers.cross_encoder import CrossEncoder

from app.utils.logger import get_logger

logger = get_logger(__name__)


class RerankerException(Exception):
    """Reranker specific exception"""

    pass


class CrossEncoderReranker:
    """
    Cross-encoder based reranking service.

    Cross-encoders take a query-document pair and directly output
    a relevance score (0-1). This is more accurate than separate
    query and document embeddings.

    Trade-off: Slower than embedding-based search but more accurate.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        device: str = "cpu",
    ):
        """
        Initialize cross-encoder reranker.

        Args:
            model_name: Hugging Face model name
            device: Device to run model on (cpu, cuda, mps)
        """
        self.model_name = model_name
        self.device = device
        self.model: Any = None
        self._initialized = False

    async def initialize(self):
        """
        Lazily initialize the model.

        Models are large (~300MB), so we load on first use.
        Initialization happens in background.
        """
        if self._initialized:
            return

        try:
            logger.info(f"Initializing cross-encoder model: {self.model_name}")

            # Load model in background to not block
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, lambda: CrossEncoder(self.model_name, device=self.device)
            )

            self._initialized = True
            logger.info("Cross-encoder model initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize cross-encoder: {str(e)}")
            raise RerankerException(f"Model initialization failed: {str(e)}")

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using cross-encoder.

        Args:
            query: Search query
            candidates: List of candidates to rerank
                Format: [{"text": "...", "chunk_id": "...", ...}, ...]
            top_k: Return only top_k results (optional)
            score_threshold: Minimum score threshold (0-1)

        Returns:
            Reranked candidates with new "rerank_score" field

        Example:
            candidates = [
                {"text": "Machine learning is...", "chunk_id": "123"},
                {"text": "Deep learning involves...", "chunk_id": "456"}
            ]
            result = await reranker.rerank("What is ML?", candidates)
            # Result is sorted by relevance score
        """
        try:
            await self.initialize()

            if not candidates:
                logger.warning("No candidates to rerank")
                return []

            logger.info(
                f"Reranking {len(candidates)} candidates for query: '{query[:50]}...'"
            )

            # Prepare query-document pairs
            pairs = [[query, candidate["text"]] for candidate in candidates]

            # Score pairs with cross-encoder
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(None, lambda: self.model.predict(pairs))

            # Add scores to candidates
            results = []
            for candidate, score in zip(candidates, scores):
                if score >= score_threshold:
                    result = candidate.copy()
                    result["rerank_score"] = float(score)
                    results.append(result)

            # Sort by rerank score (descending)
            results.sort(key=lambda x: x["rerank_score"], reverse=True)

            # Return top_k if specified
            if top_k:
                results = results[:top_k]

            logger.info(f"Reranking complete: {len(results)} results after filtering")

            return results

        except RerankerException:
            raise
        except Exception as e:
            logger.error(f"Reranking error: {str(e)}", exc_info=True)
            raise RerankerException(f"Reranking failed: {str(e)}")

    async def rerank_batch(
        self,
        query: str,
        candidate_batches: List[List[Dict[str, Any]]],
        top_k_per_batch: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rerank multiple batches of candidates.

        Useful when candidates come from multiple sources
        (semantic search, BM25, web search).

        Args:
            query: Search query
            candidate_batches: Multiple lists of candidates
            top_k_per_batch: Top results per batch before combining

        Returns:
            Combined and reranked results
        """
        try:
            logger.info(f"Reranking {len(candidate_batches)} batches")

            all_candidates = []

            # Rerank each batch
            for batch in candidate_batches:
                reranked = await self.rerank(query, batch, top_k=top_k_per_batch)
                all_candidates.extend(reranked)

            # Final rerank across all
            final_results = await self.rerank(query, all_candidates)

            logger.info(f"Batch reranking complete: {len(final_results)} total results")
            return final_results

        except Exception as e:
            logger.error(f"Batch reranking error: {str(e)}")
            raise RerankerException(f"Batch reranking failed: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "initialized": self._initialized,
            "description": (
                "Cross-encoder model for query-document relevance scoring. "
                "More accurate than semantic search but slower."
            ),
        }


# Singleton instance with default model
cross_encoder_reranker = CrossEncoderReranker(
    model_name="cross-encoder/ms-marco-MiniLM-L-12-v2", device="cpu"
)
