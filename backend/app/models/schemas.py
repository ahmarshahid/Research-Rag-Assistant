"""
Pydantic models for request/response validation.

Why Pydantic?
- Automatic validation: Type checking at runtime
- JSON serialization: Automatic model-to-JSON conversion
- Documentation: OpenAPI schema generation
- IDE support: Full autocomplete and type hints
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, constr, validator


# ==== ENUMS ====
class ProcessingStatusEnum(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatRoleEnum(str, Enum):
    """Chat message role."""

    USER = "user"
    ASSISTANT = "assistant"


# ==== AUTH SCHEMAS ====
class UserRegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    username: constr(min_length=3, max_length=100)
    password: constr(min_length=8, max_length=128)

    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        if not any(c in "!@#$%^&*" for c in v):
            raise ValueError("Password must contain special character (!@#$%^&*)")
        return v


class UserLoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User profile response."""

    id: UUID
    email: str
    username: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


# ==== CITATION SCHEMAS ====
class Citation(BaseModel):
    """Citation information for retrieved chunk."""

    document_id: UUID
    filename: str
    page_number: int
    chunk_text: str
    similarity_score: Optional[float] = None


# ==== CHAT SCHEMAS (Phase 6) ====
class ChatSessionCreateRequest(BaseModel):
    """Request to create a new chat session."""

    document_ids: List[UUID] = Field(description="Documents to chat about")
    title: Optional[str] = Field(
        None, max_length=255, description="Session title (auto-generated if empty)"
    )


class ChatMessageRequest(BaseModel):
    """Chat message request."""

    content: str = Field(min_length=1, max_length=10000, description="Message content")
    document_id: Optional[UUID] = None  # Specific document to query
    model: Optional[str] = "gpt-4"
    temperature: Optional[float] = 0.7
    top_k: Optional[int] = 5
    min_similarity: Optional[float] = 0.5


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: UUID
    session_id: UUID
    role: str  # 'user' or 'assistant'
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    tokens_used: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    """Chat session response."""

    id: UUID
    user_id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_archived: bool
    message_count: Optional[int] = None

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Full chat history response."""

    session: ChatSessionResponse
    messages: List[ChatMessageResponse]


# ==== DOCUMENT SCHEMAS ====
class DocumentUploadRequest(BaseModel):
    """Document upload metadata (file uploaded separately)."""

    filename: str
    metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    """Document metadata response."""

    id: UUID
    user_id: UUID
    filename: str
    file_size: int
    page_count: Optional[int] = None
    processing_status: ProcessingStatusEnum
    upload_timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """List of documents response."""

    documents: List[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    """Document upload response with processing status."""

    id: UUID
    filename: str
    file_size: int
    page_count: int
    processing_status: ProcessingStatusEnum
    message: str = "File uploaded successfully and text extracted"
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentDeleteResponse(BaseModel):
    """Document deletion response."""

    id: UUID
    message: str = "Document deleted successfully"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DocumentDetailResponse(BaseModel):
    """Detailed document response with extracted text preview."""

    id: UUID
    user_id: UUID
    filename: str
    file_size: int
    page_count: int
    processing_status: ProcessingStatusEnum
    text_preview: Optional[str] = None  # First 500 chars of extracted text
    metadata: Optional[Dict[str, Any]] = None
    chroma_collection_id: Optional[str] = None
    created_at: datetime
    upload_timestamp: datetime

    class Config:
        from_attributes = True


# ==== SEARCH SCHEMAS ====
class SearchResult(BaseModel):
    """Single search result."""

    document_id: UUID
    filename: str
    page_number: int
    chunk_text: str
    score: float
    relevance: Optional[str] = None  # 'high', 'medium', 'low'


class SearchResultItem(BaseModel):
    """Single search result item."""

    chunk_id: UUID
    text: str
    similarity: float = Field(ge=0, le=1, description="Similarity score 0-1")
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class SearchResponse(BaseModel):
    """Search results response."""

    query: str
    results: List[SearchResultItem]
    total: int
    search_time_ms: float


class SearchRequest(BaseModel):
    """Search request."""

    query: str
    document_id: UUID
    top_k: Optional[int] = Field(5, ge=1, le=50)
    min_similarity: Optional[float] = Field(None, ge=0, le=1)
    page_number: Optional[int] = None


class CollectionInfoResponse(BaseModel):
    """ChromaDB collection info."""

    name: str
    document_id: UUID
    document_filename: str
    chunks_count: int
    metadata: Optional[Dict[str, Any]] = None


class CollectionsListResponse(BaseModel):
    """List of collections."""

    collections: List[CollectionInfoResponse]
    total: int


# ==== RAG SCHEMAS (Phase 5) ====
class RAGRequest(BaseModel):
    """RAG (Retrieval-Augmented Generation) request."""

    document_id: UUID
    query: str = Field(min_length=1, max_length=1000, description="Question to ask")
    top_k: Optional[int] = Field(
        5, ge=1, le=50, description="Number of chunks to retrieve"
    )
    model: Optional[str] = Field(
        "gpt-4", description="LLM model (gpt-4, gpt-3.5-turbo)"
    )
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="LLM temperature")
    min_similarity: Optional[float] = Field(
        0.5, ge=0, le=1, description="Min chunk similarity"
    )


class RAGCitation(BaseModel):
    """Citation from retrieved chunk."""

    chunk_id: Optional[UUID] = None
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    text_preview: Optional[str] = None


class RAGResponse(BaseModel):
    """RAG response with citations."""

    query: str
    response: str
    citations: List[RAGCitation]
    retrieved_chunks_count: int
    model: str
    timestamp: str


# ==== CHUNK SCHEMAS (Phase 3) ====
class ChunkRequest(BaseModel):
    """Request to chunk a document."""

    document_id: UUID
    chunk_size: Optional[int] = None  # Tokens (uses config default if None)
    chunk_overlap: Optional[int] = None  # Tokens (uses config default if None)


class ChunkMetadataResponse(BaseModel):
    """Metadata about a chunk."""

    page_number: int
    chunk_index: int
    char_start: int
    char_end: int
    tokens_estimated: int


class ChunkResponse(BaseModel):
    """Single chunk response."""

    id: UUID
    document_id: UUID
    text: str
    page_number: int
    chunk_index: int
    metadata: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None  # 768-dim vector
    created_at: datetime

    class Config:
        from_attributes = True


class ChunksListResponse(BaseModel):
    """List of chunks response."""

    document_id: UUID
    chunks: List[ChunkResponse]
    total_chunks: int
    total_tokens: int


class EmbeddingProgressResponse(BaseModel):
    """Progress of embedding generation."""

    document_id: UUID
    status: str  # "pending", "processing", "completed", "failed"
    chunks_processed: int
    total_chunks: int
    progress_percent: int = Field(default=0, ge=0, le=100)
    message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingStatusResponse(BaseModel):
    """Status of embedding for document."""

    document_id: UUID
    embedding_model: str
    chunks_count: int
    chunks_embedded: int
    embedding_dimension: int
    created_at: datetime


# ==== STREAMING RESPONSE ====
class StreamChunkResponse(BaseModel):
    """WebSocket streaming response chunk."""

    type: str  # 'chunk', 'citation', 'complete', 'error'
    content: Optional[str] = None
    citations: Optional[List[Citation]] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None


# ==== ERROR SCHEMAS ====
class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationErrorResponse(BaseModel):
    """Validation error response."""

    error: str = "Validation Error"
    details: List[Dict[str, Any]]
    status_code: int = 422


# ==== CONFIG SCHEMAS ====
class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    environment: str
    # {'postgresql': 'connected', 'redis': 'connected', 'chroma': 'connected'}
    databases: Dict[str, str]
