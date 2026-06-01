"""
Web Search Service - Phase 8: Advanced Retrieval

Augments document search with web search results via Serper API.
Useful for queries outside the document corpus.

Features:
- Real-time web search
- News and knowledge graph integration  
- Snippet extraction
- Relevance ranking
- Combined results from web + documents

Serper API:
- Fast, reliable Google Search API
- ~0.1$ per 1000 queries
- Includes organic results, news, knowledge panels
"""

from typing import List, Dict, Any, Optional
import httpx
import logging
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchException(Exception):
    """Web search specific exception"""
    pass


class WebSearchService:
    """
    Web search service using Serper API.

    Serper provides Google Search results via API.
    Useful for augmenting document search with external information.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize web search service.

        Args:
            api_key: Serper API key (from environment if not provided)
        """
        import os
        self.api_key = api_key or os.getenv("SERPER_API_KEY")
        self.base_url = "https://google.serper.dev"
        self.enabled = bool(self.api_key)

        if not self.enabled:
            logger.warning("Serper API key not found. Web search disabled.")
        else:
            logger.info("Web search service initialized")

    async def search(
        self,
        query: str,
        num_results: int = 5,
        include_news: bool = False,
        include_knowledge: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search the web using Serper API.

        Args:
            query: Search query
            num_results: Number of results to return
            include_news: Include news results
            include_knowledge: Include knowledge panel

        Returns:
            List of search results

        Result format:
            {
                "title": "...",
                "snippet": "...",
                "link": "...",
                "date": "...",  # For news
                "source": "web|news|knowledge",
                "relevance_score": 0.95  # Calculated score
            }
        """
        if not self.enabled:
            logger.info("Web search disabled (API key not configured)")
            return []

        try:
            logger.info(f"Web search for: '{query}'")

            # Build request payload
            payload = {
                "q": query,
                "gl": "us",
                "hl": "en",
                "num": num_results,
                "autocorrect": True,
                "page": 1,
                "type": "search"
            }

            # Build headers
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }

            # Make request
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()

            results = []

            # Extract organic results
            if "organic" in data:
                for idx, result in enumerate(data.get("organic", [])[:num_results]):
                    results.append({
                        "source": "web",
                        "title": result.get("title", ""),
                        "snippet": result.get("snippet", ""),
                        "link": result.get("link", ""),
                        "position": result.get("position", idx + 1),
                        "relevance_score": self._calculate_score(idx, len(results)),
                        "date": result.get("date"),
                        "type": "organic"
                    })

            # Extract news results if requested
            if include_news and "news" in data:
                for idx, result in enumerate(data.get("news", [])[:3]):
                    results.append({
                        "source": "news",
                        "title": result.get("title", ""),
                        "snippet": result.get("snippet", ""),
                        "link": result.get("link", ""),
                        "date": result.get("date"),
                        "relevance_score": self._calculate_score(idx, len(results)),
                        "type": "news"
                    })

            # Extract knowledge panel if requested
            if include_knowledge and "knowledgeGraph" in data:
                kg = data["knowledgeGraph"]
                results.append({
                    "source": "knowledge",
                    "title": kg.get("title", ""),
                    "snippet": kg.get("description", ""),
                    "link": kg.get("website", ""),
                    "relevance_score": 1.0,
                    "attributes": kg.get("attributes", {}),
                    "type": "knowledge"
                })

            logger.info(f"Web search returned {len(results)} results")
            return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.error("Serper API: Invalid API key or quota exceeded")
                raise WebSearchException("API key invalid or quota exceeded")
            elif e.response.status_code == 429:
                logger.error("Serper API: Rate limited")
                raise WebSearchException("Rate limited - try again later")
            else:
                logger.error(f"Serper API error: {e.response.status_code}")
                raise WebSearchException(
                    f"API error: {e.response.status_code}")

        except Exception as e:
            logger.error(f"Web search error: {str(e)}", exc_info=True)
            raise WebSearchException(f"Search failed: {str(e)}")

    async def search_with_context(
        self,
        query: str,
        context: Optional[str] = None,
        num_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search with optional context for better results.

        Args:
            query: Search query
            context: Additional context to improve relevance
            num_results: Number of results

        Returns:
            Search results with context consideration
        """
        # Optionally enhance query with context
        enhanced_query = query
        if context:
            enhanced_query = f"{query} {context}"
            logger.info(f"Enhanced query: '{enhanced_query}'")

        return await self.search(enhanced_query, num_results=num_results)

    @staticmethod
    def _calculate_score(position: int, total_results: int) -> float:
        """
        Calculate relevance score based on position.

        First results get higher scores.
        """
        if total_results == 0:
            return 0.0

        # Linear decay from 1.0 to 0.1
        return max(0.1, 1.0 - (position / total_results))

    def is_enabled(self) -> bool:
        """Check if web search is enabled."""
        return self.enabled


# Singleton instance
web_search_service = WebSearchService()
