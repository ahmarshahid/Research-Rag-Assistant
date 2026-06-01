"""
Hybrid Search Service - Phase 8: Advanced Retrieval

Combines multiple search strategies for optimal results:
1. Semantic search (vector embeddings) - best for meaning
2. BM25 (keyword matching) - best for exact terms
3. Cross-encoder reranking - best for final ranking
4. Web search (optional) - augment with external knowledge

Workflow:
1. Get candidates from semantic search (50 results)
2. Get candidates from BM25 (50 results)
3. Merge and deduplicate
4. Rerank with cross-encoder
5. Return top_k results

Benefits:
- Recall: Combines semantic + keyword matching
- Precision: Cross-encoder reranking improves relevance
- Hybrid: Covers different query types
- Fast: Caches BM25 corpus and runs async
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import asyncio

from app.services.vectordb_service import vectordb_service
from app.services.embedding_service import embedding_service
from app.services.bm25_search_service import bm25_search_service
from app.services.cross_encoder_reranker import cross_encoder_reranker
from app.services.web_search_service import web_search_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HybridSearchException(Exception):
    """Hybrid search specific exception"""
    pass


class HybridSearchService:
    """
    Hybrid search combining semantic + keyword + reranking.
    """

    def __init__(
        self,
        semantic_weight: float = 0.5,
        bm25_weight: float = 0.3,
        rerank_weight: float = 0.2,
        use_reranking: bool = True,
        use_web_search: bool = False
    ):
        """
        Initialize hybrid search.

        Args:
            semantic_weight: Weight for semantic search (0-1)
            bm25_weight: Weight for BM25 search (0-1)
            rerank_weight: Weight for cross-encoder (0-1)
            use_reranking: Enable cross-encoder reranking
            use_web_search: Include web search results
        """
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.rerank_weight = rerank_weight
        self.use_reranking = use_reranking
        self.use_web_search = use_web_search

    async def search(
        self,
        db: AsyncSession,
        document_id: UUID,
        query: str,
        top_k: int = 10,
        include_web: bool = False,
        semantic_top_k: int = 50,
        bm25_top_k: int = 50
    ) -> Dict[str, Any]:
        """
        Perform hybrid search.

        Args:
            db: Database session
            document_id: Document to search
            query: Search query
            top_k: Final number of results
            include_web: Include web search results
            semantic_top_k: Candidates from semantic search
            bm25_top_k: Candidates from BM25 search

        Returns:
            Hybrid search results with combined ranking

        Result format:
            {
                "query": "...",
                "results": [
                    {
                        "chunk_id": "...",
                        "text": "...",
                        "semantic_score": 0.85,
                        "bm25_score": 8.5,
                        "rerank_score": 0.92,
                        "hybrid_score": 0.89,  # Combined score
                        "page_number": 5,
                        "source": "document"
                    }
                ],
                "total": 10,
                "search_time_ms": 245
            }
        """
        try:
            import time
            start_time = time.time()

            logger.info(f"Hybrid search for: '{query}'")

            # Step 1: Parallel semantic + BM25 search
            semantic_results, bm25_results = await asyncio.gather(
                self._semantic_search(db, document_id, query, semantic_top_k),
                self._bm25_search(db, document_id, query, bm25_top_k),
                return_exceptions=True
            )

            # Handle exceptions
            if isinstance(semantic_results, Exception):
                logger.warning(f"Semantic search failed: {semantic_results}")
                semantic_results = []

            if isinstance(bm25_results, Exception):
                logger.warning(f"BM25 search failed: {bm25_results}")
                bm25_results = []

            logger.info(
                f"Got {len(semantic_results)} semantic + {len(bm25_results)} BM25 results"
            )

            # Step 2: Merge and deduplicate
            merged_results = self._merge_results(
                semantic_results,
                bm25_results,
                semantic_weight=self.semantic_weight,
                bm25_weight=self.bm25_weight
            )

            logger.info(f"Merged to {len(merged_results)} unique results")

            # Step 3: Optional reranking
            if self.use_reranking and merged_results:
                try:
                    reranked = await cross_encoder_reranker.rerank(
                        query,
                        merged_results,
                        top_k=top_k
                    )

                    # Add rerank score to results
                    for result in reranked:
                        result["rerank_score"] = result.get(
                            "rerank_score", 0.0)

                    merged_results = reranked
                    logger.info(f"Reranked to {len(reranked)} results")

                except Exception as e:
                    logger.warning(
                        f"Reranking failed, using original results: {e}")

            # Step 4: Optional web search
            web_results = []
            if include_web and web_search_service.is_enabled():
                try:
                    web_results = await web_search_service.search(
                        query,
                        num_results=3
                    )

                    # Tag web results
                    for result in web_results:
                        result["source"] = "web"

                    logger.info(f"Added {len(web_results)} web results")

                except Exception as e:
                    logger.warning(f"Web search failed: {e}")

            # Step 5: Combine and finalize
            final_results = merged_results[:top_k]

            # Add web results if space available
            if web_results:
                remaining_slots = max(0, top_k - len(final_results))
                final_results.extend(web_results[:remaining_slots])

            elapsed_ms = (time.time() - start_time) * 1000

            return {
                "query": query,
                "results": final_results,
                "total": len(final_results),
                "search_time_ms": elapsed_ms,
                "components": {
                    "semantic_results": len(semantic_results),
                    "bm25_results": len(bm25_results),
                    "web_results": len(web_results),
                    "reranked": self.use_reranking
                }
            }

        except Exception as e:
            logger.error(f"Hybrid search error: {str(e)}", exc_info=True)
            raise HybridSearchException(f"Hybrid search failed: {str(e)}")

    async def _semantic_search(
        self,
        db: AsyncSession,
        document_id: UUID,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Semantic search using vector embeddings."""
        try:
            # Generate query embedding
            query_embedding = await embedding_service.embed_text(query)

            collection_name = f"doc_{document_id}"

            # Search ChromaDB
            results = await vectordb_service.search_with_filters(
                collection_name=collection_name,
                query_embedding=query_embedding,
                top_k=top_k,
                min_similarity=0.0
            )

            # Add source tag
            for result in results:
                result["source"] = "document"
                result["semantic_score"] = result.get("similarity", 0.0)

            return results

        except Exception as e:
            logger.error(f"Semantic search error: {str(e)}")
            return []

    async def _bm25_search(
        self,
        db: AsyncSession,
        document_id: UUID,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """BM25 search using keyword matching."""
        try:
            results = await bm25_search_service.search(
                db=db,
                document_id=document_id,
                query=query,
                top_k=top_k
            )

            # Normalize scores to 0-1 range (BM25 can go higher)
            max_score = max([r.get("score", 0) for r in results], default=1.0)
            if max_score > 0:
                for result in results:
                    result["bm25_score"] = result.get("score", 0) / max_score
                    result["source"] = "document"

            return results

        except Exception as e:
            logger.error(f"BM25 search error: {str(e)}")
            return []

    @staticmethod
    def _merge_results(
        semantic_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        semantic_weight: float = 0.5,
        bm25_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Merge semantic and BM25 results.

        Deduplicates by chunk_id and combines scores.
        """
        # Create lookup by chunk_id
        merged = {}

        for result in semantic_results:
            chunk_id = result.get("id") or result.get("chunk_id")
            if chunk_id not in merged:
                merged[chunk_id] = result
            merged[chunk_id]["semantic_score"] = result.get(
                "semantic_score", result.get("similarity", 0))

        for result in bm25_results:
            chunk_id = result.get("chunk_id")
            if chunk_id not in merged:
                merged[chunk_id] = result
            merged[chunk_id]["bm25_score"] = result.get("bm25_score", 0)

        # Calculate hybrid scores
        results = []
        for chunk_id, result in merged.items():
            semantic = result.get("semantic_score", 0)
            bm25 = result.get("bm25_score", 0)

            # Weighted combination
            hybrid_score = (
                semantic * semantic_weight +
                bm25 * bm25_weight
            )

            result["hybrid_score"] = hybrid_score
            results.append(result)

        # Sort by hybrid score
        results.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)

        return results


# Singleton instance
hybrid_search_service = HybridSearchService(
    use_reranking=True,
    use_web_search=False  # Disabled by default, enable with environment variable
)
