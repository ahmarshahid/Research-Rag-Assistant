"""
Redis cache client for session management, caching, and rate limiting.

Why Redis?
- Sub-millisecond latency: Perfect for response caching
- Session storage: Store JWT tokens for quick validation
- Rate limiting: Track API usage per user
- Embedding cache: Cache expensive embedding calculations
"""

import json
from typing import Any, Optional
from redis import asyncio as aioredis
from app.config import settings
from app.utils.errors import CacheConnectionError
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Singleton Redis client for application-wide use."""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf8",
                decode_responses=True,
            )
            # Test connection
            await self.redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise CacheConnectionError()

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")

    async def ping(self):
        """Test Redis connection."""
        if not self.redis:
            raise CacheConnectionError()
        return await self.redis.ping()

    # ==== KEY-VALUE OPERATIONS ====

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self.redis:
            return None
        return await self.redis.get(key)

    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from cache."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: str, ttl: int = None):
        """Set value in cache with optional TTL."""
        if not self.redis:
            return

        ttl = ttl or settings.REDIS_CACHE_TTL
        await self.redis.setex(key, ttl, value)

    async def set_json(self, key: str, value: Any, ttl: int = None):
        """Set JSON value in cache with optional TTL."""
        json_value = json.dumps(value, default=str)
        await self.set(key, json_value, ttl)

    async def delete(self, key: str):
        """Delete key from cache."""
        if not self.redis:
            return
        await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            return False
        return await self.redis.exists(key) > 0

    async def expire(self, key: str, ttl: int):
        """Set TTL for existing key."""
        if not self.redis:
            return
        await self.redis.expire(key, ttl)

    # ==== SESSION OPERATIONS ====

    async def set_session(self, user_id: str, session_data: dict, ttl: int = 86400):
        """Store user session in cache (24 hours default)."""
        key = f"session:{user_id}"
        await self.set_json(key, session_data, ttl)

    async def get_session(self, user_id: str) -> Optional[dict]:
        """Retrieve user session from cache."""
        key = f"session:{user_id}"
        return await self.get_json(key)

    async def invalidate_session(self, user_id: str):
        """Invalidate user session."""
        key = f"session:{user_id}"
        await self.delete(key)

    # ==== RATE LIMITING OPERATIONS ====

    async def increment_rate_limit(self, user_id: str, endpoint: str, limit: int = 100, window: int = 60) -> int:
        """
        Check and increment rate limit counter.

        Args:
            user_id: User ID
            endpoint: API endpoint
            limit: Max requests in window
            window: Time window in seconds

        Returns:
            Current count

        Raises:
            RateLimitException: If limit exceeded
        """
        from app.utils.errors import RateLimitException

        key = f"rate_limit:{user_id}:{endpoint}"
        count = await self.redis.incr(key)

        # Set TTL on first increment
        if count == 1:
            await self.redis.expire(key, window)

        if count > limit:
            raise RateLimitException(retry_after=window)

        return count

    # ==== CACHE OPERATIONS ====

    async def cache_query_result(self, query_hash: str, user_id: str, result: Any, ttl: int = 300):
        """Cache query search results (5 min default)."""
        key = f"query_cache:{query_hash}:{user_id}"
        await self.set_json(key, result, ttl)

    async def get_cached_query_result(self, query_hash: str, user_id: str) -> Optional[dict]:
        """Get cached query results."""
        key = f"query_cache:{query_hash}:{user_id}"
        return await self.get_json(key)

    async def cache_embeddings(self, text_hash: str, embeddings: list, ttl: int = 2592000):
        """Cache embeddings for 30 days."""
        key = f"embedding:{text_hash}"
        await self.set_json(key, embeddings, ttl)

    async def get_cached_embeddings(self, text_hash: str) -> Optional[list]:
        """Get cached embeddings."""
        key = f"embedding:{text_hash}"
        value = await self.get_json(key)
        return value if isinstance(value, list) else None

    # ==== QUEUE OPERATIONS (for background tasks) ====

    async def push_queue(self, queue_name: str, item: Any):
        """Push item to queue."""
        if not self.redis:
            return
        await self.redis.rpush(queue_name, json.dumps(item, default=str))

    async def pop_queue(self, queue_name: str) -> Optional[dict]:
        """Pop item from queue."""
        if not self.redis:
            return None

        item = await self.redis.lpop(queue_name)
        if item:
            return json.loads(item)
        return None

    async def queue_length(self, queue_name: str) -> int:
        """Get queue length."""
        if not self.redis:
            return 0
        return await self.redis.llen(queue_name)


# Global Redis client instance
redis_client = RedisClient()
