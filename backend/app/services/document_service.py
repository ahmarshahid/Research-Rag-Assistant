"""
Document service for handling PDF uploads, extraction, and storage.

Why a service layer?
- Separation of concerns: Business logic separate from HTTP routes
- Testability: Services can be tested independently
- Reusability: Same logic can be used by multiple endpoints
- Maintainability: Changes to PDF processing only need to happen here

What this service does:
1. Validates uploaded PDF files
2. Extracts text from PDFs using pdfplumber
3. Stores document metadata in database
4. Manages document lifecycle (upload, delete, retrieve)
5. Handles errors gracefully with proper logging
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import UploadFile, HTTPException

from app.config import get_settings
from app.models.database import Document, User
from app.utils.errors import (
    InvalidFileType,
    FileTooLarge,
    PDFProcessingError,
    DocumentNotFound,
    DatabaseException
)
from app.utils.logger import get_logger
import pdfplumber

logger = get_logger(__name__)
settings = get_settings()


class DocumentService:
    """Service for document upload and processing operations."""

    @staticmethod
    async def validate_pdf_file(file: UploadFile) -> Tuple[bool, Optional[str]]:
        """
        Validate PDF file before processing.

        Checks:
        - File extension is .pdf
        - File size is within limits
        - File has content

        Args:
            file: Uploaded file from FastAPI UploadFile

        Returns:
            Tuple of (is_valid, error_message)

        Raises:
            InvalidFileType: If file is not PDF
            FileTooLarge: If file exceeds size limit
            PDFProcessingError: If file is empty or unreadable
        """
        # Check file extension
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise InvalidFileType(
                f"File must be PDF. Received: {file.filename}"
            )

        # Check file size
        # Read file content to get size
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise PDFProcessingError("File is empty")

        if file_size > settings.MAX_FILE_SIZE:
            raise FileTooLarge(
                f"File size {file_size} bytes exceeds limit of {settings.MAX_FILE_SIZE} bytes"
            )

        # Reset file pointer for later reading
        await file.seek(0)

        return True, None

    @staticmethod
    async def extract_pdf_text(file_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF file using pdfplumber.

        Why pdfplumber?
        - Accurate text extraction (better than PyPDF2)
        - Preserves layout information
        - Handles tables and structured data
        - Lightweight and fast
        - Active maintenance

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (extracted_text, page_count)

        Raises:
            PDFProcessingError: If PDF cannot be read or processed
        """
        try:
            logger.info(f"Extracting text from PDF: {file_path}")

            text_content = ""
            page_count = 0

            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)

                if page_count == 0:
                    raise PDFProcessingError("PDF has no pages")

                # Extract text from each page
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            # Add page separator for tracking page numbers
                            text_content += f"\n--- Page {page_num} ---\n"
                            text_content += page_text
                    except Exception as e:
                        logger.warning(
                            f"Failed to extract text from page {page_num}: {str(e)}"
                        )
                        # Continue with other pages
                        continue

            logger.info(
                f"Successfully extracted text from {page_count} pages ({len(text_content)} chars)"
            )

            return text_content, page_count

        except Exception as e:
            logger.error(f"PDF processing failed: {str(e)}")
            raise PDFProcessingError(f"Failed to extract PDF text: {str(e)}")

    @staticmethod
    async def save_uploaded_file(
        file: UploadFile,
        user_id: uuid.UUID
    ) -> Tuple[str, int]:
        """
        Save uploaded file to disk and extract text.

        Storage strategy:
        - Files organized by user_id for access control
        - Original filename preserved for user reference
        - Unique directory per upload for isolation
        - Text extraction happens immediately (Phase 3 for chunking)

        Args:
            file: Uploaded file from FastAPI
            user_id: ID of uploading user

        Returns:
            Tuple of (file_path, page_count)

        Raises:
            PDFProcessingError: If file cannot be saved or processed
        """
        try:
            # Validate file first
            await DocumentService.validate_pdf_file(file)

            # Create user-specific upload directory
            user_upload_dir = Path(settings.UPLOAD_DIR) / str(user_id)
            user_upload_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename to prevent collisions
            unique_id = str(uuid.uuid4())
            original_name = Path(file.filename).stem  # Remove extension
            file_extension = ".pdf"
            unique_filename = f"{unique_id}_{original_name}{file_extension}"

            file_path = user_upload_dir / unique_filename

            # Save file to disk
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            logger.info(f"Saved PDF to {file_path}")

            # Extract text from PDF
            text_content, page_count = await DocumentService.extract_pdf_text(
                str(file_path)
            )

            return str(file_path), page_count

        except (InvalidFileType, FileTooLarge, PDFProcessingError):
            raise
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {str(e)}")
            raise PDFProcessingError(f"Failed to save file: {str(e)}")

    @staticmethod
    async def create_document(
        db: AsyncSession,
        user_id: uuid.UUID,
        filename: str,
        file_path: str,
        file_size: int,
        page_count: int,
        extracted_text: str
    ) -> Document:
        """
        Create document record in database.

        What gets stored:
        - Document metadata (filename, size, page count)
        - File path for retrieval
        - Extracted text for Phase 3 (chunking)
        - Processing status (starts as COMPLETED since we extract immediately)
        - User association for access control

        Args:
            db: Database session
            user_id: ID of document owner
            filename: Original filename
            file_path: Path where file is stored
            file_size: Size in bytes
            page_count: Number of pages
            extracted_text: Extracted text content

        Returns:
            Created Document object

        Raises:
            DatabaseException: If database insertion fails
        """
        try:
            document = Document(
                id=uuid.uuid4(),
                user_id=user_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                page_count=page_count,
                extracted_text=extracted_text,
                chroma_collection_id=None,  # Set in Phase 4
                processing_status="completed",  # Text already extracted
                metadata={
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "extraction_date": datetime.utcnow().isoformat(),
                    "original_filename": filename,
                },
                created_at=datetime.utcnow()
            )

            db.add(document)
            await db.flush()  # Insert and get ID

            logger.info(
                f"Created document record: {document.id} for user {user_id}"
            )

            return document

        except Exception as e:
            logger.error(f"Failed to create document in database: {str(e)}")
            raise DatabaseException(f"Failed to save document: {str(e)}")

    @staticmethod
    async def get_document(
        db: AsyncSession,
        document_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Document:
        """
        Retrieve document by ID with access control.

        Security:
        - Verifies user owns the document
        - Prevents access to other users' documents

        Args:
            db: Database session
            document_id: ID of document to retrieve
            user_id: ID of requesting user (for access control)

        Returns:
            Document object

        Raises:
            DocumentNotFound: If document doesn't exist or user doesn't own it
        """
        try:
            result = await db.execute(
                select(Document).where(
                    (Document.id == document_id) &
                    (Document.user_id == user_id)
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise DocumentNotFound(
                    f"Document {document_id} not found or access denied"
                )

            return document

        except DocumentNotFound:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve document: {str(e)}")
            raise DatabaseException(f"Database error: {str(e)}")

    @staticmethod
    async def list_user_documents(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Document], int]:
        """
        List all documents for a user with pagination.

        Pagination:
        - Skip: Number of documents to skip (for pagination)
        - Limit: Number of documents to return
        - Default: 50 documents per page

        Args:
            db: Database session
            user_id: ID of user whose documents to retrieve
            skip: Number of documents to skip
            limit: Maximum documents to return

        Returns:
            Tuple of (documents_list, total_count)
        """
        try:
            # Get total count
            count_result = await db.execute(
                select(Document).where(Document.user_id == user_id)
            )
            total_count = len(count_result.scalars().all())

            # Get paginated results (newest first)
            result = await db.execute(
                select(Document)
                .where(Document.user_id == user_id)
                .order_by(desc(Document.created_at))
                .offset(skip)
                .limit(limit)
            )
            documents = result.scalars().all()

            logger.info(
                f"Retrieved {len(documents)} documents for user {user_id}"
            )

            return list(documents), total_count

        except Exception as e:
            logger.error(f"Failed to list documents: {str(e)}")
            raise DatabaseException(f"Database error: {str(e)}")

    @staticmethod
    async def delete_document(
        db: AsyncSession,
        document_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Delete document and its associated files.

        Cleanup:
        - Deletes file from disk
        - Deletes database record
        - Access control verified (only owner can delete)
        - Cascade delete handles dependent records

        Args:
            db: Database session
            document_id: ID of document to delete
            user_id: ID of requesting user (for access control)

        Returns:
            True if deleted successfully

        Raises:
            DocumentNotFound: If document doesn't exist
            DatabaseException: If deletion fails
        """
        try:
            # Get document with access control
            document = await DocumentService.get_document(
                db, document_id, user_id
            )

            # Delete file from disk
            if document.file_path and os.path.exists(document.file_path):
                try:
                    os.remove(document.file_path)
                    logger.info(f"Deleted file: {document.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete file: {str(e)}")
                    # Continue with database deletion even if file deletion fails

            # Delete from database (cascade delete will handle dependent records)
            await db.delete(document)
            await db.flush()

            logger.info(f"Deleted document {document_id}")

            return True

        except DocumentNotFound:
            raise
        except Exception as e:
            logger.error(f"Failed to delete document: {str(e)}")
            raise DatabaseException(f"Failed to delete document: {str(e)}")

    @staticmethod
    async def get_document_text(
        db: AsyncSession,
        document_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> str:
        """
        Retrieve extracted text for a document.

        Use case:
        - Accessed by embedding service in Phase 3
        - Used for chunking and embedding
        - Used for RAG retrieval in Phase 5

        Args:
            db: Database session
            document_id: ID of document
            user_id: ID of requesting user

        Returns:
            Extracted text content

        Raises:
            DocumentNotFound: If document doesn't exist
        """
        try:
            document = await DocumentService.get_document(
                db, document_id, user_id
            )

            if not document.extracted_text:
                raise PDFProcessingError(
                    f"Document {document_id} has no extracted text"
                )

            return document.extracted_text

        except (DocumentNotFound, PDFProcessingError):
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve document text: {str(e)}")
            raise DatabaseException(f"Database error: {str(e)}")


# Singleton instance for dependency injection
document_service = DocumentService()
