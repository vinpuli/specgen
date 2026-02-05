"""
WebSocket API endpoints for real-time communication.

This module provides:
- WebSocket connection establishment with JWT authentication
- Room subscription management
- Event broadcasting for real-time updates
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.websocket_manager import manager, authenticate_websocket
from backend.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/connect")
async def websocket_connect(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
    project_id: Optional[str] = Query(None, description="Project ID to subscribe to"),
    workspace_id: Optional[str] = Query(None, description="Workspace ID to subscribe to"),
):
    """
    WebSocket connection endpoint with JWT authentication.

    Connect to receive real-time updates for projects and workspaces.
    """
    # Get async session
    async for session in get_db_session():
        try:
            # Authenticate the connection
            user_info = await authenticate_websocket(websocket, token, session)
            user_id = user_info["user_id"]

            # Accept the connection
            websocket_id = await manager.connect(
                websocket=websocket,
                user_id=user_id,
                project_id=project_id,
                workspace_id=workspace_id,
            )

            logger.info(
                f"WebSocket connected: {websocket_id} "
                f"(user: {user_id}, project: {project_id})"
            )

            # Send connection confirmation
            await manager.send_personal_message(
                {
                    "type": "connection_established",
                    "data": {
                        "websocket_id": websocket_id,
                        "user_id": user_id,
                        "project_id": project_id,
                        "workspace_id": workspace_id,
                        "connected_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
                websocket_id,
            )

            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_json()

                    # Handle different message types
                    message_type = data.get("type", "unknown")

                    if message_type == "heartbeat":
                        # Update heartbeat timestamp
                        await manager.update_heartbeat(websocket_id)
                        await manager.send_personal_message(
                            {"type": "heartbeat_ack", "timestamp": datetime.now(timezone.utc).isoformat()},
                            websocket_id,
                        )

                    elif message_type == "subscribe":
                        # Subscribe to a room
                        room_id = data.get("room_id")
                        if room_id:
                            await manager.join_room(websocket_id, room_id)
                            await manager.send_personal_message(
                                {"type": "subscribed", "room_id": room_id},
                                websocket_id,
                            )

                    elif message_type == "unsubscribe":
                        # Unsubscribe from a room
                        room_id = data.get("room_id")
                        if room_id:
                            await manager.leave_room(websocket_id, room_id)
                            await manager.send_personal_message(
                                {"type": "unsubscribed", "room_id": room_id},
                                websocket_id,
                            )

                    elif message_type == "ping":
                        # Simple ping-pong for connection health
                        await manager.send_personal_message(
                            {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()},
                            websocket_id,
                        )

                    else:
                        # Echo unknown message types
                        await manager.send_personal_message(
                            {"type": "echo", "original": data},
                            websocket_id,
                        )

                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected: {websocket_id}")
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    break

        except HTTPException as e:
            logger.warning(f"WebSocket authentication failed: {e.detail}")
            await websocket.close(code=4001, reason=e.detail)
            return
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await websocket.close(code=4000, reason="Internal error")
            return
        finally:
            # Clean up connection
            try:
                await manager.disconnect(websocket_id, user_id)
            except (NameError, KeyError):
                pass  # Connection might not have been established


@router.websocket("/ws/project/{project_id}")
async def websocket_project_channel(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(..., description="JWT authentication token"),
):
    """
    WebSocket connection for a specific project channel.

    Automatically subscribes to the project room.
    """
    # Get async session
    async for session in get_db_session():
        try:
            # Authenticate the connection
            user_info = await authenticate_websocket(websocket, token, session)
            user_id = user_info["user_id"]

            # Accept the connection
            websocket_id = await manager.connect(
                websocket=websocket,
                user_id=user_id,
                project_id=project_id,
            )

            logger.info(
                f"WebSocket project channel connected: {websocket_id} "
                f"(user: {user_id}, project: {project_id})"
            )

            # Send connection confirmation
            await manager.send_personal_message(
                {
                    "type": "project_connected",
                    "data": {
                        "websocket_id": websocket_id,
                        "project_id": project_id,
                        "connected_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
                websocket_id,
            )

            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_json()
                    message_type = data.get("type", "unknown")

                    if message_type == "heartbeat":
                        await manager.update_heartbeat(websocket_id)
                        await manager.send_personal_message(
                            {"type": "heartbeat_ack"},
                            websocket_id,
                        )

                except WebSocketDisconnect:
                    logger.info(f"WebSocket project channel disconnected: {websocket_id}")
                    break
                except Exception as e:
                    logger.error(f"Error in project channel: {e}")
                    break

        except HTTPException as e:
            logger.warning(f"WebSocket project authentication failed: {e.detail}")
            await websocket.close(code=4001, reason=e.detail)
            return
        except Exception as e:
            logger.error(f"WebSocket project connection error: {e}")
            await websocket.close(code=4000, reason="Internal error")
            return
        finally:
            try:
                await manager.disconnect(websocket_id, user_id)
            except (NameError, KeyError):
                pass


# ======================
# Event Broadcasting Helpers
# ======================


async def broadcast_question_ready(project_id: str, question_data: dict):
    """
    Broadcast question_ready event to project room.

    Args:
        project_id: Project ID.
        question_data: Question information.
    """
    await manager.broadcast_to_room(
        f"project:{project_id}",
        {
            "type": "question_ready",
            "data": {
                **question_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def broadcast_answer_submitted(project_id: str, answer_data: dict):
    """
    Broadcast answer_submitted event to project room.

    Args:
        project_id: Project ID.
        answer_data: Answer information.
    """
    await manager.broadcast_to_room(
        f"project:{project_id}",
        {
            "type": "answer_submitted",
            "data": {
                **answer_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def broadcast_artifact_progress(project_id: str, progress_data: dict):
    """
    Broadcast artifact_progress event to project room.

    Args:
        project_id: Project ID.
        progress_data: Progress information.
    """
    await manager.broadcast_to_room(
        f"project:{project_id}",
        {
            "type": "artifact_progress",
            "data": {
                **progress_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def broadcast_artifact_complete(project_id: str, artifact_data: dict):
    """
    Broadcast artifact_complete event to project room.

    Args:
        project_id: Project ID.
        artifact_data: Artifact information.
    """
    await manager.broadcast_to_room(
        f"project:{project_id}",
        {
            "type": "artifact_complete",
            "data": {
                **artifact_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def broadcast_comment_added(project_id: str, comment_data: dict):
    """
    Broadcast comment_added event to project room.

    Args:
        project_id: Project ID.
        comment_data: Comment information.
    """
    await manager.broadcast_to_room(
        f"project:{project_id}",
        {
            "type": "comment_added",
            "data": {
                **comment_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def broadcast_conversation_update(project_id: str, conversation_data: dict):
    """
    Broadcast conversation_update event to project room.

    Args:
        project_id: Project ID.
        conversation_data: Conversation update information.
    """
    await manager.broadcast_to_room(
        f"project:{project_id}",
        {
            "type": "conversation_update",
            "data": {
                **conversation_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def broadcast_contradiction_detected(project_id: str, contradiction_data: dict):
    """
    Broadcast contradiction_detected event to project room.

    Args:
        project_id: Project ID.
        contradiction_data: Contradiction information.
    """
    await manager.broadcast_to_room(
        f"project:{project_id}",
        {
            "type": "contradiction_detected",
            "data": {
                **contradiction_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
