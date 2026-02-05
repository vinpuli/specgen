"""
Base repository class providing common data access operations.

This module provides a generic base class for all repositories,
implementing common CRUD operations and query utilities.
"""

import uuid
from typing import Any, Generic, TypeVar, Optional, List, Type

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from backend.db.base import Base


T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Base repository class providing common data access operations.

    Attributes:
        model: The SQLAlchemy model class this repository manages.
        session: The async database session.
    """

    def __init__(self, model: Type[T], session: AsyncSession):
        """
        Initialize the repository with a model class and session.

        Args:
            model: The SQLAlchemy model class.
            session: The async database session.
        """
        self.model = model
        self.session = session

    async def get_by_id(self, id: uuid.UUID) -> Optional[T]:
        """
        Get a record by its primary key ID.

        Args:
            id: The UUID of the record.

        Returns:
            The record if found, None otherwise.
        """
        return await self.session.get(self.model, id)

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> List[T]:
        """
        Get all records with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.
            order_by: Field name to order by.
            descending: Whether to order in descending order.

        Returns:
            List of records.
        """
        query = select(self.model).offset(skip).limit(limit)

        if order_by:
            column = getattr(self.model, order_by, None)
            if column:
                if descending:
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        """
        Count all records in the table.

        Returns:
            Total count of records.
        """
        query = select(func.count()).select_from(self.model)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> T:
        """
        Create a new record.

        Args:
            **kwargs: Model field values.

        Returns:
            The created record.
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: uuid.UUID, **kwargs: Any) -> Optional[T]:
        """
        Update a record by ID.

        Args:
            id: The UUID of the record to update.
            **kwargs: Fields to update.

        Returns:
            The updated record if found.
        """
        # Remove None values
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        query = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete(self, id: uuid.UUID) -> bool:
        """
        Delete a record by ID.

        Args:
            id: The UUID of the record to delete.

        Returns:
            True if deleted, False if not found.
        """
        query = (
            delete(self.model)
            .where(self.model.id == id)
            .returning(self.model.id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def exists(self, id: uuid.UUID) -> bool:
        """
        Check if a record exists by ID.

        Args:
            id: The UUID of the record.

        Returns:
            True if exists, False otherwise.
        """
        query = (
            select(self.model.id)
            .where(self.model.id == id)
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    def _build_query(self, **kwargs: Select) -> Select:
        """
        Build a query from filter parameters.

        Args:
            **kwargs: Filter parameters matching model fields.

        Returns:
            The built query.
        """
        query = select(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        return query

    async def find_one(self, **kwargs: Any) -> Optional[T]:
        """
        Find a single record by filter parameters.

        Args:
            **kwargs: Filter parameters.

        Returns:
            The record if found, None otherwise.
        """
        query = self._build_query(**kwargs)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_all(self, **kwargs: Any) -> List[T]:
        """
        Find all records matching filter parameters.

        Args:
            **kwargs: Filter parameters.

        Returns:
            List of matching records.
        """
        query = self._build_query(**kwargs)
        result = await self.session.execute(query)
        return list(result.scalars().all())
