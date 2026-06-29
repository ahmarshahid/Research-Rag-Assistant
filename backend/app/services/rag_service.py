"""
RAG (Retrieval-Augmented Generation) Service for Phase 5.

Purpose:
- Retrieve relevant chunks from ChromaDB (Phase 4)
- Format context for LLM
- Call LLM with context (OpenAI or Ollama)
- Extract citations from response
- Handle streaming responses

Design:
- Modular: Decouple retrieval, LLM, formatting
- Flexible: Support multiple LLM providers
- Streaming: Real-time response tokens
- Citations: Track which chunks were used

Workflow:
1. User query
2. Generate query embedding
3. Search ChromaDB for similar chunks
4. Rank/rerank results
5. Format as LLM context
6. Call LLM with instructions
7. Stream response back to user
8. Extract citations from response
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from uuid import UUID
import logging
from datetime import datetime
import json

from openai import AsyncOpenAI
import httpx

from app.config import settings
from app.services.embedding_service import embedding_service
from app.services.vectordb_service import vectordb_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RAGException(Exception):
    """Base exception for RAG operations."""
    pass


class LLMException(RAGException):
    """LLM API error."""
    pass


class RetrievalException(RAGException):
    """Retrieval error."""
    pass


class CitationExtractor:
    """Extract citations from LLM response."""

    @staticmethod
    def extract_citations(
        response_text: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extract citations from response text.

        Looks for patterns like [1], [2], etc. in response.
        Maps back to retrieved chunks.

        Args:
            response_text: LLM response text
            retrieved_chunks: Original retrieved chunks with metadata

        Returns:
            (cleaned_text, citations_used)
        """
        citations_used = []

        # Simple pattern: look for [1], [2], etc.
        # In production, could use more sophisticated parsing
        import re
        pattern = r'\[(\d+)\]'
        matches = re.finditer(pattern, response_text)

        citation_indices = set()
        for match in matches:
            idx = int(match.group(1)) - 1  # Convert to 0-indexed
            if 0 <= idx < len(retrieved_chunks):
                citation_indices.add(idx)

        # Build citations list
        for idx in sorted(citation_indices):
            chunk = retrieved_chunks[idx]
            citations_used.append({
                "chunk_id": chunk.get("chunk_id"),
                "page_number": chunk.get("page_number"),
                "chunk_index": chunk.get("chunk_index"),
                "char_start": chunk.get("char_start"),
                "char_end": chunk.get("char_end"),
                "text_preview": chunk.get("text", "")[:200]
            })

        return response_text, citations_used


class RAGService:
    """
    Retrieval-Augmented Generation service.

    Combines search (Phase 4) + embeddings (Phase 3) + LLM
    for intelligent document Q&A.

    Singleton pattern - initialize once, reuse globally.
    """

    def __init__(self):
        """Initialize RAG service."""
        self.openai_client = None
        self.is_initialized = False

    async def initialize(self) -> None:
        """
        Initialize OpenAI client and verify settings.

        Lazy initialization on first use.
        """
        if self.is_initialized:
            return

        try:
            api_key = getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "openai_api_key", None)
            if api_key:
                self.openai_client = AsyncOpenAI(
                    api_key=api_key,
                    timeout=30.0
                )
                logger.info("RAG service initialized with OpenAI API")
            else:
                logger.warning("No OpenAI API key found in configuration. Will use smart local extractive synthesis for RAG responses.")
            
            self.is_initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {str(e)}")
            raise RAGException(f"RAG initialization failed: {str(e)}")

    async def retrieve(
        self,
        document_id: UUID,
        query: str,
        top_k: int = 5,
        page_number: Optional[int] = None,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for query.
        """
        try:
            logger.info(
                f"Retrieving chunks for query: '{query}' "
                f"(top_k={top_k}, min_similarity={min_similarity})"
            )

            # Step 1: Generate query embedding
            query_embedding = await embedding_service.embed_text(query)

            # Step 2: Search ChromaDB
            collection_name = f"doc_{document_id}"
            try:
                results = await vectordb_service.search_with_filters(
                    collection_name=collection_name,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    page_number=page_number,
                    min_similarity=min_similarity
                )
            except Exception as search_err:
                logger.warning(f"ChromaDB search failed for collection {collection_name}: {str(search_err)}. Returning empty retrieval.")
                results = []

            # Step 3: Format results
            retrieved = [
                {
                    "chunk_id": result["id"],
                    "text": result["text"],
                    "similarity": result["similarity"],
                    "page_number": result["metadata"].get("page_number"),
                    "chunk_index": result["metadata"].get("chunk_index"),
                    "char_start": result["metadata"].get("char_start"),
                    "char_end": result["metadata"].get("char_end"),
                    "embedding": result.get("embedding")
                }
                for result in results
            ]

            logger.info(f"Retrieved {len(retrieved)} chunks")
            return retrieved

        except Exception as e:
            logger.error(f"Retrieval failed: {str(e)}")
            raise RetrievalException(f"Retrieval failed: {str(e)}")

    def _format_context(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Format retrieved chunks as LLM context.
        """
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            page = chunk.get("page_number", "?")
            similarity = chunk.get("similarity", 0)
            text = chunk.get("text", "")
            context_parts.append(
                f"[{i}] (Page {page}, similarity: {similarity:.2%})\n{text}"
            )

        context = "\n\n".join(context_parts)

        prompt = f"""You are a helpful AI assistant that answers questions based on provided document excerpts.

Question: {query}

Here are the relevant document excerpts:

{context}

Instructions:
- Answer the question based on the provided excerpts
- Include citations like [1], [2] when referencing specific excerpts
- If the answer is not in the excerpts, say so clearly
- Be concise and accurate
- Format your response clearly

Answer:"""

        return prompt

    async def generate_response(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generate LLM response with retrieved context.
        """
        await self.initialize()

        # Check if OpenAI client is available and has a valid key
        api_key = getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "openai_api_key", None)
        has_valid_key = api_key and not api_key.startswith("your-") and len(api_key) > 20

        if self.openai_client and has_valid_key:
            try:
                logger.info(f"Generating response with model={model}")
                prompt = self._format_context(query, retrieved_chunks)

                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                response_text = response.choices[0].message.content
                _, citations = CitationExtractor.extract_citations(
                    response_text,
                    retrieved_chunks
                )
                return response_text, citations

            except Exception as e:
                logger.warning(f"OpenAI API call failed ({str(e)}). Switching to local RAG synthesis fallback.")

        # Extractive Local RAG Synthesis Fallback
        logger.info("Synthesizing answer using local RAG extractive engine.")
        summary_lines = [f"### 📚 Insights Extracted for: *\"{query}\"*\n"]
        citations = []

        for i, chunk in enumerate(retrieved_chunks, 1):
            page = chunk.get("page_number", 1)
            text_snippet = chunk.get("text", "").strip()
            if text_snippet:
                summary_lines.append(f"**Excerpt [{i}] (Page {page}):**")
                summary_lines.append(f"> \"{text_snippet}\"\n")
                citations.append({
                    "chunk_id": chunk.get("chunk_id"),
                    "page_number": page,
                    "chunk_index": chunk.get("chunk_index"),
                    "char_start": chunk.get("char_start"),
                    "char_end": chunk.get("char_end"),
                    "text_preview": text_snippet[:200]
                })

        if not retrieved_chunks:
            response_text = "I searched the document for relevant excerpts matching your query, but could not find matching text vector passages. Please try broadening your query."
        else:
            response_text = "\n".join(summary_lines)

        return response_text, citations

    async def generate_response_stream(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response tokens in real-time.

        Yields response tokens as they arrive from LLM.

        Args:
            query: User query
            retrieved_chunks: Chunks from retrieval
            model: LLM model
            temperature: LLM temperature
            max_tokens: Max output tokens

        Yields:
            Response tokens
        """
        await self.initialize()

        try:
            logger.info(f"Streaming response with model={model}")

            # Step 1: Format context
            prompt = self._format_context(query, retrieved_chunks)

            # Step 2: Stream from LLM
            async with self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            ) as stream:
                async for text in stream:
                    if text.choices and text.choices[0].delta.content:
                        yield text.choices[0].delta.content

        except Exception as e:
            logger.error(f"Response streaming failed: {str(e)}")
            raise LLMException(f"LLM streaming error: {str(e)}")

    async def answer_question(
        self,
        document_id: UUID,
        query: str,
        top_k: int = 5,
        model: str = "gpt-4",
        temperature: float = 0.7,
        min_similarity: float = 0.5,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Complete RAG pipeline: retrieve + generate.

        Full end-to-end question answering workflow.

        Args:
            document_id: Document to question
            query: User query
            top_k: Number of chunks to retrieve
            model: LLM model
            temperature: LLM temperature
            min_similarity: Min similarity for retrieval
            stream: Stream response (if False, return all at once)

        Returns:
            {
                "query": user query,
                "response": LLM response,
                "citations": [citation objects],
                "retrieved_chunks": [chunk objects],
                "timestamp": ISO timestamp
            }
        """
        try:
            logger.info(f"Starting RAG pipeline for query: '{query}'")

            # Step 1: Retrieve relevant chunks
            retrieved_chunks = await self.retrieve(
                document_id=document_id,
                query=query,
                top_k=top_k,
                min_similarity=min_similarity
            )

            if not retrieved_chunks:
                logger.warning(f"No chunks retrieved for query: '{query}'")
                return {
                    "query": query,
                    "response": "I couldn't find relevant information in the document.",
                    "citations": [],
                    "retrieved_chunks": [],
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Step 2: Generate response
            response_text, citations = await self.generate_response(
                query=query,
                retrieved_chunks=retrieved_chunks,
                model=model,
                temperature=temperature
            )

            logger.info("RAG pipeline completed successfully")

            return {
                "query": query,
                "response": response_text,
                "citations": citations,
                "retrieved_chunks": retrieved_chunks,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"RAG pipeline failed: {str(e)}")
            raise RAGException(f"Question answering failed: {str(e)}")

    async def answer_question_stream(
        self,
        document_id: UUID,
        query: str,
        top_k: int = 5,
        model: str = "gpt-4",
        temperature: float = 0.7,
        min_similarity: float = 0.5
    ) -> AsyncGenerator[str, None]:
        """
        Stream complete RAG response.

        Yields JSON objects as they're generated:
        1. Retrieved chunks metadata
        2. Response tokens
        3. Final citations

        Args:
            document_id: Document to question
            query: User query
            top_k: Number of chunks to retrieve
            model: LLM model
            temperature: LLM temperature
            min_similarity: Min similarity for retrieval

        Yields:
            JSON-encoded updates
        """
        try:
            logger.info(f"Starting streaming RAG for query: '{query}'")

            # Step 1: Retrieve chunks
            retrieved_chunks = await self.retrieve(
                document_id=document_id,
                query=query,
                top_k=top_k,
                min_similarity=min_similarity
            )

            # Yield retrieved chunks
            yield json.dumps({
                "type": "retrieved",
                "chunks_count": len(retrieved_chunks),
                "chunks": [
                    {
                        "page": c.get("page_number"),
                        "similarity": c.get("similarity"),
                        "text": c.get("text", "")[:100]  # Preview
                    }
                    for c in retrieved_chunks
                ]
            }) + "\n"

            if not retrieved_chunks:
                yield json.dumps({
                    "type": "response",
                    "token": "I couldn't find relevant information in the document."
                }) + "\n"
                return

            # Step 2: Stream response
            full_response = ""
            async for token in self.generate_response_stream(
                query=query,
                retrieved_chunks=retrieved_chunks,
                model=model,
                temperature=temperature
            ):
                full_response += token
                yield json.dumps({
                    "type": "response",
                    "token": token
                }) + "\n"

            # Step 3: Extract and yield citations
            _, citations = CitationExtractor.extract_citations(
                full_response,
                retrieved_chunks
            )

            yield json.dumps({
                "type": "citations",
                "citations": citations
            }) + "\n"

            logger.info("Streaming RAG completed")

        except Exception as e:
            logger.error(f"Streaming RAG failed: {str(e)}")
            yield json.dumps({
                "type": "error",
                "message": str(e)
            }) + "\n"


# Global singleton instance
rag_service = RAGService()
