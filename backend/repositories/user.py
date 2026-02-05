"""
User repository for user data access operations.

This module implements the repository pattern for User model,
providing data access methods for authentication and user management.
"""

import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.user import User
from backend.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    Repository for User data access operations.

    Provides methods for:
    - User authentication (by email)
    - OAuth provider lookup
    - User search and filtering
    - Account management operations
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the UserRepository.

        Args:
            session: The async database session.
        """
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by their email address.

        Args:
            email: The user's email address.

        Returns:
            The user if found, None otherwise.
        """
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email_with_password(self, email: str) -> Optional[User]:
        """
        Get a user by email with password hash (for authentication).

        Args:
            email: The user's email address.

        Returns:
            The user if found, None otherwise.
        """
        query = select(User).where(
            and_(User.email == email, User.password_hash.isnot(None))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_oauth_provider(
        self, provider: str, provider_id: str
    ) -> Optional[User]:
        """
        Get a user by OAuth provider and provider-specific ID.

        Note: This method checks if the provider is in the oauth_providers array.
        For full OAuth support, additional tracking may be needed.

        Args:
            provider: The OAuth provider name (e.g., 'google', 'github').
            provider_id: The provider's user ID.

        Returns:
            The user if found, None otherwise.
        """
        query = select(User).where(User.oauth_providers.contains([provider]))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_users(
        self, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """
        Get all active users with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of active users.
        """
        query = (
            select(User)
            .where(User.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_unverified_users(self, older_than: datetime) -> List[User]:
        """
        Get users who haven't verified their email.

        Args:
            older_than: Find users created before this time.

        Returns:
            List of unverified users.
        """
        query = select(User).where(
            and_(
                User.is_verified == False,
                User.created_at < older_than,
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_users_with_workspaces(
        self, user_id: uuid.UUID
    ) -> Optional[User]:
        """
        Get a user with their workspace memberships loaded.

        Args:
            user_id: The user's ID.

        Returns:
            The user with workspaces loaded.
        """
        query = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.workspace_members))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def search_by_name(
        self, name_query: str, limit: int = 50
    ) -> List[User]:
        """
        Search users by name (case-insensitive partial match).

        Args:
            name_query: The search query for full_name.
            limit: Maximum number of results.

        Returns:
            List of matching users.
        """
        query = (
            select(User)
            .where(
                User.full_name.ilike(f"%{name_query}%"),
                User.is_active == True,
            )
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def deactivate(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Deactivate a user account.

        Args:
            user_id: The user's ID.

        Returns:
            The deactivated user if found.
        """
        return await self.update(user_id, is_active=False)

    async def activate(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Activate a user account.

        Args:
            user_id: The user's ID.

        Returns:
            The activated user if found.
        """
        return await self.update(user_id, is_active=True)

    async def verify_email(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Mark a user's email as verified.

        Args:
            user_id: The user's ID.

        Returns:
            The updated user if found.
        """
        return await self.update(user_id, is_verified=True)

    async def update_last_login(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Update the user's last login timestamp.

        Args:
            user_id: The user's ID.

        Returns:
            The updated user if found.
        """
        return await self.update(
            user_id, last_login_at=datetime.now(timezone.utc)
        )

    async def enable_2fa(
        self, user_id: uuid.UUID, secret: str
    ) -> Optional[User]:
        """
        Enable two-factor authentication for a user.

        Args:
            user_id: The user's ID.
            secret: The TOTP secret.

        Returns:
            The updated user if found.
        """
        return await self.update(
            user_id,
            two_factor_enabled=True,
            two_factor_secret=secret,
        )

    async def disable_2fa(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Disable two-factor authentication for a user.

        Args:
            user_id: The user's ID.

        Returns:
            The updated user if found.
        """
        return await self.update(
            user_id,
            two_factor_enabled=False,
            two_factor_secret=None,
        )

    async def add_oauth_provider(
        self, user_id: uuid.UUID, provider: str
    ) -> Optional[User]:
        """
        Add an OAuth provider to a user's account.

        Args:
            user_id: The user's ID.
            provider: The OAuth provider name.

        Returns:
            The updated user if found.
        """
        user = await self.get_by_id(user_id)
        if user:
            providers = set(user.oauth_providers or [])
            providers.add(provider)
            return await self.update(
                user_id, oauth_providers=list(providers)
            )
        return None

    async def remove_oauth_provider(
        self, user_id: uuid.UUID, provider: str
    ) -> Optional[User]:
        """
        Remove an OAuth provider from a user's account.

        Args:
            user_id: The user's ID.
            provider: The OAuth provider name.

        Returns:
            The updated user if found.
        """
        user = await self.get_by_id(user_id)
        if user:
            providers = set(user.oauth_providers or [])
            providers.discard(provider)
            return await self.update(
                user_id, oauth_providers=list(providers)
            )
        return None


# Import for timezone-aware datetime
from datetime import timezone  # noqa: E402
