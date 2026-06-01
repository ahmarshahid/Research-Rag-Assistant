"""
Text chunking service for Phase 3: Breaking down documents into chunks for embedding.

Why chunking?
- LLMs have token limits (GPT-4: 8k, 32k, 128k)
- Embeddings work best on medium-length text (50-500 tokens)
- Allows fine-grained retrieval (get relevant chunks, not whole document)
- Enables tracking of source location (page, position)

Chunking strategies:
1. Fixed-size chunking: Simple but may split sentences
2. Recursive chunking: Respects text structure (para → sentence → word)
3. Semantic chunking: Groups similar content (requires embedding model)

We implement: Recursive chunking (best balance of accuracy and performance)
"""

from typing import List, Tuple, Optional
import re
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ChunkMetadata:
    """Metadata about a chunk for tracking and retrieval."""

    def __init__(
        self,
        document_id: str,
        page_number: int,
        chunk_index: int,
        char_start: int,
        char_end: int,
        tokens_estimated: int
    ):
        self.document_id = document_id
        self.page_number = page_number
        self.chunk_index = chunk_index
        self.char_start = char_start  # Position in document
        self.char_end = char_end
        self.tokens_estimated = tokens_estimated  # For token counting


class Chunk:
    """A text chunk with metadata."""

    def __init__(self, text: str, metadata: ChunkMetadata):
        self.text = text
        self.metadata = metadata

    def __repr__(self) -> str:
        return f"<Chunk(len={len(self.text)}, page={self.metadata.page_number})>"


class ChunkingService:
    """Service for splitting text into chunks."""

    # Separators used in recursive chunking (largest to smallest)
    # Try to split on these in order to keep semantically related text together
    SEPARATORS = [
        "\n\n",      # Paragraph break
        "\n",        # Line break
        ". ",        # Sentence end
        " ",         # Word boundary
        ""           # Character level (fallback)
    ]

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count using simple heuristic.

        Why estimate?
        - Avoid tokenizer overhead during chunking
        - Good enough for sizing decisions
        - tiktoken tokenizer available for exact count in Phase 5

        Heuristic: 1 token ≈ 4 characters on average
        This is approximate but works for English text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rule of thumb: 1 token ≈ 4 characters
        return len(text) // 4

    @staticmethod
    def split_text_recursive(
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        separators: List[str] = None
    ) -> List[str]:
        """
        Split text recursively while preserving structure.

        Algorithm:
        1. Try to split on separator 0 (paragraph breaks)
        2. If chunks still too large, try separator 1 (line breaks)
        3. Continue until chunks fit or use character-level split
        4. Add overlap between chunks for context

        Why recursive?
        - Paragraphs → lines → sentences → words → chars
        - Keeps related text together
        - Better semantic coherence than fixed-size

        Args:
            text: Text to split
            chunk_size: Target size (in tokens)
            chunk_overlap: Overlap between chunks (in tokens)
            separators: Custom separators (uses default if None)

        Returns:
            List of text chunks
        """
        if separators is None:
            separators = ChunkingService.SEPARATORS

        logger.info(
            f"Splitting text: {len(text)} chars, "
            f"target {chunk_size} tokens, {chunk_overlap} overlap"
        )

        good_chunks = []
        separator = separators[-1]  # Start with character split

        # Find the best separator (largest one that produces splits)
        for _s in separators:
            if _s == "":
                separator = _s
                break
            if _s in text:
                separator = _s
                break

        # Split on separator
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # Merge splits to reach chunk_size
        good_splits = []
        for s in splits:
            if ChunkingService.estimate_tokens(s) < chunk_size:
                good_splits.append(s)
            else:
                # Recursively split if too large
                if good_splits:
                    merged = ChunkingService._merge_splits(
                        good_splits, separator, chunk_size
                    )
                    good_chunks.extend(merged)
                    good_splits = []

                # Recursively split the oversized split
                other_info = ChunkingService.split_text_recursive(
                    s,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    separators=separators
                )
                good_chunks.extend(other_info)

        # Merge remaining splits
        if good_splits:
            merged = ChunkingService._merge_splits(
                good_splits, separator, chunk_size
            )
            good_chunks.extend(merged)

        logger.info(f"Created {len(good_chunks)} chunks")

        # Add overlap
        return ChunkingService._add_overlap(good_chunks, chunk_overlap)

    @staticmethod
    def _merge_splits(
        splits: List[str],
        separator: str,
        chunk_size: int
    ) -> List[str]:
        """
        Merge splits into chunks of target size.

        Args:
            splits: List of text splits
            separator: Separator used to split
            chunk_size: Target chunk size in tokens

        Returns:
            List of merged chunks
        """
        separator_size = ChunkingService.estimate_tokens(separator)
        good_chunks = []
        current_chunk = ""

        for split in splits:
            split_size = ChunkingService.estimate_tokens(split)
            current_size = ChunkingService.estimate_tokens(current_chunk)

            if current_size + split_size + separator_size <= chunk_size:
                # Add to current chunk
                if current_chunk:
                    current_chunk += separator + split
                else:
                    current_chunk = split
            else:
                # Start new chunk
                if current_chunk:
                    good_chunks.append(current_chunk)
                current_chunk = split

        if current_chunk:
            good_chunks.append(current_chunk)

        return good_chunks

    @staticmethod
    def _add_overlap(chunks: List[str], overlap_tokens: int) -> List[str]:
        """
        Add context overlap between chunks.

        Why overlap?
        - Prevents losing meaning at chunk boundaries
        - Helps embeddings capture broader context
        - Typical overlap: 10-20% of chunk size

        Example:
        Chunk 1: "...... context text A |"
        Chunk 2: "| context text A ...... context text B |"
        Chunk 3: "| context text B ......"

        Args:
            chunks: List of chunks without overlap
            overlap_tokens: Overlap size in tokens

        Returns:
            List of chunks with overlap
        """
        if overlap_tokens == 0 or len(chunks) < 2:
            return chunks

        overlapped = []
        overlap_chars = overlap_tokens * 4  # Convert tokens to approximate chars

        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
            else:
                # Add end of previous chunk as prefix
                prev_chunk = chunks[i - 1]
                overlap_text = prev_chunk[-overlap_chars:]
                overlapped.append(overlap_text + chunk)

        return overlapped

    @staticmethod
    def chunk_document(
        document_id: str,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[Chunk]:
        """
        Chunk a full document with metadata tracking.

        This is the main entry point for chunking documents.

        Args:
            document_id: ID of document being chunked
            text: Full extracted text
            chunk_size: Token size (uses config default if None)
            chunk_overlap: Token overlap (uses config default if None)

        Returns:
            List of Chunk objects with metadata
        """
        if chunk_size is None:
            chunk_size = settings.CHUNK_SIZE
        if chunk_overlap is None:
            chunk_overlap = settings.CHUNK_OVERLAP

        logger.info(
            f"Chunking document {document_id}: "
            f"{len(text)} chars with {chunk_size} token chunks"
        )

        # Split into chunks
        text_chunks = ChunkingService.split_text_recursive(
            text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        # Add metadata to each chunk
        chunks = []
        char_pos = 0

        for chunk_idx, chunk_text in enumerate(text_chunks):
            # Determine page number from text
            # Look for "--- Page N ---" marker (added during extraction)
            page_num = ChunkingService._extract_page_number(text, char_pos)

            metadata = ChunkMetadata(
                document_id=document_id,
                page_number=page_num,
                chunk_index=chunk_idx,
                char_start=char_pos,
                char_end=char_pos + len(chunk_text),
                tokens_estimated=ChunkingService.estimate_tokens(chunk_text)
            )

            chunks.append(Chunk(text=chunk_text, metadata=metadata))
            char_pos += len(chunk_text)

        logger.info(
            f"Created {len(chunks)} chunks from document {document_id}"
        )

        return chunks

    @staticmethod
    def _extract_page_number(text: str, position: int) -> int:
        """
        Extract page number from text at given position.

        Looks for "--- Page N ---" markers added during PDF extraction.

        Args:
            text: Full document text
            position: Character position

        Returns:
            Page number (1-indexed)
        """
        # Look backwards from position for page marker
        page_pattern = r"--- Page (\d+) ---"

        # Find all page markers before position
        matches = list(re.finditer(page_pattern, text[:position]))

        if matches:
            # Get the last (most recent) page marker
            last_match = matches[-1]
            return int(last_match.group(1))

        return 1  # Default to page 1

    @staticmethod
    def chunk_batch(
        documents: List[Tuple[str, str]]
    ) -> dict:
        """
        Chunk multiple documents in batch.

        Useful for batch processing in background jobs.

        Args:
            documents: List of (document_id, text) tuples

        Returns:
            Dict mapping document_id to list of Chunks
        """
        results = {}

        for doc_id, text in documents:
            try:
                chunks = ChunkingService.chunk_document(doc_id, text)
                results[doc_id] = chunks
            except Exception as e:
                logger.error(f"Failed to chunk document {doc_id}: {str(e)}")
                results[doc_id] = []

        return results


# Singleton instance
chunking_service = ChunkingService()
