"""
API routes for document management (Phase 2: PDF Upload & Parsing).

Endpoints:
- POST /api/documents/upload - Upload PDF file
- GET /api/documents - List user's documents
- GET /api/documents/{document_id} - Get document details
- DELETE /api/documents/{document_id} - Delete document

Design principles:
- All endpoints require authentication (added Phase 7)
- File upload uses multipart/form-data
- Large file handling with streaming
- Proper error handling and validation
- Comprehensive logging for debugging
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
import logging

from app.dependencies import get_db
from app.api.dependencies import get_current_user_id
from app.models.schemas import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentListResponse,
    DocumentDetailResponse,
    DocumentDeleteResponse,
    ErrorResponse
)
from app.services.document_service import document_service
from app.utils.errors import (
    InvalidFileType,
    FileTooLarge,
    PDFProcessingError,
    DocumentNotFound,
    DatabaseException,
    ApplicationException
)
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = get_logger(__name__)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or too large"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Processing error"},
    }
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> DocumentUploadResponse:
    """
    Upload and process a PDF document.

    What happens:
    1. Validate file (PDF, not too large)
    2. Save to disk in user-specific directory
    3. Extract text from PDF using pdfplumber
    4. Store document metadata in database
    5. Return document ID and processing status

    Request:
    - Content-Type: multipart/form-data
    - Body: file (binary PDF)

    Response:
    - 201 Created: Document uploaded successfully
    - 400 Bad Request: Invalid file or too large
    - 422 Unprocessable Entity: Validation error
    - 500 Internal Server Error: PDF processing failed

    Example:
    ```bash
    curl -X POST http://localhost:8000/api/documents/upload \
      -F "file=@research_paper.pdf"
    ```

    Response:
    ```json
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "filename": "research_paper.pdf",
        "file_size": 2048576,
        "page_count": 42,
        "processing_status": "completed",
        "message": "File uploaded successfully and text extracted",
        "created_at": "2026-05-31T12:34:56Z"
    }
    ```
    """
    try:
        logger.info(
            f"Document upload started for user {user_id}: {file.filename}"
        )

        # Step 1: Validate file
        # Checks: PDF extension, file size, content not empty
        await document_service.validate_pdf_file(file)

        # Step 2: Save file to disk and extract text
        # Returns file_path and page_count
        file_path, page_count = await document_service.save_uploaded_file(
            file, user_id
        )

        # Step 3: Get file size
        file_size = 0
        try:
            import os
            file_size = os.path.getsize(file_path)
        except Exception as e:
            logger.warning(f"Could not get file size: {str(e)}")

        # Step 4: Extract text from PDF for chunking in Phase 3
        extracted_text, _ = await document_service.extract_pdf_text(file_path)

        # Step 5: Create database record
        await db.begin()
        document = await document_service.create_document(
            db=db,
            user_id=user_id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            page_count=page_count,
            extracted_text=extracted_text
        )
        await db.commit()

        logger.info(
            f"Document uploaded successfully: {document.id} ({file_size} bytes, {page_count} pages)"
        )

        return DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            file_size=file_size,
            page_count=page_count,
            processing_status="completed",
            created_at=document.created_at
        )

    except InvalidFileType as e:
        logger.warning(f"Invalid file type: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {str(e)}"
        )

    except FileTooLarge as e:
        logger.warning(f"File too large: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {str(e)}"
        )

    except PDFProcessingError as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise HTTPException(
            status_code=422,
            detail=f"Failed to process PDF: {str(e)}"
        )

    except DatabaseException as e:
        logger.error(f"Database error: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save document: {str(e)}"
        )

    except Exception as e:
        logger.error(
            f"Unexpected error during upload: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during upload"
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=200,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        500: {"model": ErrorResponse, "description": "Database error"},
    }
)
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(
        50, ge=1, le=100, description="Max documents to return"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> DocumentListResponse:
    """
    List all documents for the current user with pagination.

    Pagination:
    - skip: Starting position (0 = first document)
    - limit: Max documents per page (1-100, default 50)

    Returns:
    - List of documents (newest first)
    - Total count for pagination

    Example:
    ```bash
    # Get first 50 documents
    curl http://localhost:8000/api/documents

    # Get next 50 documents
    curl http://localhost:8000/api/documents?skip=50&limit=50
    ```

    Response:
    ```json
    {
        "documents": [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "filename": "research_paper.pdf",
                "file_size": 2048576,
                "page_count": 42,
                "processing_status": "completed",
                "upload_timestamp": "2026-05-31T12:34:56Z",
                "created_at": "2026-05-31T12:34:56Z"
            }
        ],
        "total": 1
    }
    ```
    """
    try:
        logger.info(
            f"Listing documents for user {user_id} (skip={skip}, limit={limit})"
        )

        documents, total_count = await document_service.list_user_documents(
            db=db,
            user_id=user_id,
            skip=skip,
            limit=limit
        )

        document_responses = [
            DocumentResponse(
                id=doc.id,
                user_id=doc.user_id,
                filename=doc.filename,
                file_size=doc.file_size,
                page_count=doc.page_count,
                processing_status=doc.processing_status,
                upload_timestamp=doc.upload_timestamp,
                created_at=doc.created_at
            )
            for doc in documents
        ]

        return DocumentListResponse(
            documents=document_responses,
            total=total_count
        )

    except DatabaseException as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    status_code=200,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    }
)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> DocumentDetailResponse:
    """
    Get detailed information about a specific document.

    Returns:
    - Full document metadata
    - Preview of extracted text (first 500 chars)
    - Processing status
    - ChromaDB collection ID (if available in Phase 4+)

    Example:
    ```bash
    curl http://localhost:8000/api/documents/123e4567-e89b-12d3-a456-426614174000
    ```

    Response:
    ```json
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "user_id": "123e4567-e89b-12d3-a456-426614174001",
        "filename": "research_paper.pdf",
        "file_size": 2048576,
        "page_count": 42,
        "processing_status": "completed",
        "text_preview": "This is a research paper about AI. The paper discusses...",
        "metadata": {"uploaded_at": "2026-05-31T12:34:56Z"},
        "chroma_collection_id": null,
        "created_at": "2026-05-31T12:34:56Z",
        "upload_timestamp": "2026-05-31T12:34:56Z"
    }
    ```
    """
    try:
        logger.info(
            f"Getting document details: {document_id} for user {user_id}")

        document = await document_service.get_document(
            db=db,
            document_id=document_id,
            user_id=user_id
        )

        # Extract preview (first 500 chars)
        text_preview = None
        if document.extracted_text:
            text_preview = document.extracted_text[:500]

        return DocumentDetailResponse(
            id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            file_size=document.file_size,
            page_count=document.page_count,
            processing_status=document.processing_status,
            text_preview=text_preview,
            metadata=document.document_metadata,
            chroma_collection_id=document.chroma_collection_id,
            created_at=document.created_at,
            upload_timestamp=document.upload_timestamp
        )

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except DatabaseException as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=200,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Database error"},
    }
)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> DocumentDeleteResponse:
    """
    Delete a document and its associated files.

    Cleanup:
    - Removes file from disk
    - Deletes database record
    - Deletes dependent chat sessions/messages (if any)
    - Only owner can delete (verified via access control)

    Example:
    ```bash
    curl -X DELETE http://localhost:8000/api/documents/123e4567-e89b-12d3-a456-426614174000
    ```

    Response:
    ```json
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "message": "Document deleted successfully",
        "timestamp": "2026-05-31T12:34:56Z"
    }
    ```
    """
    try:
        logger.info(f"Deleting document: {document_id} for user {user_id}")

        await document_service.delete_document(
            db=db,
            document_id=document_id,
            user_id=user_id
        )
        await db.commit()

        logger.info(f"Document deleted: {document_id}")

        return DocumentDeleteResponse(id=document_id)

    except DocumentNotFound as e:
        logger.warning(f"Document not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except DatabaseException as e:
        logger.error(f"Database error: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(
            f"Unexpected error during deletion: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")
