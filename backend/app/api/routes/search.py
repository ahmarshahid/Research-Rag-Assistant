"""
API routes for Phase 4-8: ChromaDB Vector Search + Advanced Retrieval.

Endpoints:
- POST /api/search/init-collection - Initialize ChromaDB collection for document
- POST /api/search/vector - Semantic search by vector
- POST /api/search/text - Search by query text (converts to embedding)
- POST /api/search/hybrid - Hybrid search (semantic + BM25 + reranking)
- POST /api/search/bm25 - BM25 keyword search
- POST /api/search/rerank - Rerank results with cross-encoder
- GET /api/search/collections - List all collections
- GET /api/search/collections/{id} - Get collection info
- DELETE /api/search/collections/{id} - Delete collection

Phase 8 (Advanced Retrieval):
- Hybrid search combining semantic + keyword matching
- Cross-encoder reranking for better relevance
- BM25 keyword-based search
- Optional web search integration

Design:
- Creates collection when document is chunked
- Automatically inserts chunks from Phase 3
- Fast semantic search across documents
- Metadata filtering support
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field as PydanticField
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_id
from app.dependencies import get_db
from app.models.database import Chunk, Document
from app.models.schemas import (
    CollectionInfoResponse,
    CollectionsListResponse,
    ErrorResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.services.bm25_search_service import BM25SearchException, bm25_search_service
from app.services.cross_encoder_reranker import (
    RerankerException,
    cross_encoder_reranker,
)
from app.services.document_service import document_service
from app.services.embedding_service import embedding_service
from app.services.hybrid_search_service import (
    HybridSearchException,
    hybrid_search_service,
)
from app.services.vectordb_service import (
    SearchException,
    VectorDBException,
    vectordb_service,
)
from app.utils.errors import DatabaseException, DocumentNotFound
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["search"])
logger = get_logger(__name__)


@router.post(
    "/search/init-collection",
    response_model=dict,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid document"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "ChromaDB error"},
    },
)
async def initialize_collection(
    document_id: UUID = Query(..., description="Document ID to initialize"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Initialize ChromaDB collection for a document.

    This is called after Phase 3 (chunking + embedding).
    It creates a collection and inserts all chunks with embeddings.

    What happens:
    1. Verify document exists and chunks are embedded
    2. Create ChromaDB collection named "doc_{uuid}"
    3. Fetch all chunks with embeddings from database
    4. Insert into ChromaDB with metadata
    5. Return collection info

    Why separate endpoint?
    - Decouples chunk processing from vector store initialization
    - Allows manual re-indexing if needed
    - Persists even if API restarts

    Response (201 Created):
    ```json
    {
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "collection_name": "doc_550e8400",
        "status": "initialized",
        "chunks_indexed": 42,
        "embeddings_indexed": 42
    }
    ```
    """
    try:
        logger.info(f"Initializing ChromaDB collection for document {document_id}")

        # Step 1: Verify document exists and user owns it
        document = await document_service.get_document(
            db=db, document_id=document_id, user_id=user_id
        )

        collection_name = f"doc_{document_id}"

        # Step 2: Create ChromaDB collection
        collection_info = await vectordb_service.create_collection(
            collection_name=collection_name,
            metadata={
                "document_id": str(document_id),
                "filename": document.filename,
                "page_count": document.page_count,
            },
        )

        # Step 3: Fetch all chunks for this document with embeddings
        result = await db.execute(
            select(Chunk)
            .where((Chunk.document_id == document_id) & (Chunk.embedding.isnot(None)))
            .order_by(Chunk.chunk_index)
        )
        chunks = result.scalars().all()

        if not chunks:
            logger.warning(f"No embedded chunks found for document {document_id}")
            return {
                "document_id": str(document_id),
                "collection_name": collection_name,
                "status": "created_empty",
                "chunks_indexed": 0,
                "embeddings_indexed": 0,
            }

        # Step 4: Insert chunks into ChromaDB
        insertion_info = await vectordb_service.insert_chunks(
            collection_name=collection_name,
            documents=[chunk.text for chunk in chunks],
            embeddings=[chunk.embedding for chunk in chunks],
            metadatas=[
                {
                    "chunk_id": str(chunk.id),
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "tokens_estimated": chunk.tokens_estimated,
                }
                for chunk in chunks
            ],
            ids=[str(chunk.id) for chunk in chunks],
        )

        logger.info(
            f"Successfully initialized collection {collection_name} "
            f"with {len(chunks)} chunks"
        )

        return {
            "document_id": str(document_id),
            "collection_name": collection_name,
            "status": "initialized",
            "chunks_indexed": len(chunks),
            "embeddings_indexed": len(chunks),
        }

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except VectorDBException as e:
        logger.error(f"ChromaDB error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ChromaDB error: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post(
    "/search/text",
    response_model=SearchResponse,
    status_code=200,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Search error"},
    },
)
async def search_by_text(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> SearchResponse:
    """
    Search documents using text query (semantic search).

    What happens:
    1. Convert query text to embedding using same model as chunks
    2. Search ChromaDB collection
    3. Return results with similarity scores
    4. Optionally filter by page/metadata

    Query embedding is cached in Redis like chunk embeddings.

    Request:
    ```json
    {
        "query": "What is machine learning?",
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "top_k": 5,
        "min_similarity": 0.7,
        "page_number": null
    }
    ```

    Response:
    ```json
    {
        "query": "What is machine learning?",
        "results": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
                "text": "Machine learning is...",
                "similarity": 0.89,
                "page_number": 5,
                "chunk_index": 12
            }
        ],
        "total": 1,
        "search_time_ms": 45
    }
    ```
    """
    try:
        logger.info(f"Text search: '{request.query}' in document {request.document_id}")

        # Verify document exists
        await document_service.get_document(
            db=db, document_id=request.document_id, user_id=user_id
        )

        # Step 1: Generate embedding for query text
        query_embedding = await embedding_service.embed_text(request.query)

        collection_name = f"doc_{request.document_id}"

        # Step 2: Search ChromaDB
        results = await vectordb_service.search_with_filters(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=request.top_k or 5,
            page_number=request.page_number,
            min_similarity=request.min_similarity,
        )

        # Step 3: Build response
        search_results = [
            SearchResultItem(
                chunk_id=UUID(result["id"]),
                text=result["text"],
                similarity=result["similarity"],
                page_number=result["metadata"].get("page_number"),
                chunk_index=result["metadata"].get("chunk_index"),
                char_start=result["metadata"].get("char_start"),
                char_end=result["metadata"].get("char_end"),
            )
            for result in results
        ]

        logger.info(f"Search returned {len(search_results)} results")

        return SearchResponse(
            query=request.query,
            results=search_results,
            total=len(search_results),
            search_time_ms=0.0,  # TODO: Add timing
        )

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except SearchException as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post(
    "/search/vector",
    response_model=SearchResponse,
    status_code=200,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Search error"},
    },
)
async def search_by_vector(
    document_id: UUID = Query(..., description="Document to search"),
    query_embedding: List[float] = Query(..., description="768-dim embedding vector"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results"),
    min_similarity: Optional[float] = Query(
        None, ge=0, le=1, description="Minimum similarity (0-1)"
    ),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> SearchResponse:
    """
    Search using an embedding vector directly.

    Useful for advanced search scenarios:
    - Multi-query search (combine multiple query embeddings)
    - Cross-document similarity
    - Reranking results

    For simple text search, use POST /search/text instead.
    """
    try:
        logger.info(f"Vector search in document {document_id}")

        # Verify document exists
        await document_service.get_document(
            db=db, document_id=document_id, user_id=user_id
        )

        # Validate embedding dimension
        if len(query_embedding) != 768:
            raise HTTPException(
                status_code=400,
                detail=f"Expected 768-dim embedding, got {len(query_embedding)}",
            )

        collection_name = f"doc_{document_id}"

        # Search ChromaDB
        results = await vectordb_service.search_with_filters(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        search_results = [
            SearchResultItem(
                chunk_id=UUID(result["id"]),
                text=result["text"],
                similarity=result["similarity"],
                page_number=result["metadata"].get("page_number"),
                chunk_index=result["metadata"].get("chunk_index"),
                char_start=result["metadata"].get("char_start"),
                char_end=result["metadata"].get("char_end"),
            )
            for result in results
        ]

        return SearchResponse(
            query="[vector search]",
            results=search_results,
            total=len(search_results),
            search_time_ms=0.0,
        )

    except DocumentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    except SearchException as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get(
    "/search/collections",
    response_model=CollectionsListResponse,
    status_code=200,
    responses={500: {"model": ErrorResponse, "description": "Database error"}},
)
async def list_collections(
    db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)
) -> CollectionsListResponse:
    """
    List all ChromaDB collections accessible by this user.

    Returns collections for documents the user owns.
    """
    try:
        # Get all user documents
        result = await db.execute(select(Document).where(Document.user_id == user_id))
        documents = result.scalars().all()

        collections = []
        for doc in documents:
            collection_name = f"doc_{doc.id}"

            try:
                info = await vectordb_service.get_collection_info(collection_name)
                collections.append(
                    CollectionInfoResponse(
                        name=info["name"],
                        document_id=doc.id,
                        document_filename=doc.filename,
                        chunks_count=info["count"],
                        metadata=info["metadata"],
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Could not get info for collection {collection_name}: {str(e)}"
                )
                continue

        return CollectionsListResponse(collections=collections, total=len(collections))

    except Exception as e:
        logger.error(f"Failed to list collections: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list collections")


@router.get(
    "/search/collections/{document_id}",
    response_model=CollectionInfoResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    },
)
async def get_collection_info(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> CollectionInfoResponse:
    """
    Get ChromaDB collection info for a document.

    Returns:
    - Collection name
    - Number of chunks indexed
    - Metadata
    """
    try:
        # Verify user owns document
        document = await document_service.get_document(
            db=db, document_id=document_id, user_id=user_id
        )

        collection_name = f"doc_{document_id}"
        info = await vectordb_service.get_collection_info(collection_name)

        return CollectionInfoResponse(
            name=info["name"],
            document_id=document_id,
            document_filename=document.filename,
            chunks_count=info["count"],
            metadata=info["metadata"],
        )

    except DocumentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to get collection info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get collection info")


@router.delete(
    "/search/collections/{document_id}",
    response_model=dict,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    },
)
async def delete_collection(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Delete ChromaDB collection for a document.

    Called when document is deleted (Phase 2 DELETE endpoint).
    Cleans up vector store.
    """
    try:
        # Verify user owns document
        await document_service.get_document(
            db=db, document_id=document_id, user_id=user_id
        )

        collection_name = f"doc_{document_id}"
        result = await vectordb_service.delete_collection(collection_name)

        logger.info(f"Deleted ChromaDB collection for document {document_id}")

        return {
            "document_id": str(document_id),
            "collection_name": collection_name,
            "status": "deleted",
        }

    except DocumentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to delete collection: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete collection")


# ============================================================================
# Phase 8: Advanced Retrieval Features (Hybrid Search, BM25, Reranking)
# ============================================================================


@router.post(
    "/search/hybrid",
    response_model=dict,
    status_code=200,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Search error"},
    },
)
async def hybrid_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Hybrid search combining semantic + BM25 + cross-encoder reranking.

    This is the recommended search method for best results.

    Workflow:
    1. Get candidates from semantic search (50 results)
    2. Get candidates from BM25 keyword search (50 results)
    3. Merge and deduplicate
    4. Rerank with cross-encoder model
    5. Return top_k results

    Benefits:
    - Semantic search for meaning-based retrieval
    - BM25 for exact phrase matching
    - Cross-encoder for accurate relevance ranking
    - Hybrid approach covers all query types

    Request:
    ```json
    {
        "query": "What is machine learning?",
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "top_k": 5
    }
    ```

    Response:
    ```json
    {
        "query": "What is machine learning?",
        "results": [
            {
                "chunk_id": "550e8400-e29b-41d4-a716-446655440001",
                "text": "Machine learning is...",
                "semantic_score": 0.85,
                "bm25_score": 0.72,
                "rerank_score": 0.92,
                "hybrid_score": 0.82,
                "page_number": 5,
                "source": "document"
            }
        ],
        "total": 1,
        "search_time_ms": 245
    }
    ```
    """
    try:
        logger.info(f"Hybrid search for: '{request.query}'")

        # Verify document exists
        await document_service.get_document(
            db=db, document_id=request.document_id, user_id=user_id
        )

        # Perform hybrid search
        result = await hybrid_search_service.search(
            db=db,
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k or 5,
            include_web=False,
            semantic_top_k=50,
            bm25_top_k=50,
        )

        logger.info(f"Hybrid search returned {result['total']} results")
        return result

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except HybridSearchException as e:
        logger.error(f"Hybrid search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post(
    "/search/bm25",
    response_model=dict,
    status_code=200,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Search error"},
    },
)
async def bm25_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    BM25 keyword-based search.

    BM25 (Best Matching 25) is a probabilistic relevance framework
    that scores documents based on term frequency and inverse document frequency.

    Use when:
    - Looking for exact phrases
    - Query has specific keywords
    - Need fast keyword-based search
    - Semantic search doesn't work well

    Response:
    ```json
    {
        "results": [
            {
                "chunk_id": "...",
                "text": "...",
                "score": 8.5,
                "page_number": 5
            }
        ],
        "total": 1
    }
    ```
    """
    try:
        logger.info(f"BM25 search for: '{request.query}'")

        # Verify document exists
        await document_service.get_document(
            db=db, document_id=request.document_id, user_id=user_id
        )

        # Perform BM25 search
        results = await bm25_search_service.search(
            db=db,
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k or 5,
        )

        logger.info(f"BM25 search returned {len(results)} results")

        return {
            "query": request.query,
            "results": results,
            "total": len(results),
            "search_type": "bm25",
        }

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except BM25SearchException as e:
        logger.error(f"BM25 search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


class RerankRequest(PydanticBaseModel):
    """Request body for reranking candidates."""

    query: str
    candidates: List[dict]
    top_k: Optional[int] = PydanticField(
        None, le=50, description="Return top k results"
    )


@router.post(
    "/search/rerank",
    response_model=dict,
    status_code=200,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid candidates"},
        500: {"model": ErrorResponse, "description": "Reranking error"},
    },
)
async def rerank_results(
    request: RerankRequest,
) -> dict:
    """
    Rerank search results using cross-encoder model.

    Takes search candidates and scores them with a cross-encoder
    for better relevance ranking.

    Use when:
    - You have many candidate results
    - Want to rerank existing search results
    - Combining results from multiple sources

    Request:
    ```json
    {
        "query": "What is AI?",
        "candidates": [
            {"text": "Artificial Intelligence is...", "chunk_id": "..."},
            {"text": "AI refers to...", "chunk_id": "..."}
        ],
        "top_k": 2
    }
    ```

    Response:
    ```json
    {
        "query": "What is AI?",
        "results": [
            {
                "text": "Artificial Intelligence is...",
                "rerank_score": 0.95,
                "rank": 1
            }
        ]
    }
    ```
    """
    try:
        logger.info(f"Reranking {len(request.candidates)} candidates")

        # Rerank candidates
        reranked = await cross_encoder_reranker.rerank(
            query=request.query, candidates=request.candidates, top_k=request.top_k
        )

        # Add rank position
        for idx, result in enumerate(reranked, 1):
            result["rank"] = idx

        logger.info(f"Reranking complete: {len(reranked)} results")

        return {"query": request.query, "results": reranked, "total": len(reranked)}

    except RerankerException as e:
        logger.error(f"Reranking error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reranking failed: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
