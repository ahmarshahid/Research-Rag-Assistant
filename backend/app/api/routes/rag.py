"""
API routes for Phase 5: RAG Retrieval and LLM Response.

Endpoints:
- POST /api/rag/chat - Answer question about document
- POST /api/rag/chat-stream - Stream response tokens
- GET /api/rag/health - Health check for LLM service

Design:
- Simple /chat endpoint for standard Q&A
- /chat-stream for real-time responses
- Combines retrieval (Phase 4) + LLM (Phase 5)
- Citation tracking for accuracy
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
import logging
import json

from app.dependencies import get_db
from app.api.dependencies import get_current_user_id
from app.models.schemas import (
    RAGRequest,
    RAGResponse,
    RAGCitation,
    ErrorResponse
)
from app.services.document_service import document_service
from app.services.rag_service import rag_service, RAGException, LLMException, RetrievalException
from app.utils.errors import DocumentNotFound
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["rag"])
logger = get_logger(__name__)


@router.post(
    "/rag/chat",
    response_model=RAGResponse,
    status_code=200,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    }
)
async def answer_question(
    request: RAGRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> RAGResponse:
    """
    Answer a question about a document using RAG pipeline.

    What happens:
    1. Retrieve relevant chunks from document (Phase 4)
    2. Format as LLM context
    3. Call LLM (GPT-4) with context + query
    4. Extract citations from response
    5. Return response + citations

    Why RAG?
    - Grounds responses in actual document content
    - Enables accurate citations
    - Avoids hallucinations (LLM only uses provided chunks)
    - Cost-effective (retrieve once, generate response)

    Request:
    ```json
    {
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "query": "What is the main topic?",
        "top_k": 5,
        "model": "gpt-4",
        "temperature": 0.7,
        "min_similarity": 0.5
    }
    ```

    Response (200 OK):
    ```json
    {
        "query": "What is the main topic?",
        "response": "The document discusses machine learning...",
        "citations": [
            {
                "chunk_id": "uuid",
                "page_number": 5,
                "text_preview": "Machine learning is..."
            }
        ],
        "retrieved_chunks_count": 5,
        "model": "gpt-4",
        "timestamp": "2026-06-01T12:34:56Z"
    }
    ```
    """
    try:
        logger.info(
            f"RAG query for document {request.document_id}: '{request.query}'"
        )

        # Verify document exists and user owns it
        await document_service.get_document(
            db=db,
            document_id=request.document_id,
            user_id=user_id
        )

        # Run RAG pipeline
        result = await rag_service.answer_question(
            document_id=request.document_id,
            query=request.query,
            top_k=request.top_k or 5,
            model=request.model or "gpt-4",
            temperature=request.temperature or 0.7,
            min_similarity=request.min_similarity or 0.5
        )

        logger.info(
            f"Generated response with {len(result['citations'])} citations"
        )

        return RAGResponse(
            query=result["query"],
            response=result["response"],
            citations=result["citations"],
            retrieved_chunks_count=len(result["retrieved_chunks"]),
            model=request.model or "gpt-4",
            timestamp=result["timestamp"]
        )

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except LLMException as e:
        logger.error(f"LLM error: {str(e)}")
        raise HTTPException(status_code=503, detail=f"LLM error: {str(e)}")

    except RetrievalException as e:
        logger.error(f"Retrieval error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Retrieval error: {str(e)}")

    except RAGException as e:
        logger.error(f"RAG error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RAG error: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.post(
    "/rag/chat-stream",
    response_class=StreamingResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    }
)
async def stream_answer(
    request: RAGRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Stream answer to question in real-time.

    Returns Server-Sent Events (SSE) stream with:
    1. Retrieved chunks metadata
    2. Response tokens as they arrive
    3. Final citations

    Format: newline-delimited JSON
    ```json
    {"type": "retrieved", "chunks_count": 5, ...}
    {"type": "response", "token": "The"}
    {"type": "response", "token": " document"}
    ...
    {"type": "citations", "citations": [...]}
    ```

    Use with EventSource in browser:
    ```javascript
    const eventSource = new EventSource('/api/rag/chat-stream?...');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'response') {
            // Add token to UI
            responseText += data.token;
        }
    };
    ```
    """
    try:
        logger.info(
            f"Streaming RAG query for document {request.document_id}: '{request.query}'"
        )

        # Verify document exists
        await document_service.get_document(
            db=db,
            document_id=request.document_id,
            user_id=user_id
        )

        # Create streaming generator
        async def stream_generator():
            try:
                async for chunk in rag_service.answer_question_stream(
                    document_id=request.document_id,
                    query=request.query,
                    top_k=request.top_k or 5,
                    model=request.model or "gpt-4",
                    temperature=request.temperature or 0.7,
                    min_similarity=request.min_similarity or 0.5
                ):
                    yield chunk

            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
                yield json.dumps({
                    "type": "error",
                    "message": str(e)
                }) + "\n"

        return StreamingResponse(
            stream_generator(),
            media_type="application/x-ndjson"  # Newline-delimited JSON
        )

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.get(
    "/rag/health",
    response_model=dict,
    status_code=200,
    responses={503: {"model": ErrorResponse,
                     "description": "Service unavailable"}}
)
async def rag_health() -> dict:
    """
    Health check for RAG service.

    Verifies:
    - OpenAI API connection
    - ChromaDB availability
    - Configuration loaded

    Returns:
    ```json
    {
        "status": "healthy",
        "service": "rag",
        "llm_model": "gpt-4",
        "retrieval_model": "bge-base-en-v1.5",
        "timestamp": "2026-06-01T12:34:56Z"
    }
    ```
    """
    try:
        # Verify RAG service initialized
        await rag_service.initialize()

        return {
            "status": "healthy",
            "service": "rag",
            "llm_model": "gpt-4",
            "retrieval_model": "BAAI/bge-base-en-v1.5",
            "embedding_dimension": 768,
            "vector_db": "ChromaDB",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"RAG health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"RAG service unavailable: {str(e)}"
        )
