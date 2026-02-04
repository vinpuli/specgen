"""
Redis-based session management.

Provides secure session storage with:
- Secure session token generation
- Session data serialization
- Automatic session expiration
- Session refresh on activity
"""

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis

from backend.cache.connection import (
    init_redis,
    get_redis,
    SESSION_PREFIX,
    SESSION_TTL,
)


class RedisSessionStore:
    """
    Redis-based session storage.

    Session Structure:
        {SESSION_PREFIX}{session_id}: {
            "user_id": "uuid",
            "data": {...},
            "created_at": "isoformat",
            "updated_at": "isoformat",
            "expires_at": "isoformat",
            "ip_address": "...",
            "user_agent": "..."
        }
    """

    def __init__(self, redis_client: redis.Redis = None):
        """
        Initialize session store.

        Args:
            redis_client: Optional Redis client (will be initialized if not provided)
        """
        self.redis = redis_client
        self.prefix = SESSION_PREFIX
        self.ttl = SESSION_TTL

    async def get_client(self) -> redis.Redis:
        """Get Redis client."""
        if self.redis is None:
            self.redis = await init_redis()
        return self.redis

    def _session_key(self, session_id: str) -> str:
        """Generate session key."""
        return f"{self.prefix}{session_id}"

    async def create_session(
        self,
        user_id: uuid.UUID,
        data: Dict[str, Any] = None,
        ip_address: str = None,
        user_agent: str = None,
        expires_delta: timedelta = None,
    ) -> str:
        """
        Create a new session.

        Args:
            user_id: User ID
            data: Session data
            ip_address: Client IP address
            user_agent: Client user agent
            expires_delta: Session expiration time

        Returns:
            Session ID (token)
        """
        client = await self.get_client()

        # Generate secure session ID
        session_id = secrets.token_urlsafe(32)

        now = datetime.utcnow()
        expires_delta = expires_delta or timedelta(seconds=self.ttl)
        expires_at = now + expires_delta

        session_data = {
            "user_id": str(user_id),
            "data": data or {},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        key = self._session_key(session_id)

        # Store session with expiration
        await client.setex(
            key,
            int(expires_delta.total_seconds()),
            json.dumps(session_data),
        )

        return session_id

    async def get_session(
        self,
        session_id: str,
        refresh: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Get session data.

        Args:
            session_id: Session ID
            refresh: Whether to refresh session expiration

        Returns:
            Session data or None if not found/expired
        """
        client = await self.get_client()
        key = self._session_key(session_id)

        data = await client.get(key)

        if data is None:
            return None

        session_data = json.loads(data)

        if refresh:
            # Refresh session expiration
            await client.expire(key, self.ttl)
            session_data["updated_at"] = datetime.utcnow().isoformat()

        return session_data

    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
    ) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID
            data: New session data

        Returns:
            True if updated, False if session not found
        """
        client = await self.get_client()
        key = self._session_key(session_id)

        # Get existing session
        existing = await self.get_session(session_id, refresh=False)

        if existing is None:
            return False

        # Update data
        existing["data"] = {**existing.get("data", {}), **data}
        existing["updated_at"] = datetime.utcnow().isoformat()

        # Get remaining TTL
        ttl = await client.ttl(key)

        # Store updated session
        await client.setex(key, ttl, json.dumps(existing))

        return True

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        client = await self.get_client()
        key = self._session_key(session_id)

        result = await client.delete(key)
        return result > 0

    async def validate_session(
        self,
        session_id: str,
        user_id: uuid.UUID = None,
    ) -> bool:
        """
        Validate session.

        Args:
            session_id: Session ID
            user_id: Optional user ID to validate against

        Returns:
            True if valid, False otherwise
        """
        session_data = await self.get_session(session_id)

        if session_data is None:
            return False

        if user_id is not None:
            return session_data.get("user_id") == str(user_id)

        return True

    async def get_user_sessions(
        self,
        user_id: uuid.UUID,
        pattern: str = "*",
    ) -> list:
        """
        Get all sessions for a user.

        Args:
            user_id: User ID
            pattern: Key pattern to search

        Returns:
            List of session IDs
        """
        client = await self.get_client()

        # Find all user sessions
        user_pattern = f"{self.prefix}{user_id}:*"
        keys = await client.keys(user_pattern)

        sessions = []
        for key in keys:
            session_id = key.replace(self.prefix, "")
            session = await self.get_session(session_id)
            if session is not None:
                sessions.append({
                    "session_id": session_id,
                    "created_at": session.get("created_at"),
                    "updated_at": session.get("updated_at"),
                    "ip_address": session.get("ip_address"),
                    "user_agent": session.get("user_agent"),
                })

        return sessions

    async def delete_user_sessions(
        self,
        user_id: uuid.UUID,
        except_session_id: str = None,
    ) -> int:
        """
        Delete all sessions for a user.

        Args:
            user_id: User ID
            except_session_id: Session ID to preserve

        Returns:
            Number of sessions deleted
        """
        client = await self.get_client()

        user_pattern = f"{self.prefix}{user_id}:*"
        keys = await client.keys(user_pattern)

        deleted = 0
        for key in keys:
            session_id = key.replace(self.prefix, "")
            if except_session_id and session_id == except_session_id:
                continue
            if await client.delete(key):
                deleted += 1

        return deleted


# Session store instance
_session_store: Optional[RedisSessionStore] = None


def get_session_store() -> RedisSessionStore:
    """Get session store instance."""
    global _session_store

    if _session_store is None:
        _session_store = RedisSessionStore()

    return _session_store
