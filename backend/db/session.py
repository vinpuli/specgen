"""
Additional database session management utilities.

This module provides:
- Session context managers for transactions
- Retry logic for transient failures
- Session health checks
- Bulk operations support
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, TypeVar
import logging

from sqlalchemy import select, event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import (
    DatabaseError,
    DisconnectionError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm import selectinload

from backend.db.connection import async_session_factory, get_pool_status

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DatabaseSessionManager:
    """
    Enhanced database session manager with retry logic and transaction support.
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
    ):
        """
        Initialize the session manager.

        Args:
            max_retries: Maximum number of retry attempts for transient failures.
            retry_delay: Initial delay between retries (seconds).
            retry_backoff: Multiplier for delay after each retry.
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff

    @asynccontextmanager
    async def session(
        self,
        use_retry: bool = True,
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session with automatic commit/rollback.

        Args:
            use_retry: Whether to use retry logic for transient failures.

        Yields:
            AsyncSession instance.
        """
        session = async_session_factory()
        try:
            yield session
            await session.commit()
        except (DatabaseError, DisconnectionError, OperationalError) as e:
            if use_retry and self.max_retries > 0:
                logger.warning(
                    f"Transient database error, retrying: {e}"
                )
                await session.rollback()
                await self._retry_with_backoff(session)
            else:
                await session.rollback()
                raise
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def transaction(
        self,
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a session within an explicit transaction.

        Usage:
            async with session_manager.transaction() as tx_session:
                await tx_session.execute(select(User))
                await tx_session.commit()  # Explicit commit

        Yields:
            AsyncSession instance within a transaction.
        """
        async with async_session_factory() as session:
            async with session.begin():
                yield session

    async def _retry_with_backoff(
        self,
        session: AsyncSession,
    ) -> None:
        """
        Retry the current operation with exponential backoff.

        Args:
            session: The session to retry with.
        """
        for attempt in range(self.max_retries):
            try:
                await session.commit()
                logger.info(
                    f"Retry successful on attempt {attempt + 1}"
                )
                return
            except (DatabaseError, DisconnectionError, OperationalError) as e:
                delay = self.retry_delay * (self.retry_backoff**attempt)
                logger.warning(
                    f"Retry attempt {attempt + 1} failed: {e}, "
                    f"retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)
        raise OperationalError(
            "Max retries exceeded for database operation",
            params=None,
            orig=None,
        )


# Global session manager instance
session_manager = DatabaseSessionManager()


async def get_health_status() -> dict[str, Any]:
    """
    Get database health status.

    Returns:
        Dictionary with health information.
    """
    pool_status = get_pool_status()

    # Check if we can execute a simple query
    try:
        async with session_manager.session() as session:
            await session.execute(select(1))
            is_healthy = True
            error_message = None
    except Exception as e:
        is_healthy = False
        error_message = str(e)

    return {
        "healthy": is_healthy,
        "error": error_message,
        "pool": pool_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def execute_with_retry(
    session: AsyncSession,
    operation: Callable[[AsyncSession], T],
    max_retries: int = 3,
) -> T:
    """
    Execute a database operation with retry logic.

    Args:
        session: The database session.
        operation: The operation to execute.
        max_retries: Maximum retry attempts.

    Returns:
        Result of the operation.

    Raises:
        SQLAlchemyError: If all retries fail.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await operation(session)
        except (DatabaseError, DisconnectionError, OperationalError) as e:
            last_error = e
            delay = 1.0 * (2**attempt)
            logger.warning(
                f"Operation failed on attempt {attempt + 1}, "
                f"retrying in {delay:.2f}s: {e}"
            )
            await asyncio.sleep(delay)

    raise last_error


async def bulk_insert(
    session: AsyncSession,
    objects: list[Any],
    batch_size: int = 1000,
) -> int:
    """
    Bulk insert objects in batches.

    Args:
        session: The database session.
        objects: List of objects to insert.
        batch_size: Number of objects per batch.

    Returns:
        Total number of objects inserted.
    """
    total_inserted = 0

    for i in range(0, len(objects), batch_size):
        batch = objects[i : i + batch_size]
        session.add_all(batch)
        total_inserted += len(batch)
        logger.debug(
            f"Inserted batch {i // batch_size + 1}: "
            f"{len(batch)} objects"
        )

    return total_inserted


async def bulk_update(
    session: AsyncSession,
    objects: list[Any],
    batch_size: int = 1000,
) -> int:
    """
    Bulk update objects in batches.

    Args:
        session: The database session.
        objects: List of objects to update.
        batch_size: Number of objects per batch.

    Returns:
        Total number of objects updated.
    """
    total_updated = 0

    for i in range(0, len(objects), batch_size):
        batch = objects[i : i + batch_size]
        for obj in batch:
            session.add(obj)
        total_updated += len(batch)
        logger.debug(
            f"Updated batch {i // batch_size + 1}: "
            f"{len(batch)} objects"
        )

    return total_updated


async def fetch_all(
    session: AsyncSession,
    query: Any,
    params: dict[str, Any] | None = None,
) -> list[Any]:
    """
    Fetch all results from a query.

    Args:
        session: The database session.
        query: The query to execute.
        params: Optional query parameters.

    Returns:
        List of results.
    """
    result = await session.execute(query, params or {})
    return result.scalars().all()


async def fetch_one(
    session: AsyncSession,
    query: Any,
    params: dict[str, Any] | None = None,
) -> Any:
    """
    Fetch a single result from a query.

    Args:
        session: The database session.
        query: The query to execute.
        params: Optional query parameters.

    Returns:
        Single result or None.
    """
    result = await session.execute(query, params or {})
    return result.scalar_one_or_none()


async def count(
    session: AsyncSession,
    query: Any,
    params: dict[str, Any] | None = None,
) -> int:
    """
    Count results from a query.

    Args:
        session: The database session.
        query: The query to execute.
        params: Optional query parameters.

    Returns:
        Count of results.
    """
    result = await session.execute(query, params or {})
    return result.scalar_one()


# Loader utilities for eager loading relationships
def with_relationship(*relationships: Any) -> Callable[[Any], Any]:
    """
    Decorator to add eager loading of relationships to a query.

    Usage:
        @with_relationship(User.workspaces, Workspace.projects)
        async def get_user_with_workspaces(session, user_id):
            return await session.execute(
                select(User).where(User.id == user_id)
            )
    """
    def decorator(query: Any) -> Any:
        for rel in relationships:
            query = query.options(selectinload(rel))
        return query
    return decorator


async def get_or_create(
    session: AsyncSession,
    model: type[T],
    defaults: dict[str, Any] | None = None,
    **kwargs: Any,
) -> tuple[T, bool]:
    """
    Get an existing record or create a new one.

    Args:
        session: The database session.
        model: The model class.
        defaults: Default values for creation.
        **kwargs: Query parameters.

    Returns:
        Tuple of (instance, created).
    """
    query = select(model).filter_by(**kwargs)
    instance = await session.execute(query)
    result = instance.scalar_one_or_none()

    if result:
        return result, False

    instance = model(**{**(defaults or {}), **kwargs})
    session.add(instance)
    return instance, True


async def upsert(
    session: AsyncSession,
    model: type[T],
    index_elements: list[str],
    values: dict[str, Any],
) -> T:
    """
    Insert or update a record (upsert).

    Args:
        session: The database session.
        model: The model class.
        index_elements: Columns to use for conflict detection.
        values: Values to insert/update.

    Returns:
        The upserted instance.
    """
    # For PostgreSQL, use ON CONFLICT
    from sqlalchemy.dialects.postgresql import insert

    table = model.__table__
    stmt = insert(table).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_=values,
    )
    result = await session.execute(stmt)
    await session.commit()

    # Return the instance
    instance = await session.get(model, result.inserted_primary_key)
    return instance
