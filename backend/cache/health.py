"""
Redis health check utilities.

Provides functions to check Redis connectivity,
cluster status, and performance metrics.
"""

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis


async def check_redis_connection(
    host: str = None,
    port: int = None,
    db: int = None,
    password: str = None,
) -> Dict[str, Any]:
    """
    Check Redis connection health.

    Args:
        host: Redis host
        port: Redis port
        db: Redis database number
        password: Redis password

    Returns:
        Dictionary with health check results.
    """
    host = host or os.getenv("REDIS_HOST", "localhost")
    port = port or int(os.getenv("REDIS_PORT", "6379"))
    db = db or int(os.getenv("REDIS_DB", "0"))
    password = password or os.getenv("REDIS_PASSWORD", "")

    start_time = time.time()
    client = None

    try:
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password or None,
            socket_timeout=5,
            socket_connect_timeout=5,
        )

        # Test connection
        pong = await client.ping()
        info = await client.info("all")

        elapsed_time = (time.time() - start_time) * 1000

        return {
            "status": "healthy" if pong else "unhealthy",
            "redis": "connected",
            "version": info.get("redis_version"),
            "connection_time_ms": round(elapsed_time, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "host": host,
                "port": port,
                "db": db,
                "role": info.get("role"),
                "connected_clients": info.get("connected_clients"),
                "used_memory": info.get("used_memory_human"),
                "total_connections_received": info.get("total_connections_received"),
            },
        }

    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "redis": "disconnected",
            "error": str(e),
            "connection_time_ms": round(elapsed_time, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "host": host,
                "port": port,
                "db": db,
            },
        }

    finally:
        if client:
            await client.close()


async def check_redis_performance(
    host: str = None,
    port: int = None,
    password: str = None,
) -> Dict[str, Any]:
    """
    Check Redis performance metrics.

    Args:
        host: Redis host
        port: Redis port
        password: Redis password

    Returns:
        Dictionary with performance metrics.
    """
    host = host or os.getenv("REDIS_HOST", "localhost")
    port = port or int(os.getenv("REDIS_PORT", "6379"))
    password = password or os.getenv("REDIS_PASSWORD", "")

    client = redis.Redis(
        host=host,
        port=port,
        password=password or None,
    )

    try:
        # Get performance info
        info = await client.info([
            "stats",
            "memory",
            "clients",
            "persistence",
            "replication",
        ])

        # Test latency
        latencies = []
        for _ in range(5):
            start = time.time()
            await client.ping()
            latency = (time.time() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "avg_latency_ms": round(avg_latency, 2),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
                "hit_rate": round(
                    info.get("keyspace_hits", 0) /
                    max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)) * 100,
                    2,
                ),
                "used_memory": info.get("used_memory_human"),
                "used_memory_peak": info.get("used_memory_peak_human"),
                "connected_clients": info.get("connected_clients"),
                "blocked_clients": info.get("blocked_clients"),
                "expired_keys": info.get("expired_keys"),
                "evicted_keys": info.get("evicted_keys"),
                "rdb_changes_since_last_save": info.get("rdb_changes_since_last_save"),
            },
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }

    finally:
        await client.close()


async def check_redis_all() -> Dict[str, Any]:
    """
    Check all Redis health metrics.

    Returns:
        Dictionary with all health checks.
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }

    # Check connection
    connection = await check_redis_connection()
    results["checks"]["connection"] = connection

    # Check performance
    performance = await check_redis_performance()
    results["checks"]["performance"] = performance

    # Overall status
    all_healthy = all(
        check.get("status") == "healthy"
        for check in results["checks"].values()
    )
    results["status"] = "healthy" if all_healthy else "degraded"

    return results


async def check_readiness() -> bool:
    """
    Check if Redis is ready.

    Returns:
        True if ready, False otherwise.
    """
    try:
        health = await check_redis_connection()
        return health.get("status") == "healthy"
    except Exception:
        return False


async def check_liveness() -> bool:
    """
    Check if Redis is alive.

    Returns:
        True if alive, False otherwise.
    """
    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD", "") or None,
        )
        pong = await client.ping()
        await client.close()
        return pong
    except Exception:
        return False


class RedisHealthChecker:
    """Health checker for Redis service."""

    @staticmethod
    async def liveness_probe() -> Dict[str, Any]:
        """Kubernetes liveness probe."""
        return {
            "status": "alive" if await check_liveness() else "dead",
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def readiness_probe() -> Dict[str, Any]:
        """Kubernetes readiness probe."""
        is_ready = await check_readiness()
        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def detailed_health() -> Dict[str, Any]:
        """Detailed health check."""
        return await check_redis_all()
