"""
Redis cache service.

Provides:
- Key-value caching with TTL
- Cache-aside pattern implementation
- Cache invalidation
- Distributed locking
"""

import hashlib
import json
import os
from datetime import timedelta
from typing import Any, Optional, Union

import redis.asyncio as redis

from backend.cache.connection import (
    init_redis,
    get_redis,
    CACHE_PREFIX,
    LOCK_PREFIX,
    DEFAULT_CACHE_TTL,
)


class CacheService:
    """
    Redis-based cache service.

    Features:
    - Automatic serialization/deserialization
    - Configurable TTL
    - Cache key generation
    - Distributed locking for cache stampede prevention
    """

    def __init__(self, redis_client: redis.Redis = None):
        """
        Initialize cache service.

        Args:
            redis_client: Optional Redis client
        """
        self.redis = redis_client
        self.prefix = CACHE_PREFIX
        self.lock_prefix = LOCK_PREFIX
        self.default_ttl = DEFAULT_CACHE_TTL

    async def get_client(self) -> redis.Redis:
        """Get Redis client."""
        if self.redis is None:
            self.redis = await init_redis()
        return self.redis

    def _make_key(self, key: str) -> str:
        """Generate cache key with prefix."""
        return f"{self.prefix}{key}"

    def _serialize(self, value: Any) -> str:
        """Serialize value for storage."""
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return json.dumps(value, default=str)

    def _deserialize(self, value: str) -> Any:
        """Deserialize stored value."""
        if value is None:
            return None

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def _hash_key(self, key: str) -> str:
        """Generate hash for complex keys."""
        return hashlib.md5(key.encode()).hexdigest()

    async def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        client = await self.get_client()
        full_key = self._make_key(key)

        value = await client.get(full_key)

        if value is None:
            return default

        return self._deserialize(value)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        nx: bool = False,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            nx: Only set if not exists

        Returns:
            True if set, False if not set (nx=True and key exists)
        """
        client = await self.get_client()
        full_key = self._make_key(key)
        serialized = self._serialize(value)
        ttl = ttl or self.default_ttl

        if ttl <= 0:
            return False

        if nx:
            return await client.setnx(full_key, serialized)

        await client.setex(full_key, ttl, serialized)
        return True

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        client = await self.get_client()
        full_key = self._make_key(key)

        result = await client.delete(full_key)
        return result > 0

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        client = await self.get_client()
        full_pattern = self._make_key(pattern)

        keys = await client.keys(full_pattern)

        if not keys:
            return 0

        return await client.delete(*keys)

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists, False otherwise
        """
        client = await self.get_client()
        full_key = self._make_key(key)

        return await client.exists(full_key) > 0

    async def ttl(self, key: str) -> int:
        """
        Get remaining TTL for key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        client = await self.get_client()
        full_key = self._make_key(key)

        return await client.ttl(full_key)

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set TTL for key.

        Args:
            key: Cache key
            ttl: TTL in seconds

        Returns:
            True if TTL was set, False if key doesn't exist
        """
        client = await self.get_client()
        full_key = self._make_key(key)

        return await client.expire(full_key, ttl)

    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment value.

        Args:
            key: Cache key
            amount: Increment amount

        Returns:
            New value
        """
        client = await self.get_client()
        full_key = self._make_key(key)

        return await client.incrby(full_key, amount)

    async def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrement value.

        Args:
            key: Cache key
            amount: Decrement amount

        Returns:
            New value
        """
        client = await self.get_client()
        full_key = self._make_key(key)

        return await client.decrby(full_key, amount)

    async def get_or_set(
        self,
        key: str,
        factory,
        ttl: int = None,
    ) -> Any:
        """
        Get value from cache or set using factory.

        Implements cache-aside pattern.

        Args:
            key: Cache key
            factory: Async function to get value if not cached
            ttl: TTL in seconds

        Returns:
            Cached or computed value
        """
        value = await self.get(key)

        if value is not None:
            return value

        value = await factory()
        await self.set(key, value, ttl)

        return value

    async def lock(
        self,
        lock_name: str,
        timeout: int = 10,
        blocking_timeout: int = None,
    ):
        """
        Acquire distributed lock.

        Args:
            lock_name: Lock name
            timeout: Lock timeout in seconds
            blocking_timeout: How long to wait for lock

        Returns:
            Lock object or None if not acquired
        """
        client = await self.get_client()
        full_lock_name = f"{self.lock_prefix}{lock_name}"

        lock = client.lock(
            full_lock_name,
            timeout=timeout,
            blocking_timeout=blocking_timeout,
        )

        acquired = await lock.acquire()
        if acquired:
            return lock

        return None

    # Convenience methods for common caching patterns

    async def cache_decision(
        self,
        project_id: str,
        decision_id: str,
        data: Any,
        ttl: int = None,
    ) -> bool:
        """Cache decision data."""
        key = f"decision:{project_id}:{decision_id}"
        return await self.set(key, data, ttl)

    async def get_decision(
        self,
        project_id: str,
        decision_id: str,
    ) -> Any:
        """Get cached decision."""
        key = f"decision:{project_id}:{decision_id}"
        return await self.get(key)

    async def cache_artifact(
        self,
        project_id: str,
        artifact_id: str,
        data: Any,
        ttl: int = None,
    ) -> bool:
        """Cache artifact data."""
        key = f"artifact:{project_id}:{artifact_id}"
        return await self.set(key, data, ttl)

    async def get_artifact(
        self,
        project_id: str,
        artifact_id: str,
    ) -> Any:
        """Get cached artifact."""
        key = f"artifact:{project_id}:{artifact_id}"
        return await self.get(key)

    async def invalidate_project_cache(
        self,
        project_id: str,
    ) -> int:
        """Invalidate all cached data for a project."""
        return await self.delete_pattern(f"*:{project_id}:*")


# Cache service instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get cache service instance."""
    global _cache_service

    if _cache_service is None:
        _cache_service = CacheService()

    return _cache_service
