"""
Database connection and session management for SQLAlchemy with async support.

This module provides:
- Async SQLAlchemy engine configuration with connection pooling
- Session factory for dependency injection
- Health check utilities
- Database initialization and cleanup
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

# Async database URL (for FastAPI)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://specgen:password@localhost:6432/specgen",
)

# Sync database URL (for Alembic migrations)
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://specgen:password@localhost:6432/specgen",
)

# Pool configuration
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))

# SSL configuration
POSTGRES_SSL_MODE = os.getenv("POSTGRES_SSL_MODE", "prefer")
POSTGRES_SSL_CERT = os.getenv("POSTGRES_SSL_CERT", "")
POSTGRES_SSL_KEY = os.getenv("POSTGRES_SSL_KEY", "")
POSTGRES_SSL_ROOT_CERT = os.getenv("POSTGRES_SSL_ROOT_CERT", "")


def _get_ssl_kwargs() -> dict:
    """Build SSL kwargs for asyncpg driver."""
    ssl_kwargs = {}
    if POSTGRES_SSL_MODE == "require":
        ssl_kwargs["ssl"] = "require"
    elif POSTGRES_SSL_MODE == "verify-ca":
        ssl_kwargs["ssl"] = True
        if POSTGRES_SSL_ROOT_CERT:
            ssl_kwargs["ssl"] = {
                "ca": POSTGRES_SSL_ROOT_CERT,
            }
    elif POSTGRES_SSL_MODE == "verify-full":
        ssl_kwargs["ssl"] = True
        if POSTGRES_SSL_ROOT_CERT:
            ssl_kwargs["ssl"] = {
                "ca": POSTGRES_SSL_ROOT_CERT,
                "check_hostname": True,
                "server_hostname": os.getenv("POSTGRES_HOST", "localhost"),
            }
    return ssl_kwargs


# Async engine for production use
async_engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("APP_ENV", "development") == "development",
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
    poolclass=AsyncAdaptedQueuePool,
    **_get_ssl_kwargs(),
)

# Async session factory for dependency injection
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Sync engine for migrations and scripts
sync_engine = create_engine(
    DATABASE_URL_SYNC,
    echo=os.getenv("APP_ENV", "development") == "development",
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
)

# Sync session factory
sync_session_factory = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.

    Usage:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            await db.execute(select(User))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Alternative dependency for manual session management.

    Usage:
        async with get_db_session() as session:
            await session.execute(select(User))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.

    Usage:
        async with get_db_context() as session:
            await session.execute(select(User))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables.

    This function should be called on application startup to create
    all tables defined in the metadata.
    """
    from backend.db.base import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections.

    This function should be called on application shutdown to properly
    dispose of all database connections.
    """
    await async_engine.dispose()
    sync_engine.dispose()


def get_pool_status() -> dict:
    """
    Get connection pool status for monitoring.

    Returns:
        Dictionary with pool status information.
    """
    pool = async_engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "max_overflow": pool.max_overflow,
    }


# Event listeners for debugging (development only)
if os.getenv("APP_ENV", "development") == "development":

    @event.listens_for(sync_engine.sync_engine, "connect")
    def set_session_vars(dbapi_connection, connection_record):
        """Set session variables on connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("SELECT set_config('app.name', 'specgen', false)")
        cursor.close()
