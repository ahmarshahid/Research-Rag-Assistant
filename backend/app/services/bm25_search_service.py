"""
BM25 Search Service - Phase 8: Advanced Retrieval

Provides keyword-based search using BM25 algorithm (Okapi BM25).
Used in hybrid search along with semantic search for better recall.

Features:
- Fast keyword matching
- TF-IDF scoring
- Configurable parameters (k1, b)
- Integration with semantic search for hybrid ranking
"""

from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID
import logging
from collections import defaultdict

from app.models.database import Chunk, Document
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BM25SearchException(Exception):
    """BM25 search specific exception"""
    pass


class BM25SearchService:
    """
    BM25 search service for keyword-based document retrieval.

    BM25 (Best Matching 25) is a probabilistic relevance framework
    that combines TF (term frequency) and IDF (inverse document frequency).

    Parameters:
    - k1: Controls term frequency saturation (default 1.5)
      Higher k1 = more weight to term frequency
    - b: Controls length normalization (default 0.75)
      b=0: No normalization
      b=1: Full normalization
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 search service."""
        self.k1 = k1
        self.b = b
        self.corpus_cache: Dict[UUID, BM25Okapi] = {}
        self.doc_metadata: Dict[UUID, List[Dict[str, Any]]] = {}

    async def build_corpus(
        self,
        db: AsyncSession,
        document_id: UUID
    ) -> BM25Okapi:
        """
        Build BM25 corpus from document chunks.

        Args:
            db: Database session
            document_id: Document to build corpus for

        Returns:
            BM25Okapi object ready for searching

        Raises:
            BM25SearchException: If corpus building fails
        """
        try:
            logger.info(f"Building BM25 corpus for document {document_id}")

            # Fetch all chunks for this document
            result = await db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            )
            chunks = result.scalars().all()

            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                raise BM25SearchException(
                    f"No chunks found for document {document_id}")

            # Tokenize chunks (simple whitespace tokenization)
            corpus = [self._tokenize(chunk.text) for chunk in chunks]

            # Build BM25 model
            bm25 = BM25Okapi(corpus, k1=self.k1, b=self.b)

            # Store metadata for later retrieval
            metadata = [
                {
                    "chunk_id": str(chunk.id),
                    "text": chunk.text,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "tokens_estimated": chunk.tokens_estimated
                }
                for chunk in chunks
            ]

            # Cache for future searches
            self.corpus_cache[document_id] = bm25
            self.doc_metadata[document_id] = metadata

            logger.info(f"Built BM25 corpus with {len(chunks)} chunks")
            return bm25

        except Exception as e:
            logger.error(f"Error building BM25 corpus: {str(e)}")
            raise BM25SearchException(f"Failed to build corpus: {str(e)}")

    async def search(
        self,
        db: AsyncSession,
        document_id: UUID,
        query: str,
        top_k: int = 5,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search document using BM25 algorithm.

        Args:
            db: Database session
            document_id: Document to search
            query: Search query (keywords)
            top_k: Number of top results to return
            use_cache: Use cached corpus if available

        Returns:
            List of results with scores, sorted by relevance

        Result format:
            {
                "chunk_id": "...",
                "text": "...",
                "score": 8.5,  # BM25 score
                "page_number": 5,
                "chunk_index": 12,
                ...
            }
        """
        try:
            logger.info(f"BM25 search for: '{query}'")

            # Get or build corpus
            if use_cache and document_id in self.corpus_cache:
                bm25 = self.corpus_cache[document_id]
                metadata = self.doc_metadata[document_id]
            else:
                bm25 = await self.build_corpus(db, document_id)
                metadata = self.doc_metadata[document_id]

            # Tokenize query
            query_tokens = self._tokenize(query)

            if not query_tokens:
                logger.warning("Empty query after tokenization")
                return []

            # Get BM25 scores
            scores = bm25.get_scores(query_tokens)

            # Create results with metadata
            results = []
            for idx, score in enumerate(scores):
                if score > 0:  # Only include chunks with positive score
                    result = metadata[idx].copy()
                    result["score"] = float(score)
                    results.append(result)

            # Sort by score descending
            results.sort(key=lambda x: x["score"], reverse=True)

            # Return top_k results
            top_results = results[:top_k]
            logger.info(f"BM25 search returned {len(top_results)} results")

            return top_results

        except BM25SearchException:
            raise
        except Exception as e:
            logger.error(f"BM25 search error: {str(e)}", exc_info=True)
            raise BM25SearchException(f"Search failed: {str(e)}")

    async def search_multiple_documents(
        self,
        db: AsyncSession,
        document_ids: List[UUID],
        query: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple documents using BM25.

        Args:
            db: Database session
            document_ids: List of documents to search
            query: Search query
            top_k: Number of top results total

        Returns:
            Combined results from all documents, sorted by score
        """
        try:
            logger.info(
                f"BM25 multi-doc search for '{query}' across {len(document_ids)} documents")

            all_results = []

            for doc_id in document_ids:
                try:
                    results = await self.search(db, doc_id, query, top_k=100)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(
                        f"Error searching document {doc_id}: {str(e)}")
                    continue

            # Sort by score and return top_k
            all_results.sort(key=lambda x: x["score"], reverse=True)
            return all_results[:top_k]

        except Exception as e:
            logger.error(f"Multi-document BM25 search error: {str(e)}")
            raise BM25SearchException(f"Multi-doc search failed: {str(e)}")

    async def clear_cache(self, document_id: Optional[UUID] = None):
        """
        Clear cached corpus.

        Args:
            document_id: Specific document to clear, or None for all
        """
        if document_id:
            self.corpus_cache.pop(document_id, None)
            self.doc_metadata.pop(document_id, None)
            logger.info(f"Cleared BM25 cache for document {document_id}")
        else:
            self.corpus_cache.clear()
            self.doc_metadata.clear()
            logger.info("Cleared all BM25 cache")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        Simple whitespace tokenization with lowercase conversion.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Convert to lowercase and split by whitespace
        tokens = text.lower().split()

        # Remove empty tokens and very short tokens
        tokens = [t for t in tokens if len(t) > 2]

        return tokens

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cached_documents": len(self.corpus_cache),
            "total_chunks_cached": sum(
                len(meta) for meta in self.doc_metadata.values()
            )
        }


# Singleton instance
bm25_search_service = BM25SearchService()
