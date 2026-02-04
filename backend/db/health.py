"""
Database health check utilities.

Provides functions to check database connectivity, pool status,
and overall database health for monitoring.
"""

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
from sqlalchemy import text


async def check_postgres_connection(
    host: str = None,
    port: int = None,
    user: str = None,
    password: str = None,
    database: str = None,
    ssl_mode: str = "prefer",
) -> Dict[str, Any]:
    """
    Check PostgreSQL connection health.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        user: PostgreSQL user
        password: PostgreSQL password
        database: Database name
        ssl_mode: SSL mode (disable, allow, prefer, require)

    Returns:
        Dictionary with health check results.
    """
    host = host or os.getenv("POSTGRES_HOST", "localhost")
    port = port or int(os.getenv("POSTGRES_PORT", "5432"))
    user = user or os.getenv("POSTGRES_USER", "specgen")
    password = password or os.getenv("POSTGRES_PASSWORD", "password")
    database = database or os.getenv("POSTGRES_DB", "specgen")
    ssl_mode = os.getenv("POSTGRES_SSL_MODE", ssl_mode)

    start_time = time.time()
    connection = None

    try:
        # Establish connection
        connection = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl=ssl_mode == "require",
        )

        # Execute health check query
        version = await connection.fetchval("SELECT version()")
        await connection.fetchval("SELECT 1")

        # Get connection info
        connection_info = connection.get_connection_info()

        elapsed_time = (time.time() - start_time) * 1000  # ms

        return {
            "status": "healthy",
            "database": "postgresql",
            "version": version,
            "connection_time_ms": round(elapsed_time, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "host": host,
                "port": port,
                "database": database,
                "ssl_mode": ssl_mode,
            },
        }

    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "error": str(e),
            "connection_time_ms": round(elapsed_time, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "host": host,
                "port": port,
                "database": database,
            },
        }

    finally:
        if connection:
            await connection.close()


async def check_pgbouncer_connection(
    host: str = None,
    port: int = None,
    user: str = None,
    password: str = None,
    database: str = None,
) -> Dict[str, Any]:
    """
    Check PgBouncer connection health.

    Args:
        host: PgBouncer host
        port: PgBouncer port
        user: PgBouncer user
        password: PgBouncer password
        database: Database name

    Returns:
        Dictionary with health check results.
    """
    host = host or os.getenv("PGBOUNCER_HOST", "localhost")
    port = port or int(os.getenv("PGBOUNCER_PORT", "6432"))
    user = user or os.getenv("PGBOUNCER_USER", "specgen")
    password = password or os.getenv("PGBOUNCER_PASSWORD", "password")
    database = database or os.getenv("POSTGRES_DB", "specgen")

    start_time = time.time()
    connection = None

    try:
        connection = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )

        # Check PgBouncer stats
        stats = await connection.fetch(
            "SELECT * FROM pgbouncer.get_stats()"
        )

        # Get pool status
        pools = await connection.fetch(
            "SELECT * FROM pgbouncer.get_pools()"
        )

        elapsed_time = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "database": "pgbouncer",
            "connection_time_ms": round(elapsed_time, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "host": host,
                "port": port,
                "stats": [dict(s) for s in stats],
                "pools": [dict(p) for p in pools],
            },
        }

    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        return {
            "status": "unhealthy",
            "database": "pgbouncer",
            "error": str(e),
            "connection_time_ms": round(elapsed_time, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }


def get_connection_pool_status() -> Dict[str, Any]:
    """
    Get SQLAlchemy connection pool status.

    Returns:
        Dictionary with pool status information.
    """
    from backend.db.connection import async_engine

    pool = async_engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "max_overflow": pool.max_overflow,
        "status": "healthy" if pool.checkedout() < pool.size() + pool.max_overflow else "warning",
    }


async def check_all_databases() -> Dict[str, Any]:
    """
    Check health of all databases.

    Returns:
        Dictionary with health status of all databases.
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }

    # Check PostgreSQL
    pg_health = await check_postgres_connection()
    results["checks"]["postgresql"] = pg_health

    # Check PgBouncer
    pgb_health = await check_pgbouncer_connection()
    results["checks"]["pgbouncer"] = pgb_health

    # Overall status
    all_healthy = all(
        check.get("status") == "healthy"
        for check in results["checks"].values()
    )
    results["status"] = "healthy" if all_healthy else "degraded"

    return results


async def check_readiness() -> bool:
    """
    Check if the database is ready to accept requests.

    Returns:
        True if ready, False otherwise.
    """
    try:
        health = await check_postgres_connection()
        return health.get("status") == "healthy"
    except Exception:
        return False


async def check_liveness() -> bool:
    """
    Check if the database service is alive.

    Returns:
        True if alive, False otherwise.
    """
    try:
        # Just check if we can connect, don't perform a query
        health = await check_postgres_connection()
        # Consider it alive if we got a response (even if error in details)
        return "version" in health or health.get("status") == "healthy"
    except Exception:
        return False


# Health check for Kubernetes probes
class DatabaseHealthChecker:
    """Health checker for database services."""

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
        """Detailed health check with all metrics."""
        return await check_all_databases()
