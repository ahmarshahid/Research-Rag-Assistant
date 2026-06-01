"""
ChromaDB Vector Database Service for Phase 4.

Purpose:
- Initialize persistent ChromaDB store
- Create document collections
- Insert chunks with embeddings
- Perform similarity search
- Filter by metadata

Design:
- Collection per document (isolation & scalability)
- Metadata stored with vectors for filtering
- Persistent storage (survives server restarts)
- Lazy initialization (first use)

Why ChromaDB over alternatives?
- Lightweight (no external database needed)
- Persistent storage support
- Built-in metadata filtering
- Fast approximate nearest neighbor search
- Great for RAG systems
- Easier than Pinecone (no API key) or Milvus (no setup)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb

from app.config import settings as _app_settings

logger = logging.getLogger(__name__)


class VectorDBException(Exception):
    """Base exception for vector DB operations."""

    pass


class CollectionNotFound(VectorDBException):
    """Collection not found in ChromaDB."""

    pass


class SearchException(VectorDBException):
    """Error during search operation."""

    pass


class VectorDBService:
    """
    ChromaDB service for vector operations.

    Singleton pattern - initialize once, reuse globally.

    Usage:
    ```python
    from app.services.vectordb_service import vectordb_service

    # Create collection
    await vectordb_service.create_collection(
        collection_name="doc_123",
        metadata={"document_id": "123", "filename": "research.pdf"}
    )

    # Insert chunks
    await vectordb_service.insert_chunks(
        collection_name="doc_123",
        documents=[chunk.text for chunk in chunks],
        embeddings=[chunk.embedding for chunk in chunks],
        metadatas=[
            {
                "page": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "char_start": chunk.char_start
            }
            for chunk in chunks
        ],
        ids=[str(chunk.id) for chunk in chunks]
    )

    # Search
    results = await vectordb_service.search(
        collection_name="doc_123",
        query_embedding=query_vec,
        top_k=5,
        where={"page": 1}  # Optional metadata filter
    )
    ```
    """

    def __init__(self, persist_dir: str = "./chroma_db"):
        """
        Initialize ChromaDB service.

        Args:
            persist_dir: Directory for persistent storage
        """
        self.persist_dir = persist_dir
        self.client: Any = None
        self.is_initialized = False

    async def initialize(self) -> None:
        """
        Initialize ChromaDB client with persistent storage.

        Why lazy initialization?
        - Defers setup until first use
        - Faster application startup
        - Handles missing directories gracefully
        """
        if self.is_initialized:
            return

        try:
            # Create persist directory if it doesn't exist
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

            # Initialize ChromaDB with persistent storage (0.4.x API)
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )

            logger.info(f"ChromaDB initialized with persist_dir: {self.persist_dir}")
            self.is_initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise VectorDBException(f"ChromaDB initialization failed: {str(e)}")

    async def create_collection(
        self, collection_name: str, metadata: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Create a new ChromaDB collection.

        Collections are isolated storage for document embeddings.
        Each document gets its own collection.

        Args:
            collection_name: Unique name (e.g., "doc_550e8400")
            metadata: Collection metadata (document_id, filename, etc.)
            **kwargs: Additional ChromaDB parameters

        Returns:
            Collection info dict

        Raises:
            VectorDBException: If creation fails
        """
        await self.initialize()

        try:
            # Check if collection already exists
            try:
                existing = self.client.get_collection(collection_name)
                logger.info(f"Collection {collection_name} already exists")
                return {
                    "name": collection_name,
                    "status": "exists",
                    "metadata": existing.metadata
                    if hasattr(existing, "metadata")
                    else metadata,
                }
            except Exception:
                # Collection doesn't exist, create it
                pass

            # Create new collection with cosine distance (correct for BGE embeddings)
            collection_metadata = {"hnsw:space": "cosine"}
            if metadata:
                collection_metadata.update(metadata)
            self.client.create_collection(
                name=collection_name, metadata=collection_metadata, **kwargs
            )

            logger.info(
                f"Created ChromaDB collection: {collection_name} "
                f"with metadata: {metadata}"
            )

            return {"name": collection_name, "status": "created", "metadata": metadata}

        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {str(e)}")
            raise VectorDBException(f"Collection creation failed: {str(e)}")

    async def insert_chunks(
        self,
        collection_name: str,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> Dict[str, Any]:
        """
        Insert chunks with embeddings into collection.

        This is called after Phase 3 (chunking + embedding).

        Args:
            collection_name: Target collection
            documents: Chunk text content
            embeddings: 768-dim embedding vectors
            metadatas: Chunk metadata (page, position, etc.)
            ids: Unique chunk IDs

        Returns:
            Insertion status

        Raises:
            VectorDBException: If insertion fails
        """
        await self.initialize()

        try:
            collection = self.client.get_collection(collection_name)

            # Validate inputs
            if not (len(documents) == len(embeddings) == len(metadatas) == len(ids)):
                raise ValueError(
                    "Length mismatch between documents, embeddings, metadatas, ids"
                )

            # Insert chunks
            collection.add(
                documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids
            )

            logger.info(
                f"Inserted {len(documents)} chunks into collection {collection_name}"
            )

            return {
                "collection_name": collection_name,
                "chunks_inserted": len(documents),
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Failed to insert chunks into {collection_name}: {str(e)}")
            raise VectorDBException(f"Chunk insertion failed: {str(e)}")

    async def search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Tuple[
        List[str], List[List[float]], List[Dict[str, Any]], List[float], List[str]
    ]:
        """
        Semantic search in collection.

        Args:
            collection_name: Collection to search
            query_embedding: Query vector (768-dim)
            top_k: Number of results to return
            where: Metadata filter (e.g., {"page": 1})
            where_document: Text filter (e.g., {"$contains": "keyword"})

        Returns:
            Tuple of (ids, embeddings, metadatas, distances)

        Raises:
            SearchException: If search fails

        Example:
        ```python
        ids, embeddings, metadatas, distances = await search(
            collection_name="doc_123",
            query_embedding=query_vec,
            top_k=5,
            where={"page": 1}  # Only search page 1
        )

        # Distances are cosine distances (0-2, lower is more similar)
        for i, (id, meta, dist) in enumerate(zip(ids, metadatas, distances)):
            similarity = 1 - (dist / 2)  # Convert to 0-1 similarity
            print(f"Rank {i+1}: {meta['page']}.{meta['chunk_index']} "
                  f"(similarity: {similarity:.2%})")
        ```
        """
        await self.initialize()

        try:
            collection = self.client.get_collection(collection_name)

            # Query collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                where_document=where_document,
                include=["embeddings", "metadatas", "distances", "documents"],
            )

            # Extract results (ChromaDB returns lists of lists)
            ids = results.get("ids", [[]])[0]
            embeddings = results.get("embeddings", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            documents = results.get("documents", [[]])[0]

            logger.info(f"Search in {collection_name} returned {len(ids)} results")

            return ids, embeddings, metadatas, distances, documents

        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {str(e)}")
            raise SearchException(f"Search operation failed: {str(e)}")

    async def search_with_filters(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        page_number: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search with common filters.

        Convenience method for typical search patterns.

        Args:
            collection_name: Collection to search
            query_embedding: Query vector
            top_k: Results to return
            page_number: Filter by page (optional)
            min_similarity: Min similarity (0-1), filters by distance

        Returns:
            List of results with all data
        """
        where = None
        if page_number is not None:
            where = {"page_number": page_number}

        ids, embeddings, metadatas, distances, documents = await self.search(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            where=where,
        )

        results = []
        for id, emb, meta, dist, doc in zip(
            ids, embeddings, metadatas, distances, documents
        ):
            # Convert ChromaDB distance (cosine) to similarity (0-1)
            similarity = 1 - (dist / 2)

            # Skip if below minimum similarity
            if min_similarity and similarity < min_similarity:
                continue

            results.append(
                {
                    "id": id,
                    "text": doc,
                    "embedding": emb,
                    "metadata": meta,
                    "similarity": similarity,
                    "distance": dist,
                }
            )

        return results

    async def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Delete a collection (cleanup when document is deleted).

        Args:
            collection_name: Collection to delete

        Returns:
            Status dict
        """
        await self.initialize()

        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return {"collection_name": collection_name, "status": "deleted"}

        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {str(e)}")
            raise VectorDBException(f"Collection deletion failed: {str(e)}")

    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get collection metadata and stats.

        Args:
            collection_name: Collection to inspect

        Returns:
            Collection info
        """
        await self.initialize()

        try:
            collection = self.client.get_collection(collection_name)

            return {
                "name": collection_name,
                "count": collection.count(),
                "metadata": collection.metadata
                if hasattr(collection, "metadata")
                else {},
            }

        except Exception as e:
            logger.error(f"Failed to get collection info: {str(e)}")
            raise VectorDBException(f"Get collection info failed: {str(e)}")

    async def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections.

        Returns:
            List of collection names
        """
        await self.initialize()

        try:
            collections = self.client.list_collections()
            logger.info(f"Found {len(collections)} collections")

            return [
                {
                    "name": col.name,
                    "count": col.count(),
                    "metadata": col.metadata if hasattr(col, "metadata") else {},
                }
                for col in collections
            ]

        except Exception as e:
            logger.error(f"Failed to list collections: {str(e)}")
            raise VectorDBException(f"List collections failed: {str(e)}")

    async def persist(self) -> None:
        """
        No-op: ChromaDB PersistentClient auto-persists to disk.
        Kept for API compatibility.
        """
        logger.info("ChromaDB auto-persists; no manual persist needed")


# Global singleton instance — uses settings.CHROMA_PERSIST_DIR
vectordb_service = VectorDBService(persist_dir=_app_settings.CHROMA_PERSIST_DIR)
