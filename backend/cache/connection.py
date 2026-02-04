"""
Redis connection and pool management.

Provides:
- Redis client with connection pooling
- Async/sync Redis operations
- Connection health checks
- Session and cache key prefixes
"""

import os
from typing import AsyncGenerator, Optional

import redis.asyncio as redis
import redis as redis_sync
from redis.connection import ConnectionPool

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# Connection pool settings
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "100"))
REDIS_SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
REDIS_SOCKET_CONNECT_TIMEOUT = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))

# Key prefixes
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "specgen:")
SESSION_PREFIX = f"{REDIS_KEY_PREFIX}session:"
CACHE_PREFIX = f"{REDIS_KEY_PREFIX}cache:"
RATE_LIMIT_PREFIX = f"{REDIS_KEY_PREFIX}ratelimit:"
LOCK_PREFIX = f"{REDIS_KEY_PREFIX}lock:"

# TTL settings (in seconds)
DEFAULT_CACHE_TTL = int(os.getenv("DEFAULT_CACHE_TTL", "300"))  # 5 minutes
SESSION_TTL = int(os.getenv("SESSION_TTL", "86400"))  # 24 hours
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 1 minute


# Async Redis client
async_redis_pool: Optional[ConnectionPool] = None
async_redis_client: Optional[redis.Redis] = None


async def init_redis() -> redis.Redis:
    """
    Initialize async Redis client with connection pooling.

    Returns:
        Async Redis client instance.
    """
    global async_redis_pool, async_redis_client

    if async_redis_client is not None:
        return async_redis_client

    async_redis_pool = ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD or None,
        max_connections=REDIS_MAX_CONNECTIONS,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
        decode_responses=True,
    )

    async_redis_client = redis.Redis(connection_pool=async_redis_pool)

    # Test connection
    await async_redis_client.ping()

    return async_redis_client


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """
    Dependency that provides an async Redis client.

    Usage:
        @app.get("/")
        async def endpoint(redis: redis.Redis = Depends(get_redis)):
            await redis.get("key")
    """
    global async_redis_client

    if async_redis_client is None:
        await init_redis()

    yield async_redis_client


async def get_redis_pool() -> ConnectionPool:
    """
    Get the Redis connection pool.

    Returns:
        Redis connection pool.
    """
    global async_redis_pool

    if async_redis_pool is None:
        await init_redis()

    return async_redis_pool


async def close_redis() -> None:
    """
    Close Redis connections.

    Call this on application shutdown.
    """
    global async_redis_pool, async_redis_client

    if async_redis_client is not None:
        await async_redis_client.close()
        async_redis_client = None

    if async_redis_pool is not None:
        await async_redis_pool.disconnect()
        async_redis_pool = None


# Sync Redis client (for scripts and migrations)
_sync_redis_client: Optional[redis_sync.Redis] = None


def get_sync_redis() -> redis_sync.Redis:
    """
    Get sync Redis client.

    Returns:
        Sync Redis client instance.
    """
    global _sync_redis_client

    if _sync_redis_client is None:
        _sync_redis_client = redis_sync.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
            decode_responses=True,
        )

    return _sync_redis_client


def close_sync_redis() -> None:
    """
    Close sync Redis client.
    """
    global _sync_redis_client

    if _sync_redis_client is not None:
        _sync_redis_client.close()
        _sync_redis_client = None


# Legacy compatibility
redis_client = get_sync_redis
