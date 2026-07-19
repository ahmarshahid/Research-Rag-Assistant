"""
Chat API routes for Phase 6: Multi-turn Conversations.

Endpoints:
- POST /api/chat - Create new chat session
- POST /api/chat/{session_id}/message - Send message to session
- GET /api/chat - List user's chat sessions
- GET /api/chat/{session_id} - Get session details
- GET /api/chat/{session_id}/history - Get complete chat history
- DELETE /api/chat/{session_id} - Delete chat session

Design:
- Session-based conversation management
- History-aware context building
- Multi-document support
- Access control (user isolation)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
import logging

from app.dependencies import get_db
from app.api.dependencies import get_current_user_id
from app.models.schemas import (
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
    ErrorResponse
)
from app.services.chat_service import chat_service
from app.utils.errors import NotFound, ValidationError, DatabaseException
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["chat"])
logger = get_logger(__name__)


@router.post(
    "/chat",
    response_model=ChatSessionResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Document not found"},
    }
)
async def create_chat_session(
    request: ChatSessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> ChatSessionResponse:
    """
    Create a new chat session.

    A chat session is a conversation with one or more documents.
    You can ask multiple questions within a single session.

    Request:
    ```json
    {
        "document_ids": ["550e8400-e29b-41d4-a716-446655440000"],
        "title": "ML Discussion"
    }
    ```

    Response (201 Created):
    ```json
    {
        "id": "a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "title": "ML Discussion",
        "created_at": "2026-06-01T12:34:56Z",
        "updated_at": "2026-06-01T12:34:56Z",
        "is_archived": false,
        "message_count": 0
    }
    ```
    """
    try:
        logger.info(f"Creating chat session for user {user_id}")

        session = await chat_service.create_session(
            db=db,
            user_id=user_id,
            document_ids=request.document_ids,
            title=request.title
        )

        return session

    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except DatabaseException as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.get(
    "/chat",
    response_model=dict,
    status_code=200,
    responses={500: {"model": ErrorResponse, "description": "Server error"}}
)
async def list_chat_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> dict:
    """
    List user's chat sessions.

    Query Parameters:
    - skip: Pagination offset (default: 0)
    - limit: Items per page (default: 50, max: 100)
    - archived: Include archived sessions (default: false)

    Response (200 OK):
    ```json
    {
        "sessions": [
            {
                "id": "a1b2c3d4-...",
                "title": "ML Discussion",
                "created_at": "2026-06-01T12:34:56Z",
                "updated_at": "2026-06-01T12:35:00Z",
                "message_count": 5,
                "is_archived": false
            }
        ],
        "total": 12,
        "skip": 0,
        "limit": 50
    }
    ```
    """
    try:
        logger.info(f"Listing chat sessions for user {user_id}")

        sessions, total = await chat_service.list_sessions(
            db=db,
            user_id=user_id,
            skip=skip,
            limit=limit,
            archived=archived
        )

        return {
            "sessions": sessions,
            "total": total,
            "skip": skip,
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Failed to list sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list sessions")


@router.get(
    "/chat/{session_id}",
    response_model=ChatSessionResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Server error"}
    }
)
async def get_chat_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> ChatSessionResponse:
    """
    Get chat session details.

    Response (200 OK):
    ```json
    {
        "id": "a1b2c3d4-...",
        "user_id": "00000000-...",
        "title": "ML Discussion",
        "created_at": "2026-06-01T12:34:56Z",
        "updated_at": "2026-06-01T12:35:00Z",
        "is_archived": false,
        "message_count": 5
    }
    ```
    """
    try:
        logger.info(f"Retrieving chat session {session_id}")

        session = await chat_service.get_session(
            db=db,
            session_id=session_id,
            user_id=user_id
        )

        return session

    except NotFound as e:
        logger.warning(f"Session not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to get session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get session")


@router.get(
    "/chat/{session_id}/history",
    response_model=ChatHistoryResponse,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Server error"}
    }
)
async def get_chat_history(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> ChatHistoryResponse:
    """
    Get complete chat history for a session.

    Returns session details + all messages in chronological order.

    Response (200 OK):
    ```json
    {
        "session": {
            "id": "a1b2c3d4-...",
            "title": "ML Discussion",
            ...
        },
        "messages": [
            {
                "id": "msg-uuid",
                "session_id": "...",
                "role": "user",
                "content": "What is machine learning?",
                "citations": null,
                "created_at": "2026-06-01T12:34:56Z"
            },
            {
                "id": "msg-uuid",
                "session_id": "...",
                "role": "assistant",
                "content": "Machine learning is... [1]",
                "citations": [
                    {
                        "chunk_id": "...",
                        "page_number": 5,
                        "text_preview": "..."
                    }
                ],
                "created_at": "2026-06-01T12:35:00Z"
            }
        ]
    }
    ```
    """
    try:
        logger.info(f"Retrieving chat history for session {session_id}")

        history = await chat_service.get_history(
            db=db,
            session_id=session_id,
            user_id=user_id
        )

        return history

    except NotFound as e:
        logger.warning(f"Session not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to get history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get history")


@router.post(
    "/chat/{session_id}/message",
    response_model=ChatMessageResponse,
    status_code=200,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Session not found"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    }
)
async def send_chat_message(
    session_id: UUID,
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> ChatMessageResponse:
    """
    Send message to chat session and get RAG response.

    What happens:
    1. Save user message
    2. Retrieve previous messages for context
    3. Query documents using RAG
    4. Generate response with citations
    5. Save assistant response
    6. Return response

    Request:
    ```json
    {
        "content": "What is the main topic?",
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "model": "gpt-4",
        "temperature": 0.7,
        "top_k": 5,
        "min_similarity": 0.5
    }
    ```

    Response (200 OK):
    ```json
    {
        "id": "msg-uuid",
        "session_id": "a1b2c3d4-...",
        "role": "assistant",
        "content": "The main topic is machine learning... [1]",
        "citations": [
            {
                "chunk_id": "uuid",
                "page_number": 5,
                "text_preview": "Machine learning is..."
            }
        ],
        "tokens_used": 250,
        "created_at": "2026-06-01T12:35:00Z"
    }
    ```
    """
    try:
        logger.info(f"Processing message in session {session_id}")

        response = await chat_service.send_message(
            db=db,
            session_id=session_id,
            user_id=user_id,
            message_content=request.content,
            document_id=request.document_id,
            model=request.model or "gpt-4",
            temperature=request.temperature or 0.7,
            top_k=request.top_k or 5,
            min_similarity=request.min_similarity or 0.3
        )

        return response

    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except NotFound as e:
        logger.warning(f"Session not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to process message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to process message")


@router.delete(
    "/chat/{session_id}",
    response_model=dict,
    status_code=200,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Server error"}
    }
)
async def delete_chat_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> dict:
    """
    Delete a chat session and all its messages.

    Response (200 OK):
    ```json
    {
        "message": "Chat session deleted",
        "session_id": "a1b2c3d4-..."
    }
    ```
    """
    try:
        logger.info(f"Deleting chat session {session_id}")

        await chat_service.delete_session(
            db=db,
            session_id=session_id,
            user_id=user_id
        )

        return {
            "message": "Chat session deleted",
            "session_id": str(session_id)
        }

    except NotFound as e:
        logger.warning(f"Session not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to delete session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete session")
