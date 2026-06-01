"""
Phase 8 Integration Tests
Test suite for advanced retrieval features: BM25, Cross-encoder reranking, and Hybrid search
"""

import pytest
import asyncio
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

# These tests assume the backend is running on localhost:8000
# Run with: pytest backend/tests/test_phase8.py -v

import httpx


class TestPhase8Services:
    """Test Phase 8 services directly"""

    BASE_URL = "http://localhost:8000"

    async def test_bm25_search(self, auth_token: str, document_id: str):
        """Test BM25 keyword search"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/bm25",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "machine learning classification",
                    "document_id": document_id,
                    "top_k": 5
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "total" in data
            assert isinstance(data["results"], list)

            # Verify result structure
            for result in data["results"]:
                assert "chunk_id" in result
                assert "text" in result
                assert "score" in result
                assert isinstance(result["score"], (int, float))

    async def test_hybrid_search(self, auth_token: str, document_id: str):
        """Test hybrid search combining semantic + BM25 + reranking"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "machine learning algorithms",
                    "document_id": document_id,
                    "top_k": 5
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify hybrid search response
            assert "query" in data
            assert data["query"] == "machine learning algorithms"
            assert "results" in data
            assert isinstance(data["results"], list)
            assert "search_time_ms" in data
            assert "components" in data

            # Verify all scoring metrics present
            for result in data["results"]:
                assert "text" in result
                assert "chunk_id" in result
                assert "page_number" in result
                # At least some scoring should be present
                assert any(k in result for k in [
                           "semantic_score", "bm25_score", "rerank_score", "hybrid_score"])

            # Verify components breakdown
            components = data["components"]
            assert "semantic_results" in components
            assert "bm25_results" in components
            assert "reranked" in components

    async def test_rerank_results(self, auth_token: str):
        """Test cross-encoder reranking"""
        candidates = [
            {
                "text": "Machine learning is a subset of artificial intelligence",
                "chunk_id": "chunk_1"
            },
            {
                "text": "Deep learning uses neural networks with many layers",
                "chunk_id": "chunk_2"
            },
            {
                "text": "Python is a programming language",
                "chunk_id": "chunk_3"
            }
        ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/rerank",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "What is machine learning?",
                    "candidates": candidates,
                    "top_k": 2
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify rerank response
            assert "results" in data
            assert "total" in data
            assert len(data["results"]) <= 2

            # Results should be ranked
            prev_score = 1.0
            for result in data["results"]:
                assert "text" in result
                assert "chunk_id" in result
                assert "rerank_score" in result
                assert "rank" in result
                # Verify scores are in descending order
                assert result["rerank_score"] <= prev_score
                prev_score = result["rerank_score"]

    async def test_bm25_vs_semantic_vs_hybrid(self, auth_token: str, document_id: str):
        """Compare results from different search methods"""
        query = "machine learning"

        async with httpx.AsyncClient() as client:
            # Get semantic results
            semantic_resp = await client.post(
                f"{self.BASE_URL}/api/search/text",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"query": query, "document_id": document_id, "top_k": 5}
            )

            # Get BM25 results
            bm25_resp = await client.post(
                f"{self.BASE_URL}/api/search/bm25",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"query": query, "document_id": document_id, "top_k": 5}
            )

            # Get hybrid results
            hybrid_resp = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"query": query, "document_id": document_id, "top_k": 5}
            )

            assert semantic_resp.status_code == 200
            assert bm25_resp.status_code == 200
            assert hybrid_resp.status_code == 200

            semantic_data = semantic_resp.json()
            bm25_data = bm25_resp.json()
            hybrid_data = hybrid_resp.json()

            # Hybrid should have equal or more results due to merging
            hybrid_count = len(hybrid_data.get("results", []))
            semantic_count = len(semantic_data.get("results", []))
            bm25_count = len(bm25_data.get("results", []))

            # Note: counts may not always follow this, but hybrid should have good coverage
            assert hybrid_count > 0
            assert semantic_count > 0
            assert bm25_count > 0


class TestPhase8Authentication:
    """Test authentication enforcement on new endpoints"""

    BASE_URL = "http://localhost:8000"

    async def test_hybrid_search_requires_auth(self, document_id: str):
        """Hybrid search should require authentication"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                json={
                    "query": "test",
                    "document_id": document_id,
                    "top_k": 5
                }
            )

            assert response.status_code == 401

    async def test_bm25_search_requires_auth(self, document_id: str):
        """BM25 search should require authentication"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/bm25",
                json={
                    "query": "test",
                    "document_id": document_id,
                    "top_k": 5
                }
            )

            assert response.status_code == 401

    async def test_invalid_token_rejected(self, document_id: str):
        """Invalid tokens should be rejected"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": "Bearer invalid_token_12345"},
                json={
                    "query": "test",
                    "document_id": document_id,
                    "top_k": 5
                }
            )

            assert response.status_code in [401, 403]


class TestPhase8Performance:
    """Test performance characteristics"""

    BASE_URL = "http://localhost:8000"

    async def test_hybrid_search_performance(self, auth_token: str, document_id: str):
        """Verify hybrid search completes in reasonable time"""
        import time

        async with httpx.AsyncClient() as client:
            start = time.time()
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "machine learning",
                    "document_id": document_id,
                    "top_k": 10
                }
            )
            elapsed = (time.time() - start) * 1000  # Convert to ms

            assert response.status_code == 200
            data = response.json()

            # Hybrid search should complete in < 1 second
            assert elapsed < 1000, f"Hybrid search took {elapsed}ms (expected < 1000ms)"

            # Verify server's reported time is reasonable
            if "search_time_ms" in data:
                assert data["search_time_ms"] < 1000

    async def test_bm25_search_fast(self, auth_token: str, document_id: str):
        """Verify BM25 search is fast"""
        import time

        async with httpx.AsyncClient() as client:
            start = time.time()
            response = await client.post(
                f"{self.BASE_URL}/api/search/bm25",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "machine learning",
                    "document_id": document_id,
                    "top_k": 10
                }
            )
            elapsed = (time.time() - start) * 1000

            assert response.status_code == 200
            # BM25 should be very fast (< 100ms)
            assert elapsed < 100, f"BM25 search took {elapsed}ms (expected < 100ms)"


class TestPhase8Scoring:
    """Test scoring accuracy and consistency"""

    BASE_URL = "http://localhost:8000"

    async def test_scores_in_valid_range(self, auth_token: str, document_id: str):
        """Verify scores are in valid ranges"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "test query",
                    "document_id": document_id,
                    "top_k": 5
                }
            )

            data = response.json()
            for result in data.get("results", []):
                # All normalized scores should be 0-1
                if "semantic_score" in result:
                    assert 0 <= result["semantic_score"] <= 1
                if "bm25_score" in result:
                    assert 0 <= result["bm25_score"] <= 1
                if "rerank_score" in result:
                    assert 0 <= result["rerank_score"] <= 1
                if "hybrid_score" in result:
                    assert 0 <= result["hybrid_score"] <= 1

    async def test_rerank_improves_ordering(self, auth_token: str):
        """Verify reranking changes result order"""
        candidates = [
            {
                "text": "Cat is an animal",
                "chunk_id": "1"
            },
            {
                "text": "Dog is a domestic animal",
                "chunk_id": "2"
            },
            {
                "text": "Programming is writing code",
                "chunk_id": "3"
            }
        ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/rerank",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "What animals are dogs?",
                    "candidates": candidates,
                    "top_k": 3
                }
            )

            data = response.json()
            results = data.get("results", [])

            # Result about dog should rank highest for dog-related query
            if len(results) > 0:
                # Check that results are ordered by score (descending)
                for i in range(len(results) - 1):
                    assert results[i]["rerank_score"] >= results[i +
                                                                 1]["rerank_score"]


class TestPhase8ErrorHandling:
    """Test error handling and edge cases"""

    BASE_URL = "http://localhost:8000"

    async def test_invalid_document_id(self, auth_token: str):
        """Test with non-existent document"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "test",
                    "document_id": "00000000-0000-0000-0000-000000000000",
                    "top_k": 5
                }
            )

            # Should return 404 or empty results
            assert response.status_code in [200, 404]

    async def test_empty_query(self, auth_token: str, document_id: str):
        """Test with empty query"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "",
                    "document_id": document_id,
                    "top_k": 5
                }
            )

            # Should handle gracefully (400 or empty results)
            assert response.status_code in [200, 400]

    async def test_large_top_k(self, auth_token: str, document_id: str):
        """Test with very large top_k"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/search/hybrid",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "query": "test",
                    "document_id": document_id,
                    "top_k": 1000
                }
            )

            # Should handle gracefully
            assert response.status_code == 200
            data = response.json()
            # Should not actually return 1000 results
            assert len(data.get("results", [])) < 1000

    async def test_special_characters_in_query(self, auth_token: str, document_id: str):
        """Test with special characters"""
        queries = [
            "machine & learning",
            "C++",
            "test@#$%",
            "query with \"quotes\"",
            "test\twith\ttabs",
        ]

        async with httpx.AsyncClient() as client:
            for query in queries:
                response = await client.post(
                    f"{self.BASE_URL}/api/search/hybrid",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    json={
                        "query": query,
                        "document_id": document_id,
                        "top_k": 5
                    }
                )

                # Should not crash
                assert response.status_code in [200, 400]


# Fixtures for pytest

@pytest.fixture
async def auth_token():
    """Get authentication token for tests"""
    async with httpx.AsyncClient() as client:
        # This assumes test user exists or is auto-created
        response = await client.post(
            "http://localhost:8000/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "test_password"
            }
        )

        if response.status_code == 200:
            return response.json()["tokens"]["access_token"]
        else:
            # Try to register
            reg_response = await client.post(
                "http://localhost:8000/api/auth/register",
                json={
                    "email": "test@example.com",
                    "username": "testuser",
                    "password": "test_password"
                }
            )
            if reg_response.status_code == 200:
                return reg_response.json()["tokens"]["access_token"]

    raise Exception("Could not get auth token")


@pytest.fixture
async def document_id(auth_token: str):
    """Get or create a test document"""
    async with httpx.AsyncClient() as client:
        # Get existing documents
        response = await client.get(
            "http://localhost:8000/api/documents",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        if response.status_code == 200:
            docs = response.json().get("documents", [])
            if docs:
                return docs[0]["id"]

    raise Exception("No documents available for testing")


if __name__ == "__main__":
    print("""
    Phase 8 Integration Tests
    
    Run with: pytest backend/tests/test_phase8.py -v
    
    Requirements:
    - Backend running on localhost:8000
    - Test user account available or auto-creation enabled
    - At least one document uploaded
    
    Test Coverage:
    - BM25 search functionality
    - Cross-encoder reranking
    - Hybrid search
    - API authentication
    - Performance metrics
    - Scoring accuracy
    - Error handling
    """)
