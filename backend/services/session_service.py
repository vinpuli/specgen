"""
Session and token blacklist service.

This module provides:
- Token blacklist for logout
- Session management
- Active session tracking
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import redis.asyncio as redis

from backend.cache.connection import (
    get_redis,
    init_redis,
    SESSION_PREFIX,
)
from backend.core.security import decode_token

logger = logging.getLogger(__name__)

# Token blacklist prefix
TOKEN_BLACKLIST_PREFIX = f"{SESSION_PREFIX}blacklist:"
# Active sessions prefix
ACTIVE_SESSIONS_PREFIX = f"{SESSION_PREFIX}active:"
# Refresh token to user mapping
REFRESH_TOKEN_PREFIX = f"{SESSION_PREFIX}refresh:"


class TokenBlacklistService:
    """
    Service for managing token blacklists and sessions.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize token blacklist service.

        Args:
            redis_client: Async Redis client.
        """
        self.redis = redis_client

    def _get_blacklist_key(self, token: str) -> str:
        """Get Redis key for token blacklist."""
        return f"{TOKEN_BLACKLIST_PREFIX}{token}"

    def _get_active_sessions_key(self, user_id: str) -> str:
        """Get Redis key for user's active sessions."""
        return f"{ACTIVE_SESSIONS_PREFIX}{user_id}"

    def _get_refresh_token_key(self, refresh_token: str) -> str:
        """Get Redis key for refresh token mapping."""
        return f"{REFRESH_TOKEN_PREFIX}{refresh_token}"

    async def add_to_blacklist(self, token: str, ttl: int = 86400) -> bool:
        """
        Add a token to the blacklist.

        Args:
            token: JWT token to blacklist.
            ttl: Time to live in seconds (default 24 hours).

        Returns:
            True if successful.
        """
        try:
            await self.redis.set(
                self._get_blacklist_key(token),
                "revoked",
                ex=ttl,
            )
            logger.info(f"Token added to blacklist")
            return True
        except Exception as e:
            logger.error(f"Failed to blacklist token: {str(e)}")
            return False

    async def is_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token: JWT token to check.

        Returns:
            True if token is blacklisted.
        """
        try:
            result = await self.redis.get(self._get_blacklist_key(token))
            return result == "revoked"
        except Exception as e:
            logger.error(f"Failed to check blacklist: {str(e)}")
            return False

    async def blacklist_all_user_tokens(self, user_id: str) -> int:
        """
        Blacklist all active tokens for a user.

        Args:
            user_id: User ID.

        Returns:
            Number of tokens blacklisted.
        """
        try:
            sessions_key = self._get_active_sessions_key(user_id)
            tokens = await self.redis.smembers(sessions_key)

            if not tokens:
                return 0

            # Calculate TTL based on oldest token
            ttl = 86400  # Default 24 hours

            # Add all tokens to blacklist
            pipeline = self.redis.pipeline()
            for token in tokens:
                pipeline.set(self._get_blacklist_key(token), "revoked", ex=ttl)
            await pipeline.execute()

            # Clear active sessions
            await self.redis.delete(sessions_key)

            logger.info(f"Blacklisted {len(tokens)} tokens for user {user_id}")
            return len(tokens)

        except Exception as e:
            logger.error(f"Failed to blacklist user tokens: {str(e)}")
            return 0

    async def add_active_session(
        self, user_id: str, access_token: str, refresh_token: str, ttl: int = 86400
    ) -> bool:
        """
        Add an active session for a user.

        Args:
            user_id: User ID.
            access_token: Access token.
            refresh_token: Refresh token.
            ttl: Session TTL in seconds.

        Returns:
            True if successful.
        """
        try:
            sessions_key = self._get_active_sessions_key(user_id)

            # Add access token to active sessions
            await self.redis.sadd(sessions_key, access_token)
            await self.redis.expire(sessions_key, ttl)

            # Map refresh token to user
            refresh_key = self._get_refresh_token_key(refresh_token)
            await self.redis.set(refresh_key, user_id, ex=ttl)

            return True

        except Exception as e:
            logger.error(f"Failed to add active session: {str(e)}")
            return False

    async def remove_active_session(
        self, user_id: str, access_token: str, refresh_token: str
    ) -> bool:
        """
        Remove an active session.

        Args:
            user_id: User ID.
            access_token: Access token.
            refresh_token: Refresh token.

        Returns:
            True if successful.
        """
        try:
            sessions_key = self._get_active_sessions_key(user_id)

            # Remove from active sessions
            await self.redis.srem(sessions_key, access_token)

            # Remove refresh token mapping
            refresh_key = self._get_refresh_token_key(refresh_token)
            await self.redis.delete(refresh_key)

            return True

        except Exception as e:
            logger.error(f"Failed to remove active session: {str(e)}")
            return False

    async def get_active_session_count(self, user_id: str) -> int:
        """
        Get count of active sessions for a user.

        Args:
            user_id: User ID.

        Returns:
            Number of active sessions.
        """
        try:
            return await self.redis.scard(self._get_active_sessions_key(user_id))
        except Exception as e:
            logger.error(f"Failed to get session count: {str(e)}")
            return 0

    async def get_active_sessions(self, user_id: str) -> List[str]:
        """
        Get all active session tokens for a user.

        Args:
            user_id: User ID.

        Returns:
            List of active tokens.
        """
        try:
            return list(await self.redis.smembers(self._get_active_sessions_key(user_id)))
        except Exception as e:
            logger.error(f"Failed to get active sessions: {str(e)}")
            return []

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token.

        Args:
            refresh_token: Refresh token to revoke.

        Returns:
            True if successful.
        """
        try:
            refresh_key = self._get_refresh_token_key(refresh_token)
            user_id = await self.redis.get(refresh_key)

            if user_id:
                # Blacklist all user tokens
                await self.blacklist_all_user_tokens(user_id)

            await self.redis.delete(refresh_key)
            return True

        except Exception as e:
            logger.error(f"Failed to revoke refresh token: {str(e)}")
            return False


async def get_token_blacklist_service() -> TokenBlacklistService:
    """
    Get token blacklist service instance.

    Returns:
        TokenBlacklistService instance.
    """
    redis_client = await get_redis()
    return TokenBlacklistService(redis_client)


async def init_session_service() -> None:
    """
    Initialize the session service.
    """
    await init_redis()
    logger.info("Session service initialized")
