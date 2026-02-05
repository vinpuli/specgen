"""
WebSocket connection manager for real-time communication.

This module provides:
- WebSocket connection management
- Room-based subscription management
- Heartbeat mechanism for connection health
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import decode_token

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and room subscriptions.
    """

    def __init__(self):
        """Initialize connection manager."""
        # Active connections: websocket_id -> connection_info
        self.active_connections: Dict[str, dict] = {}
        # Room subscriptions: room_id -> set of websocket_ids
        self.rooms: Dict[str, Set[str]] = {}
        # User connections: user_id -> set of websocket_ids
        self.user_connections: Dict[str, Set[str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        project_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> str:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection.
            user_id: User ID from JWT token.
            project_id: Optional project ID to subscribe to.
            workspace_id: Optional workspace ID.

        Returns:
            websocket_id: Unique identifier for this connection.
        """
        await websocket.accept()

        # Generate unique websocket ID
        from uuid import uuid4
        websocket_id = str(uuid4())

        # Store connection info
        self.active_connections[websocket_id] = {
            "websocket": websocket,
            "user_id": user_id,
            "project_id": project_id,
            "workspace_id": workspace_id,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        }

        # Track user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket_id)

        # Subscribe to project room if provided
        if project_id:
            await self.join_room(websocket_id, f"project:{project_id}")

        # Subscribe to workspace room if provided
        if workspace_id:
            await self.join_room(websocket_id, f"workspace:{workspace_id}")

        logger.info(f"WebSocket connected: {websocket_id} for user {user_id}")

        return websocket_id

    async def disconnect(self, websocket_id: str, user_id: str):
        """
        Disconnect a WebSocket connection.

        Args:
            websocket_id: Unique connection identifier.
            user_id: User ID.
        """
        if websocket_id not in self.active_connections:
            return

        # Get connection info before removing
        connection_info = self.active_connections[websocket_id]
        project_id = connection_info.get("project_id")
        workspace_id = connection_info.get("workspace_id")

        # Remove from active connections
        del self.active_connections[websocket_id]

        # Remove from user connections
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Remove from rooms
        for room_id in list(self.rooms.keys()):
            self.rooms[room_id].discard(websocket_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

        logger.info(f"WebSocket disconnected: {websocket_id} for user {user_id}")

    async def join_room(self, websocket_id: str, room_id: str):
        """
        Add a connection to a room.

        Args:
            websocket_id: Connection identifier.
            room_id: Room identifier.
        """
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket_id)
        logger.debug(f"WebSocket {websocket_id} joined room {room_id}")

    async def leave_room(self, websocket_id: str, room_id: str):
        """
        Remove a connection from a room.

        Args:
            websocket_id: Connection identifier.
            room_id: Room identifier.
        """
        if room_id in self.rooms:
            self.rooms[room_id].discard(websocket_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        logger.debug(f"WebSocket {websocket_id} left room {room_id}")

    async def send_personal_message(self, message: dict, websocket_id: str):
        """
        Send a message to a specific connection.

        Args:
            message: Message to send.
            websocket_id: Connection identifier.
        """
        if websocket_id not in self.active_connections:
            return

        websocket = self.active_connections[websocket_id]["websocket"]
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to {websocket_id}: {e}")

    async def broadcast_to_room(self, room_id: str, message: dict, exclude: Optional[Set[str]] = None):
        """
        Broadcast a message to all connections in a room.

        Args:
            room_id: Room identifier.
            message: Message to broadcast.
            exclude: Optional set of websocket_ids to exclude.
        """
        if room_id not in self.rooms:
            return

        exclude = exclude or set()
        for websocket_id in self.rooms[room_id]:
            if websocket_id not in exclude:
                await self.send_personal_message(message, websocket_id)

    async def broadcast_to_user(self, user_id: str, message: dict):
        """
        Broadcast a message to all connections of a user.

        Args:
            user_id: User ID.
            message: Message to send.
        """
        if user_id not in self.user_connections:
            return

        for websocket_id in self.user_connections[user_id]:
            await self.send_personal_message(message, websocket_id)

    async def update_heartbeat(self, websocket_id: str):
        """
        Update the last heartbeat timestamp for a connection.

        Args:
            websocket_id: Connection identifier.
        """
        if websocket_id in self.active_connections:
            self.active_connections[websocket_id]["last_heartbeat"] = datetime.now(
                timezone.utc
            ).isoformat()

    def get_connection_info(self, websocket_id: str) -> Optional[dict]:
        """
        Get connection information.

        Args:
            websocket_id: Connection identifier.

        Returns:
            Connection info dict or None.
        """
        return self.active_connections.get(websocket_id)

    def get_user_connections(self, user_id: str) -> Set[str]:
        """
        Get all connection IDs for a user.

        Args:
            user_id: User ID.

        Returns:
            Set of websocket_ids.
        """
        return self.user_connections.get(user_id, set())

    def get_room_connections(self, room_id: str) -> Set[str]:
        """
        Get all connection IDs in a room.

        Args:
            room_id: Room identifier.

        Returns:
            Set of websocket_ids.
        """
        return self.rooms.get(room_id, set())

    async def get_active_users_in_project(self, project_id: str) -> Set[str]:
        """
        Get all active user IDs in a project room.

        Args:
            project_id: Project ID.

        Returns:
            Set of user IDs.
        """
        room_id = f"project:{project_id}"
        if room_id not in self.rooms:
            return set()

        user_ids = set()
        for websocket_id in self.rooms[room_id]:
            if websocket_id in self.active_connections:
                user_id = self.active_connections[websocket_id].get("user_id")
                if user_id:
                    user_ids.add(user_id)

        return user_ids


# Global connection manager
manager = ConnectionManager()


async def authenticate_websocket(
    websocket: WebSocket,
    token: str,
    session: AsyncSession,
) -> dict:
    """
    Authenticate a WebSocket connection using JWT token.

    Args:
        websocket: WebSocket connection.
        token: JWT token from query parameter.
        session: Database session.

    Returns:
        dict: User information from token.

    Raises:
        HTTPException: If authentication fails.
    """
    try:
        # Decode JWT token
        payload = decode_token(token)
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: user_id not found")

        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role"),
        }

    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
