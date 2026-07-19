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


# ---------------------------------------------------------------------------
# Conversational intent detection
# ---------------------------------------------------------------------------
_CONVERSATIONAL_PATTERNS = [
    # greetings
    r"^\s*(hi|hello|hey|howdy|hiya|greetings|good\s*(morning|afternoon|evening|night|day))\b",
    # farewells
    r"^\s*(bye|goodbye|see\s*you|take\s*care|later|cya|farewell)\b",
    # thanks
    r"^\s*(thanks?|thank\s*you|thx|ty|cheers|appreciate\s*it)\b",
    # how are you
    r"^\s*(how\s*(are|r)\s*(you|u)|what'?s\s*up|how'?s\s*it\s*going|how\s*do\s*you\s*do)\b",
    # who / what are you
    r"^\s*(who|what)\s*(are|r)\s*(you|u)\b",
    # help without context
    r"^\s*help\s*[.!?]*\s*$",
    # ok / yes / no short replies
    r"^\s*(ok|okay|sure|yep|nope|no|yes|yeah|nah|alright|great|cool|nice|awesome|perfect|got\s*it)\s*[.!?]*\s*$",
    # introductions: "I'm Ahmar", "I am John", "My name is Sara", "call me Zaid"
    r"^\s*(i'?m|i\s+am|my\s+name\s+is|call\s+me|this\s+is)\s+[a-zA-Z]+\s*[.!?]*\s*$",
]

_CONVERSATIONAL_REPLIES: Dict[str, str] = {
    "greeting": (
        "Hello! 👋 I'm your AI Research Assistant. "
        "Ask me anything about your uploaded document — I'll search through it and give you precise, cited answers."
    ),
    "farewell": "Goodbye! Feel free to come back whenever you have more questions about your documents. 👋",
    "thanks": "You're welcome! 😊 Let me know if you have more questions about the document.",
    "how_are_you": (
        "I'm doing great, thanks for asking! 🤖 "
        "I'm here and ready to help you explore your research documents. What would you like to know?"
    ),
    "who_are_you": (
        "I'm an AI Research Assistant powered by RAG (Retrieval-Augmented Generation). "
        "I analyze your uploaded PDFs and answer questions with cited excerpts from the actual text. "
        "Try asking something like: *'What is the main topic of this document?'*"
    ),
    "help": (
        "Sure! Here's what I can do:\n"
        "• **Summarize** the document or any section\n"
        "• **Answer questions** with page-level citations\n"
        "• **Find specific information** (dates, names, figures, conclusions)\n\n"
        "Just type your question and I'll search the document for you!"
    ),
    "short_reply": "Got it! Feel free to ask me anything about the document. 😊",
    "introduction": None,  # handled dynamically below
}


def _detect_conversational_intent(query: str):
    """
    Return (intent, name_or_None) if the query is conversational/small-talk,
    or (None, None) if it looks like a real document question.
    """
    import re
    q = query.strip()
    ql = q.lower()

    if re.search(_CONVERSATIONAL_PATTERNS[0], ql, re.IGNORECASE):
        return "greeting", None
    if re.search(_CONVERSATIONAL_PATTERNS[1], ql, re.IGNORECASE):
        return "farewell", None
    if re.search(_CONVERSATIONAL_PATTERNS[2], ql, re.IGNORECASE):
        return "thanks", None
    if re.search(_CONVERSATIONAL_PATTERNS[3], ql, re.IGNORECASE):
        return "how_are_you", None
    if re.search(_CONVERSATIONAL_PATTERNS[4], ql, re.IGNORECASE):
        return "who_are_you", None
    if re.search(_CONVERSATIONAL_PATTERNS[5], ql, re.IGNORECASE):
        return "help", None
    if re.search(_CONVERSATIONAL_PATTERNS[6], ql, re.IGNORECASE):
        return "short_reply", None
    # Introductions — extract the name
    intro_match = re.search(_CONVERSATIONAL_PATTERNS[7], ql, re.IGNORECASE)
    if intro_match:
        # Pull the name: last word group in the original query
        name_match = re.search(
            r"(?:i'?m|i\s+am|my\s+name\s+is|call\s+me|this\s+is)\s+([a-zA-Z]+)",
            q, re.IGNORECASE
        )
        name = name_match.group(1).capitalize() if name_match else "there"
        return "introduction", name
    return None, None


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
        min_similarity: float = 0.3
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
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: str = ""
    ) -> str:
        """
        Format retrieved chunks and chat history as LLM context.
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

        history_section = f"Previous Conversation:\n{chat_history}\n\n" if chat_history else ""

        prompt = f"""You are a helpful, conversational AI Research Assistant. Your job is to answer questions based on the provided document excerpts, while also maintaining a friendly conversation.

{history_section}Here are the relevant document excerpts for the user's latest message:

{context}

Current User Message: {query}

Instructions:
- First, try to answer the question using ONLY the provided excerpts.
- If you use the excerpts, include citations like [1], [2] when referencing specific parts.
- If the answer to the user's question is NOT in the excerpts, you may use your own general knowledge to answer it. HOWEVER, if you do this, you MUST explicitly state at the beginning of your answer: "The provided document does not contain this information, but based on general knowledge..."
- If the user is just greeting you or making small talk (like "Hi", "I'm Ahmar", "How are you"), reply conversationally and warmly. You don't need to use the document excerpts for small talk.
- Be concise, accurate, and format your response clearly using markdown.

Answer:"""

        return prompt

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """
        Call Google Gemini 2.5 Flash via its REST API using httpx.
        Free tier: 15 requests/min, 1M tokens/day — no package install needed.
        """
        # Force load directly from .env to bypass broken Windows system environment variables
        from dotenv import dotenv_values
        env_dict = dotenv_values(".env")
        gemini_key = env_dict.get("GEMINI_API_KEY", "")

        if not gemini_key or gemini_key.startswith("your-"):
            return None

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={gemini_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
                "topP": 0.9,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                logger.info("Gemini response received successfully.")
                return text
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}")
            return None

    async def generate_response(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        chat_history: str = ""
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generate LLM response with retrieved context.
        Priority: Gemini → OpenAI → Extractive fallback
        """
        await self.initialize()

        prompt = self._format_context(query, retrieved_chunks, chat_history)

        # ── 1. Try Google Gemini (free, fast) ──────────────────────────────────
        gemini_text = await self._call_gemini(prompt)
        if gemini_text:
            _, citations = CitationExtractor.extract_citations(gemini_text, retrieved_chunks)
            return gemini_text, citations

        # ── 2. Try OpenAI ──────────────────────────────────────────────────────
        from dotenv import dotenv_values
        env_dict = dotenv_values(".env")
        api_key = env_dict.get("OPENAI_API_KEY", "")
        has_valid_key = api_key and not api_key.startswith("your-") and len(api_key) > 20

        if self.openai_client and has_valid_key:
            try:
                logger.info(f"Generating response with OpenAI model={model}")
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                response_text = response.choices[0].message.content
                _, citations = CitationExtractor.extract_citations(response_text, retrieved_chunks)
                return response_text, citations

            except Exception as e:
                logger.warning(f"OpenAI API call failed ({str(e)}). Falling back to extractive synthesis.")

        # ── 3. Extractive fallback (no LLM key) ────────────────────────────────
        logger.info("Using local extractive synthesis (no LLM key configured).")
        citations = []
        excerpt_lines = []

        for i, chunk in enumerate(retrieved_chunks, 1):
            page = chunk.get("page_number", 1)
            similarity = chunk.get("similarity", 0)
            text_snippet = chunk.get("text", "").strip()
            if len(text_snippet) > 400:
                text_snippet = text_snippet[:400].rsplit(" ", 1)[0] + "…"
            if text_snippet:
                excerpt_lines.append(f"**[{i}]** *(Page {page}, relevance: {similarity:.0%})*\n> {text_snippet}")
                citations.append({
                    "chunk_id": chunk.get("chunk_id"),
                    "page_number": page,
                    "chunk_index": chunk.get("chunk_index"),
                    "char_start": chunk.get("char_start"),
                    "char_end": chunk.get("char_end"),
                    "text_preview": chunk.get("text", "")[:200]
                })

        if not excerpt_lines:
            return "I searched the document but couldn't find relevant information for that query. Try rephrasing.", []

        response_text = (
            f"Here are the most relevant excerpts from the document for **\"{query}\"**:\n\n"
            + "\n\n".join(excerpt_lines)
            + "\n\n---\n"
        )
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
        min_similarity: float = 0.3,
        stream: bool = False,
        chat_history: str = ""
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

            # Step 0: Short-circuit for conversational / small-talk queries
            intent, extra = _detect_conversational_intent(query)
            if intent:
                logger.info(f"Conversational query detected (intent={intent}), skipping RAG.")
                if intent == "introduction" and extra:
                    reply = (
                        f"Nice to meet you, **{extra}**! 👋 I'm your AI Research Assistant.\n\n"
                        f"I'm here to help you explore your uploaded documents. "
                        f"Feel free to ask me anything about the content — I'll search through it and give you cited answers!"
                    )
                else:
                    reply = _CONVERSATIONAL_REPLIES.get(intent, "Got it! How can I help you with the document?")
                return {
                    "query": query,
                    "response": reply,
                    "citations": [],
                    "retrieved_chunks": [],
                    "timestamp": datetime.utcnow().isoformat()
                }

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
                    "response": "I searched the document but couldn't find relevant information for your query. Try rephrasing or asking something more specific about the document's content.",
                    "citations": [],
                    "retrieved_chunks": [],
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Step 2: Generate response
            response_text, citations = await self.generate_response(
                query=query,
                retrieved_chunks=retrieved_chunks,
                model=model,
                temperature=temperature,
                chat_history=chat_history
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
        min_similarity: float = 0.3
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
