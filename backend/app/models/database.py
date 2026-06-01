"""
SQLAlchemy ORM models for PostgreSQL database.

Why SQLAlchemy?
- Type-safe: Full ORM support with IDE autocomplete
- Migrations: Alembic integration for version control of schema
- Relationships: Built-in support for foreign keys and relationships
- Query building: Pythonic query API instead of raw SQL
- Session management: Automatic connection pooling and transaction handling
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class User(Base):
    """User account model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    documents = relationship(
        "Document", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship(
        "ChatMessage", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(email='{self.email}', username='{self.username}')>"


class Document(Base):
    """Uploaded PDF document model with processing metadata."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    # Full path to uploaded file
    file_path = Column(String(512), nullable=False)
    file_size = Column(BigInteger)  # File size in bytes
    page_count = Column(Integer)  # Number of pages in PDF
    # Full extracted text from PDF (for chunking in Phase 3)
    extracted_text = Column(Text)
    # ChromaDB collection identifier
    chroma_collection_id = Column(String(255))
    upload_timestamp = Column(
        DateTime, default=datetime.utcnow, nullable=False)
    # pending, processing, completed, failed
    processing_status = Column(String(50), default="pending")
    # Additional metadata (extraction method, language detected, etc.)
    document_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="documents")
    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan")
    document_sessions = relationship(
        "DocumentSession", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Document(filename='{self.filename}', status='{self.processing_status}')>"


class ChatSession(Base):
    """Chat conversation session model."""

    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255))  # Auto-generated from first message if empty
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan")
    document_sessions = relationship(
        "DocumentSession", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession(id='{self.id}', title='{self.title}')>"


class ChatMessage(Base):
    """Individual chat message model with citations."""

    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey(
        "chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    # Array of {document_id, page_number, chunk_text, similarity_score}
    citations = Column(JSON)
    tokens_used = Column(Integer)  # Token usage for cost tracking
    created_at = Column(DateTime, default=datetime.utcnow,
                        nullable=False, index=True)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    user = relationship("User", back_populates="chat_messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(role='{self.role}', created_at='{self.created_at}')>"


class Chunk(Base):
    """Text chunk for embedding and retrieval (Phase 3)."""

    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey(
        "documents.id", ondelete="CASCADE"), nullable=False, index=True)
    # Position in document (0-indexed)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)  # Chunk text content
    text_hash = Column(String(32), nullable=False,
                       index=True)  # MD5 for deduplication
    page_number = Column(Integer, nullable=False)  # Which page chunk came from
    char_start = Column(Integer)  # Character position in document
    char_end = Column(Integer)  # Character position in document
    tokens_estimated = Column(Integer)  # Approximate token count
    embedding = Column(JSON)  # Embedding vector (768-dim for BAAI/bge)
    embedding_model = Column(String(255))  # Model used for embedding
    chunk_metadata = Column(JSON)  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow,
                        nullable=False, index=True)
    embedded_at = Column(DateTime)  # When embedding was generated

    # Relationships
    document = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk(doc_id='{self.document_id}', page={self.page_number}, idx={self.chunk_index})>"


class DocumentSession(Base):
    """Association table for multi-document reasoning (many-to-many)."""

    __tablename__ = "document_sessions"

    document_id = Column(UUID(as_uuid=True), ForeignKey(
        "documents.id", ondelete="CASCADE"), primary_key=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey(
        "chat_sessions.id", ondelete="CASCADE"), primary_key=True, index=True)

    # Relationships
    document = relationship("Document", back_populates="document_sessions")
    session = relationship("ChatSession", back_populates="document_sessions")


# ==== INDEXING STRATEGY ====
# Why index the columns we did:
# - user_id: Most queries filter by user (foreign key access pattern)
# - created_at: Sorting messages by time, getting recent items
# - session_id: Getting messages for a specific session
# - email: User lookup by email (unique constraint index)
# - processing_status: Filtering documents by status

# ==== CASCADE DELETE LOGIC ====
# When a user deletes their account:
# - All documents get deleted (cascade)
# - All chat sessions get deleted (cascade)
# - All chat messages get deleted (cascade)
# This ensures data consistency and GDPR compliance
