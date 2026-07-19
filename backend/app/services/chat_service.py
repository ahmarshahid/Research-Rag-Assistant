"""
Chat Service for Phase 6: Multi-turn Conversations.

Purpose:
- Manage chat sessions (create, retrieve, delete)
- Handle multi-turn conversations
- Track conversation history
- Build context from previous messages
- Integrate with RAG service for intelligent responses

Design:
- Session-based conversation management
- History-aware context building
- Citation tracking per message
- User isolation and access control
"""

import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.models.database import ChatSession, ChatMessage, Document, DocumentSession
from app.models.schemas import ChatSessionResponse, ChatMessageResponse, ChatHistoryResponse
from app.services.rag_service import rag_service, RAGException
from app.utils.logger import get_logger
from app.utils.errors import NotFound, DatabaseException, ValidationError

logger = get_logger(__name__)


class ChatService:
    """
    Manage chat conversations and multi-turn interactions.

    Handles:
    - Session lifecycle (create, retrieve, delete)
    - Message storage with citations
    - Conversation context building
    - RAG integration for intelligent responses
    """

    async def create_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        document_ids: List[UUID],
        title: Optional[str] = None
    ) -> ChatSessionResponse:
        """
        Create a new chat session.

        What happens:
        1. Create ChatSession record
        2. Link documents via DocumentSession table
        3. Return session with metadata

        Args:
            db: Database session
            user_id: User creating session
            document_ids: Documents to chat about (can be multiple for multi-doc reasoning)
            title: Optional session title (auto-generated if empty)

        Returns:
            ChatSessionResponse with session details
        """
        try:
            logger.info(
                f"Creating chat session for user {user_id} with {len(document_ids)} documents")

            # Validate documents exist and user owns them
            if document_ids:
                query = select(Document).where(
                    and_(
                        Document.id.in_(document_ids),
                        Document.user_id == user_id
                    )
                )
                result = await db.execute(query)
                documents = result.scalars().all()

                if len(documents) != len(document_ids):
                    raise ValidationError(
                        "One or more documents not found or access denied")

            # Create session
            session = ChatSession(
                user_id=user_id,
                title=title or f"Chat Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            )
            db.add(session)
            await db.flush()

            # Link documents
            for doc_id in document_ids:
                doc_session = DocumentSession(
                    document_id=doc_id,
                    session_id=session.id
                )
                db.add(doc_session)

            await db.commit()
            logger.info(f"Chat session created: {session.id}")

            return ChatSessionResponse(
                id=session.id,
                user_id=session.user_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                is_archived=session.is_archived,
                message_count=0
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create chat session: {str(e)}")
            raise DatabaseException(f"Failed to create session: {str(e)}")

    async def get_session(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_id: UUID
    ) -> ChatSessionResponse:
        """
        Retrieve session details.

        Args:
            db: Database session
            session_id: Session to retrieve
            user_id: User requesting (must own session)

        Returns:
            ChatSessionResponse with metadata and message count
        """
        try:
            query = select(ChatSession).where(
                and_(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id
                )
            )
            result = await db.execute(query)
            session = result.scalars().first()

            if not session:
                raise NotFound("Chat session not found")

            # Get message count
            msg_query = select(ChatMessage).where(
                ChatMessage.session_id == session_id
            )
            msg_result = await db.execute(msg_query)
            message_count = len(msg_result.scalars().all())

            return ChatSessionResponse(
                id=session.id,
                user_id=session.user_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                is_archived=session.is_archived,
                message_count=message_count
            )

        except Exception as e:
            logger.error(f"Failed to get chat session: {str(e)}")
            raise

    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        archived: bool = False
    ) -> tuple[List[ChatSessionResponse], int]:
        """
        List user's chat sessions.

        Args:
            db: Database session
            user_id: User whose sessions to list
            skip: Pagination offset
            limit: Pagination limit
            archived: Include archived sessions

        Returns:
            (sessions_list, total_count)
        """
        try:
            # Build query
            query = select(ChatSession).where(
                and_(
                    ChatSession.user_id == user_id,
                    ChatSession.is_archived == archived
                )
            ).order_by(desc(ChatSession.updated_at))

            # Get total count
            count_result = await db.execute(
                select(ChatSession).where(
                    and_(
                        ChatSession.user_id == user_id,
                        ChatSession.is_archived == archived
                    )
                )
            )
            total = len(count_result.scalars().all())

            # Get paginated results
            result = await db.execute(query.offset(skip).limit(limit))
            sessions = result.scalars().all()

            # Convert to response models
            responses = []
            for session in sessions:
                msg_query = select(ChatMessage).where(
                    ChatMessage.session_id == session.id
                )
                msg_result = await db.execute(msg_query)
                message_count = len(msg_result.scalars().all())

                responses.append(ChatSessionResponse(
                    id=session.id,
                    user_id=session.user_id,
                    title=session.title,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    is_archived=session.is_archived,
                    message_count=message_count
                ))

            return responses, total

        except Exception as e:
            logger.error(f"Failed to list chat sessions: {str(e)}")
            raise DatabaseException(f"Failed to list sessions: {str(e)}")

    async def delete_session(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_id: UUID
    ) -> None:
        """
        Delete a chat session and all its messages.

        Args:
            db: Database session
            session_id: Session to delete
            user_id: User requesting (must own session)
        """
        try:
            # Verify ownership
            query = select(ChatSession).where(
                and_(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id
                )
            )
            result = await db.execute(query)
            session = result.scalars().first()

            if not session:
                raise NotFound("Chat session not found")

            # Delete (cascade handles messages and document_sessions)
            await db.delete(session)
            await db.commit()

            logger.info(f"Chat session deleted: {session_id}")

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete chat session: {str(e)}")
            raise

    async def get_history(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_id: UUID
    ) -> ChatHistoryResponse:
        """
        Get complete chat history for a session.

        Args:
            db: Database session
            session_id: Session to retrieve history for
            user_id: User requesting (must own session)

        Returns:
            ChatHistoryResponse with session + all messages
        """
        try:
            # Get session
            session_response = await self.get_session(db, session_id, user_id)

            # Get messages
            query = select(ChatMessage).where(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at)
            result = await db.execute(query)
            messages = result.scalars().all()

            # Convert to response models
            message_responses = [
                ChatMessageResponse(
                    id=msg.id,
                    session_id=msg.session_id,
                    role=msg.role,
                    content=msg.content,
                    citations=msg.citations,
                    tokens_used=msg.tokens_used,
                    created_at=msg.created_at
                )
                for msg in messages
            ]

            return ChatHistoryResponse(
                session=session_response,
                messages=message_responses
            )

        except Exception as e:
            logger.error(f"Failed to get chat history: {str(e)}")
            raise

    async def send_message(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_id: UUID,
        message_content: str,
        document_id: Optional[UUID] = None,
        model: str = "gpt-4",
        temperature: float = 0.7,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> ChatMessageResponse:
        """
        Send message and get RAG response.

        What happens:
        1. Save user message
        2. Get previous messages for context (last 5)
        3. Use first document in session, or specified document
        4. Retrieve chunks
        5. Generate response with RAG
        6. Save assistant message with citations
        7. Return assistant response

        Args:
            db: Database session
            session_id: Session to message in
            user_id: User sending message
            message_content: Message text
            document_id: Specific document to query (optional)
            model: LLM model
            temperature: LLM temperature
            top_k: Chunks to retrieve
            min_similarity: Min similarity threshold

        Returns:
            ChatMessageResponse with assistant response + citations
        """
        try:
            logger.info(f"Processing message in session {session_id}")

            # Step 1: Verify session ownership
            session_result = await db.execute(
                select(ChatSession).where(
                    and_(
                        ChatSession.id == session_id,
                        ChatSession.user_id == user_id
                    )
                )
            )
            session = session_result.scalars().first()
            if not session:
                raise NotFound("Chat session not found")

            # Step 2: Determine document to query
            if not document_id:
                # Get first document in session
                doc_result = await db.execute(
                    select(DocumentSession).where(
                        DocumentSession.session_id == session_id
                    )
                )
                doc_sessions = doc_result.scalars().all()
                if not doc_sessions:
                    raise ValidationError(
                        "No documents associated with this session")
                document_id = doc_sessions[0].document_id

            # Step 3: Save user message
            user_msg = ChatMessage(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=message_content
            )
            db.add(user_msg)
            await db.flush()

            # Step 4: Build context from previous messages (last 5 Q&As)
            context_query = select(ChatMessage).where(
                ChatMessage.session_id == session_id
            ).order_by(desc(ChatMessage.created_at)).limit(10)
            context_result = await db.execute(context_query)
            previous_messages = list(reversed(context_result.scalars().all()))

            # Format context: "Q: previous question\nA: previous answer\n..."
            context_str = ""
            for msg in previous_messages[-4:]:  # Last 4 messages (2 Q&As)
                role = "User" if msg.role == "user" else "Assistant"
                context_str += f"{role}: {msg.content}\n"

            # Auto-initialize ChromaDB collection if missing
            try:
                collection_name = f"doc_{document_id}"
                try:
                    collection_info = await vectordb_service.get_collection_info(collection_name)
                    has_vectors = collection_info.get("count", 0) > 0
                except Exception:
                    has_vectors = False

                if not has_vectors:
                    logger.info(f"Auto-indexing document {document_id} into ChromaDB on the fly.")
                    from app.models.database import Document, Chunk
                    from app.services.chunking_service import chunking_service
                    from app.services.embedding_service import embedding_service
                    
                    doc_query = await db.execute(select(Document).where(Document.id == document_id))
                    target_doc = doc_query.scalars().first()
                    if target_doc and target_doc.extracted_text:
                        chunk_query = await db.execute(select(Chunk).where(Chunk.document_id == document_id))
                        existing_chunks = list(chunk_query.scalars().all())
                        if not existing_chunks:
                            raw_chunks = chunking_service.chunk_document(str(document_id), target_doc.extracted_text)
                            if raw_chunks:
                                chunk_texts = [c.text for c in raw_chunks]
                                embeddings = await embedding_service.embed_texts(chunk_texts)
                                existing_chunks = []
                                import hashlib
                                for rc, emb in zip(raw_chunks, embeddings):
                                    db_chunk = Chunk(
                                        document_id=document_id,
                                        chunk_index=rc.metadata.chunk_index,
                                        text=rc.text,
                                        text_hash=hashlib.md5(rc.text.encode()).hexdigest(),
                                        page_number=rc.metadata.page_number,
                                        char_start=rc.metadata.char_start,
                                        char_end=rc.metadata.char_end,
                                        tokens_estimated=rc.metadata.tokens_estimated,
                                        embedding=emb.tolist() if hasattr(emb, 'tolist') else emb,
                                        embedding_model="BAAI/bge-base-en-v1.5",
                                        chunk_metadata={"chunk_source": "auto_rag"}
                                    )
                                    db.add(db_chunk)
                                    existing_chunks.append(db_chunk)
                                await db.flush()

                        if existing_chunks:
                            await vectordb_service.create_collection(
                                collection_name, 
                                metadata={"document_id": str(document_id), "filename": target_doc.filename}
                            )
                            await vectordb_service.insert_chunks(
                                collection_name=collection_name,
                                documents=[c.text for c in existing_chunks],
                                embeddings=[c.embedding for c in existing_chunks],
                                metadatas=[{"chunk_id": str(c.id), "page_number": c.page_number} for c in existing_chunks],
                                ids=[str(c.id) for c in existing_chunks]
                            )
            except Exception as auto_idx_err:
                logger.warning(f"Auto-indexing check failed: {str(auto_idx_err)}")

            # Step 5: Retrieve chunks using RAG service
            try:
                rag_result = await rag_service.answer_question(
                    document_id=document_id,
                    query=message_content,
                    top_k=top_k,
                    model=model,
                    temperature=temperature,
                    min_similarity=min_similarity,
                    chat_history=context_str
                )
            except RAGException as e:
                logger.warning(
                    f"RAG failed: {str(e)}, using fallback response")
                # Fallback response
                response_text = "I encountered an issue while processing your question. Please try rephrasing your question."
                citations = []
            else:
                response_text = rag_result["response"]
                citations = rag_result["citations"]

            # Step 6: Save assistant message
            assistant_msg = ChatMessage(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=response_text,
                citations=[{
                    "chunk_id": str(c.get("chunk_id", "")),
                    "page_number": c.get("page_number"),
                    "text_preview": c.get("text_preview")
                } for c in citations]
            )
            db.add(assistant_msg)

            # Update session timestamp
            session.updated_at = datetime.utcnow()

            await db.commit()
            logger.info(f"Message processed and saved in session {session_id}")

            return ChatMessageResponse(
                id=assistant_msg.id,
                session_id=assistant_msg.session_id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                citations=assistant_msg.citations,
                tokens_used=assistant_msg.tokens_used,
                created_at=assistant_msg.created_at
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to process message: {str(e)}")
            raise


# Global singleton instance
chat_service = ChatService()
