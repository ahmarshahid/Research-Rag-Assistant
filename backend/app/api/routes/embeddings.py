"""
API routes for Phase 3: Chunking and Embeddings.

Endpoints:
- POST /api/chunks/process - Process document (chunk + embed)
- GET /api/chunks/document/{id} - Get all chunks for document
- GET /api/chunks/{chunk_id} - Get specific chunk
- GET /api/embeddings/status/{doc_id} - Check embedding status

Design:
- Immediate feedback on chunk processing
- Background job for embedding generation
- Progress tracking for long-running operations
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import Optional
import hashlib

from app.dependencies import get_db
from app.api.dependencies import get_current_user_id
from app.models.schemas import (
    ChunkRequest,
    ChunkResponse,
    ChunksListResponse,
    EmbeddingProgressResponse,
    EmbeddingStatusResponse,
    ErrorResponse
)
from app.models.database import Document, Chunk
from app.services.document_service import document_service
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.utils.errors import (
    DocumentNotFound,
    DatabaseException,
    EmbeddingException
)
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["embeddings"])
logger = get_logger(__name__)


@router.post(
    "/chunks/process",
    response_model=ChunksListResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid document"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Processing error"},
    }
)
async def process_document_chunking(
    request: ChunkRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> ChunksListResponse:
    """
    Process a document: chunk text and generate embeddings.

    What happens:
    1. Verify document exists and user owns it
    2. Split extracted text into chunks (recursive chunking)
    3. Generate embeddings for each chunk (using batch)
    4. Store chunks with embeddings in database
    5. Return chunks list

    Why batch embedding?
    - 3-5x faster than sequential
    - Better GPU utilization
    - Handles caching automatically

    Request:
    ```json
    {
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "chunk_size": 1024,      // Optional, uses config default
        "chunk_overlap": 128     // Optional, uses config default
    }
    ```

    Response (201 Created):
    ```json
    {
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "chunks": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "text": "chunk text...",
                "page_number": 1,
                "chunk_index": 0,
                "embedding": [0.1, -0.2, ...],  // 768-dim vector
                "created_at": "2026-05-31T12:34:56Z"
            }
        ],
        "total_chunks": 42,
        "total_tokens": 43008
    }
    ```
    """
    try:
        logger.info(
            f"Processing document {request.document_id} for user {user_id}"
        )

        # Step 1: Verify document exists and user owns it
        document = await document_service.get_document(
            db=db,
            document_id=request.document_id,
            user_id=user_id
        )

        if not document.extracted_text:
            raise ValueError("Document has no extracted text")

        # Step 2: Get chunks using recursive chunking
        chunks = chunking_service.chunk_document(
            document_id=str(request.document_id),
            text=document.extracted_text,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )

        logger.info(f"Created {len(chunks)} chunks for document")

        # Step 3: Generate embeddings for all chunks (batch)
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = await embedding_service.embed_texts(chunk_texts)

        logger.info(f"Generated embeddings for {len(chunks)} chunks")

        # Step 4: Store chunks in database
        db_chunks = []
        total_tokens = 0

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Create text hash for deduplication
            text_hash = hashlib.md5(chunk.text.encode()).hexdigest()

            db_chunk = Chunk(
                document_id=request.document_id,
                chunk_index=chunk.metadata.chunk_index,
                text=chunk.text,
                text_hash=text_hash,
                page_number=chunk.metadata.page_number,
                char_start=chunk.metadata.char_start,
                char_end=chunk.metadata.char_end,
                tokens_estimated=chunk.metadata.tokens_estimated,
                embedding=embedding.tolist() if hasattr(
                    embedding, 'tolist'
                ) else embedding,
                embedding_model="BAAI/bge-base-en-v1.5",
                chunk_metadata={
                    "chunk_source": "recursive_chunking",
                    "chunking_method": "recursive",
                    "chunk_size": request.chunk_size,
                    "chunk_overlap": request.chunk_overlap,
                },
            )

            db.add(db_chunk)
            db_chunks.append(db_chunk)
            total_tokens += chunk.metadata.tokens_estimated

        # Flush to generate UUIDs
        await db.flush()

        # Step 5: Return chunks list with embeddings
        chunk_responses = [
            ChunkResponse(
                id=db_chunk.id,
                document_id=db_chunk.document_id,
                text=db_chunk.text,
                page_number=db_chunk.page_number,
                chunk_index=db_chunk.chunk_index,
                metadata=db_chunk.chunk_metadata,
                embedding=db_chunk.embedding,
                created_at=db_chunk.created_at
            )
            for db_chunk in db_chunks
        ]

        logger.info(
            f"Successfully chunked and embedded document {request.document_id}: "
            f"{len(chunks)} chunks, {total_tokens} tokens"
        )

        return ChunksListResponse(
            document_id=request.document_id,
            chunks=chunk_responses,
            total_chunks=len(chunks),
            total_tokens=total_tokens
        )

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except EmbeddingException as e:
        logger.error(f"Embedding error: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Embedding failed: {str(e)}")

    except DatabaseException as e:
        logger.error(f"Database error: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Database error: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.get(
    "/chunks/document/{document_id}",
    response_model=ChunksListResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    }
)
async def get_document_chunks(
    document_id: UUID,
    skip: int = Query(0, ge=0, description="Number of chunks to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max chunks to return"),
    include_embeddings: bool = Query(
        False, description="Include embedding vectors"
    ),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> ChunksListResponse:
    """
    Get all chunks for a document.

    Parameters:
    - skip: Pagination offset
    - limit: Max chunks to return
    - include_embeddings: Include 768-dim vectors (large payload, default False)

    Example:
    ```bash
    # Get first 50 chunks without embeddings
    curl http://localhost:8000/api/chunks/document/{id}

    # Get chunks with embeddings
    curl "http://localhost:8000/api/chunks/document/{id}?include_embeddings=true"
    ```
    """
    try:
        logger.info(
            f"Getting chunks for document {document_id} (skip={skip}, limit={limit})"
        )

        # Verify document exists and user owns it
        document = await document_service.get_document(
            db=db,
            document_id=document_id,
            user_id=user_id
        )

        # Get total count
        count_result = await db.execute(
            select(func.count(Chunk.id)).where(
                Chunk.document_id == document_id
            )
        )
        total_count = count_result.scalar() or 0

        # Get paginated chunks
        result = await db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .offset(skip)
            .limit(limit)
        )
        chunks = result.scalars().all()

        # Calculate total tokens
        total_tokens = sum(chunk.tokens_estimated for chunk in chunks)

        # Build responses
        chunk_responses = [
            ChunkResponse(
                id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                metadata=chunk.chunk_metadata,
                embedding=chunk.embedding if include_embeddings else None,
                created_at=chunk.created_at
            )
            for chunk in chunks
        ]

        return ChunksListResponse(
            document_id=document_id,
            chunks=chunk_responses,
            total_chunks=total_count,
            total_tokens=total_tokens
        )

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.get(
    "/chunks/{chunk_id}",
    response_model=ChunkResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Chunk not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    }
)
async def get_chunk(
    chunk_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> ChunkResponse:
    """
    Get a specific chunk by ID.

    Includes full embedding vector (768-dim).
    """
    try:
        result = await db.execute(
            select(Chunk).where(Chunk.id == chunk_id)
        )
        chunk = result.scalar_one_or_none()

        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found")

        # Verify user owns the document this chunk belongs to
        document = await document_service.get_document(
            db=db,
            document_id=chunk.document_id,
            user_id=user_id
        )

        return ChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            text=chunk.text,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            metadata=chunk.chunk_metadata,
            embedding=chunk.embedding,
            created_at=chunk.created_at
        )

    except DocumentNotFound:
        raise HTTPException(
            status_code=404,
            detail="Chunk not found or access denied"
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.get(
    "/embeddings/status/{document_id}",
    response_model=EmbeddingStatusResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    }
)
async def get_embedding_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> EmbeddingStatusResponse:
    """
    Get embedding status for a document.

    Returns:
    - Number of chunks created
    - Number of chunks with embeddings
    - Embedding model used
    - Embedding dimension (768 for BAAI/bge)

    Example response:
    ```json
    {
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "embedding_model": "BAAI/bge-base-en-v1.5",
        "chunks_count": 42,
        "chunks_embedded": 42,
        "embedding_dimension": 768,
        "created_at": "2026-05-31T12:34:56Z"
    }
    ```
    """
    try:
        # Verify document exists
        document = await document_service.get_document(
            db=db,
            document_id=document_id,
            user_id=user_id
        )

        # Count chunks
        count_result = await db.execute(
            select(func.count(Chunk.id)).where(
                Chunk.document_id == document_id
            )
        )
        total_chunks = count_result.scalar() or 0

        # Count embedded chunks
        embedded_result = await db.execute(
            select(func.count(Chunk.id)).where(
                (Chunk.document_id == document_id) &
                (Chunk.embedding.isnot(None))
            )
        )
        embedded_chunks = embedded_result.scalar() or 0

        return EmbeddingStatusResponse(
            document_id=document_id,
            embedding_model="BAAI/bge-base-en-v1.5",
            chunks_count=total_chunks,
            chunks_embedded=embedded_chunks,
            embedding_dimension=768,
            created_at=document.created_at
        )

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")
