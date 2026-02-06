"""
WebSocket integration for human-in-the-loop interrupt notifications.

This module provides:
1. WebSocket connection management for interrupt notifications
2. Interrupt subscription handling
3. Real-time interrupt status updates
4. Response handling via WebSocket
"""

from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
import asyncio
import json

from .human_in_the_loop import (
    HumanInterruptConfig,
    InterruptResponse,
    InterruptStatus,
    InterruptType,
)


class WebSocketState(str, Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


class InterruptNotification(BaseModel):
    """Notification about an interrupt."""
    notification_id: str = Field(default_factory=lambda: str(uuid4()))
    interrupt_id: str
    interrupt_type: InterruptType
    title: str
    description: str
    priority: str
    options: List[str] = Field(default_factory=list)
    thread_id: str
    project_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InterruptUpdate(BaseModel):
    """Update about an interrupt status change."""
    interrupt_id: str
    status: InterruptStatus
    responded_at: Optional[datetime] = None
    responded_by: Optional[str] = None
    response: Optional[str] = None
    comment: Optional[str] = None


class WebSocketInterruptManager:
    """
    Manages WebSocket connections for interrupt notifications.
    
    Provides:
    1. Connection lifecycle management
    2. Interrupt subscription by thread/project
    3. Real-time notification broadcasting
    4. Response handling via WebSocket
    """
    
    def __init__(self):
        """Initialize the WebSocket interrupt manager."""
        self._connections: Dict[str, Set[str]] = {}  # connection_id -> set of subscribed thread_ids
        self._thread_subscribers: Dict[str, Set[str]] = {}  # thread_id -> set of connection_ids
        self._project_subscribers: Dict[str, Set[str]] = {}  # project_id -> set of connection_ids
        self._interrupt_handlers: Dict[str, Callable] = {}
        self._notification_handlers: List[Callable] = []
        self._connection_handlers: Dict[str, List[Callable]] = {
            "connect": [],
            "disconnect": [],
        }
    
    def register_connection(
        self,
        connection_id: str,
        thread_ids: Optional[List[str]] = None,
        project_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Register a new WebSocket connection.
        
        Args:
            connection_id: Unique identifier for the connection
            thread_ids: List of thread IDs to subscribe to
            project_ids: List of project IDs to subscribe to
        """
        self._connections[connection_id] = set(thread_ids or [])
        
        # Subscribe to threads
        for thread_id in thread_ids or []:
            if thread_id not in self._thread_subscribers:
                self._thread_subscribers[thread_id] = set()
            self._thread_subscribers[thread_id].add(connection_id)
        
        # Subscribe to projects
        for project_id in project_ids or []:
            if project_id not in self._project_subscribers:
                self._project_subscribers[project_id] = set()
            self._project_subscribers[project_id].add(connection_id)
        
        # Trigger connect handlers
        for handler in self._connection_handlers.get("connect", []):
            try:
                handler(connection_id)
            except Exception:
                pass
    
    def unregister_connection(self, connection_id: str) -> None:
        """
        Unregister a WebSocket connection.
        
        Args:
            connection_id: Unique identifier for the connection
        """
        if connection_id not in self._connections:
            return
        
        # Remove from thread subscribers
        for thread_id in self._connections[connection_id]:
            if thread_id in self._thread_subscribers:
                self._thread_subscribers[thread_id].discard(connection_id)
                if not self._thread_subscribers[thread_id]:
                    del self._thread_subscribers[thread_id]
        
        # Remove from project subscribers
        for project_id in self._connections[connection_id]:
            if project_id in self._project_subscribers:
                self._project_subscribers[project_id].discard(connection_id)
                if not self._project_subscribers[project_id]:
                    del self._project_subscribers[project_id]
        
        # Remove connection
        del self._connections[connection_id]
        
        # Trigger disconnect handlers
        for handler in self._connection_handlers.get("disconnect", []):
            try:
                handler(connection_id)
            except Exception:
                pass
    
    def subscribe_to_thread(self, connection_id: str, thread_id: str) -> None:
        """Subscribe a connection to a thread."""
        if connection_id not in self._connections:
            self._connections[connection_id] = set()
        
        self._connections[connection_id].add(thread_id)
        
        if thread_id not in self._thread_subscribers:
            self._thread_subscribers[thread_id] = set()
        self._thread_subscribers[thread_id].add(connection_id)
    
    def unsubscribe_from_thread(self, connection_id: str, thread_id: str) -> None:
        """Unsubscribe a connection from a thread."""
        if connection_id in self._connections:
            self._connections[connection_id].discard(thread_id)
        
        if thread_id in self._thread_subscribers:
            self._thread_subscribers[thread_id].discard(connection_id)
            if not self._thread_subscribers[thread_id]:
                del self._thread_subscribers[thread_id]
    
    def subscribe_to_project(self, connection_id: str, project_id: str) -> None:
        """Subscribe a connection to a project."""
        if connection_id not in self._connections:
            self._connections[connection_id] = set()
        
        self._connections[connection_id].add(project_id)
        
        if project_id not in self._project_subscribers:
            self._project_subscribers[project_id] = set()
        self._project_subscribers[project_id].add(connection_id)
    
    def unsubscribe_from_project(self, connection_id: str, project_id: str) -> None:
        """Unsubscribe a connection from a project."""
        if connection_id in self._connections:
            self._connections[connection_id].discard(project_id)
        
        if project_id in self._project_subscribers:
            self._project_subscribers[project_id].discard(connection_id)
            if not self._project_subscribers[project_id]:
                del self._project_subscribers[project_id]
    
    def get_thread_subscribers(self, thread_id: str) -> Set[str]:
        """Get all connections subscribed to a thread."""
        return self._thread_subscribers.get(thread_id, set()).copy()
    
    def get_project_subscribers(self, project_id: str) -> Set[str]:
        """Get all connections subscribed to a project."""
        return self._project_subscribers.get(project_id, set()).copy()
    
    def broadcast_interrupt(
        self,
        notification: InterruptNotification,
        send_func: Callable[[str, Dict[str, Any]], None],
    ) -> int:
        """
        Broadcast an interrupt notification to subscribed connections.
        
        Args:
            notification: The interrupt notification to broadcast
            send_func: Function to send message to a connection (connection_id, message)
        
        Returns:
            Number of connections notified
        """
        message = {
            "type": "interrupt",
            "notification": notification.model_dump(mode="json"),
        }
        
        count = 0
        subscribers = self.get_thread_subscribers(notification.thread_id)
        
        for connection_id in subscribers:
            try:
                send_func(connection_id, message)
                count += 1
            except Exception:
                pass
        
        return count
    
    def broadcast_interrupt_update(
        self,
        update: InterruptUpdate,
        thread_id: str,
        send_func: Callable[[str, Dict[str, Any]], None],
    ) -> int:
        """
        Broadcast an interrupt status update.
        
        Args:
            update: The interrupt update to broadcast
            thread_id: Thread ID for routing
            send_func: Function to send message to a connection
        
        Returns:
            Number of connections notified
        """
        message = {
            "type": "interrupt_update",
            "update": update.model_dump(mode="json"),
        }
        
        count = 0
        subscribers = self.get_thread_subscribers(thread_id)
        
        for connection_id in subscribers:
            try:
                send_func(connection_id, message)
                count += 1
            except Exception:
                pass
        
        return count
    
    def broadcast_interrupt_response(
        self,
        response: InterruptResponse,
        thread_id: str,
        send_func: Callable[[str, Dict[str, Any]], None],
    ) -> int:
        """
        Broadcast an interrupt response.
        
        Args:
            response: The interrupt response to broadcast
            thread_id: Thread ID for routing
            send_func: Function to send message to a connection
        
        Returns:
            Number of connections notified
        """
        message = {
            "type": "interrupt_response",
            "response": {
                "response_id": response.response_id,
                "interrupt_id": response.interrupt_id,
                "status": response.status.value,
                "response": response.response,
                "comment": response.comment,
                "responded_at": response.responded_at.isoformat() if response.responded_at else None,
                "responded_by": response.user_id,
            },
        }
        
        count = 0
        subscribers = self.get_thread_subscribers(thread_id)
        
        for connection_id in subscribers:
            try:
                send_func(connection_id, message)
                count += 1
            except Exception:
                pass
        
        return count
    
    def register_interrupt_handler(
        self,
        interrupt_id: str,
        handler: Callable[[InterruptResponse], None],
    ) -> None:
        """Register a handler for a specific interrupt."""
        self._interrupt_handlers[interrupt_id] = handler
    
    def unregister_interrupt_handler(self, interrupt_id: str) -> None:
        """Unregister a handler for an interrupt."""
        self._interrupt_handlers.pop(interrupt_id, None)
    
    def handle_interrupt_response(
        self,
        response: InterruptResponse,
    ) -> None:
        """
        Handle an interrupt response by calling registered handlers.
        
        Args:
            response: The interrupt response to handle
        """
        handler = self._interrupt_handlers.get(response.interrupt_id)
        if handler:
            try:
                handler(response)
            except Exception:
                pass
    
    def register_notification_handler(
        self,
        handler: Callable[[InterruptNotification], None],
    ) -> None:
        """Register a handler for all interrupt notifications."""
        self._notification_handlers.append(handler)
    
    def register_connection_handler(
        self,
        event: str,
        handler: Callable[[str], None],
    ) -> None:
        """Register a handler for connection events."""
        if event not in self._connection_handlers:
            self._connection_handlers[event] = []
        self._connection_handlers[event].append(handler)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)
    
    def get_thread_subscriber_count(self, thread_id: str) -> int:
        """Get the number of subscribers for a thread."""
        return len(self._thread_subscribers.get(thread_id, set()))
    
    def get_all_thread_ids(self) -> List[str]:
        """Get all subscribed thread IDs."""
        return list(self._thread_subscribers.keys())
    
    def get_all_project_ids(self) -> List[str]:
        """Get all subscribed project IDs."""
        return list(self._project_subscribers.keys())


class InterruptWebSocketHandler:
    """
    WebSocket handler for interrupt communication.
    
    Provides:
    1. Message parsing and validation
    2. Response submission handling
    3. Connection state management
    """
    
    def __init__(self, manager: Optional[WebSocketInterruptManager] = None):
        """
        Initialize the WebSocket handler.
        
        Args:
            manager: Optional WebSocket interrupt manager to use
        """
        self.manager = manager or WebSocketInterruptManager()
    
    async def handle_connect(
        self,
        connection_id: str,
        thread_ids: Optional[List[str]] = None,
        project_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Handle a new WebSocket connection.
        
        Args:
            connection_id: Unique identifier for the connection
            thread_ids: Thread IDs to subscribe to
            project_ids: Project IDs to subscribe to
        
        Returns:
            Welcome message with connection details
        """
        self.manager.register_connection(connection_id, thread_ids, project_ids)
        
        return {
            "type": "welcome",
            "connection_id": connection_id,
            "subscribed_threads": thread_ids or [],
            "subscribed_projects": project_ids or [],
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def handle_disconnect(self, connection_id: str) -> None:
        """Handle WebSocket disconnection."""
        self.manager.unregister_connection(connection_id)
    
    async def handle_subscribe(
        self,
        connection_id: str,
        thread_ids: Optional[List[str]] = None,
        project_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Handle subscription request.
        
        Args:
            connection_id: Unique identifier for the connection
            thread_ids: Thread IDs to subscribe to
            project_ids: Project IDs to subscribe to
        
        Returns:
            Confirmation message
        """
        for thread_id in thread_ids or []:
            self.manager.subscribe_to_thread(connection_id, thread_id)
        
        for project_id in project_ids or []:
            self.manager.subscribe_to_project(connection_id, project_id)
        
        return {
            "type": "subscribed",
            "thread_ids": thread_ids or [],
            "project_ids": project_ids or [],
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def handle_unsubscribe(
        self,
        connection_id: str,
        thread_ids: Optional[List[str]] = None,
        project_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Handle unsubscription request.
        
        Args:
            connection_id: Unique identifier for the connection
            thread_ids: Thread IDs to unsubscribe from
            project_ids: Project IDs to unsubscribe from
        
        Returns:
            Confirmation message
        """
        for thread_id in thread_ids or []:
            self.manager.unsubscribe_from_thread(connection_id, thread_id)
        
        for project_id in project_ids or []:
            self.manager.unsubscribe_from_project(connection_id, project_id)
        
        return {
            "type": "unsubscribed",
            "thread_ids": thread_ids or [],
            "project_ids": project_ids or [],
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def handle_interrupt_response(
        self,
        response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle an interrupt response submission.
        
        Args:
            response: Response data from client
        
        Returns:
            Confirmation or error message
        """
        try:
            # Validate response
            interrupt_id = response.get("interrupt_id")
            status = response.get("status")
            response_text = response.get("response")
            user_id = response.get("user_id")
            comment = response.get("comment")
            
            if not interrupt_id or not status:
                return {
                    "type": "error",
                    "error": "Missing interrupt_id or status",
                }
            
            # Create response object
            interrupt_response = InterruptResponse(
                interrupt_id=interrupt_id,
                status=InterruptStatus(status),
                response=response_text,
                user_id=user_id,
                comment=comment,
            )
            
            # Handle through manager
            self.manager.handle_interrupt_response(interrupt_response)
            
            return {
                "type": "response_received",
                "response_id": interrupt_response.response_id,
                "interrupt_id": interrupt_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "type": "error",
                "error": str(e),
            }
    
    async def handle_message(
        self,
        connection_id: str,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle an incoming WebSocket message.
        
        Args:
            connection_id: Unique identifier for the connection
            message: The message from the client
        
        Returns:
            Response message to send back
        """
        message_type = message.get("type")
        
        if message_type == "subscribe":
            return await self.handle_subscribe(
                connection_id,
                message.get("thread_ids"),
                message.get("project_ids"),
            )
        elif message_type == "unsubscribe":
            return await self.handle_unsubscribe(
                connection_id,
                message.get("thread_ids"),
                message.get("project_ids"),
            )
        elif message_type == "interrupt_response":
            return await self.handle_interrupt_response(message.get("data", {}))
        elif message_type == "ping":
            return {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
        else:
            return {
                "type": "error",
                "error": f"Unknown message type: {message_type}",
            }
    
    def create_interrupt_notification(
        self,
        interrupt_config: HumanInterruptConfig,
        thread_id: str,
        project_id: Optional[str] = None,
    ) -> InterruptNotification:
        """
        Create an interrupt notification from config.
        
        Args:
            interrupt_config: The interrupt configuration
            thread_id: Thread ID for the interrupt
            project_id: Optional project ID
        
        Returns:
            InterruptNotification instance
        """
        return InterruptNotification(
            interrupt_id=interrupt_config.interrupt_id,
            interrupt_type=interrupt_config.interrupt_type,
            title=interrupt_config.title,
            description=interrupt_config.description,
            priority=interrupt_config.priority.value,
            options=interrupt_config.options,
            thread_id=thread_id,
            project_id=project_id,
            metadata=interrupt_config.metadata,
        )
    
    def create_interrupt_update(
        self,
        interrupt_id: str,
        status: InterruptStatus,
        responded_by: Optional[str] = None,
        response: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> InterruptUpdate:
        """
        Create an interrupt update.
        
        Args:
            interrupt_id: ID of the interrupt
            status: New status
            responded_by: User who responded
            response: Response text
            comment: Optional comment
        
        Returns:
            InterruptUpdate instance
        """
        return InterruptUpdate(
            interrupt_id=interrupt_id,
            status=status,
            responded_at=datetime.utcnow(),
            responded_by=responded_by,
            response=response,
            comment=comment,
        )


# ==================== Factory Functions ====================

def create_websocket_interrupt_manager() -> WebSocketInterruptManager:
    """
    Create a WebSocket interrupt manager.
    
    Returns:
        WebSocketInterruptManager instance
    """
    return WebSocketInterruptManager()


def create_websocket_interrupt_handler(
    manager: Optional[WebSocketInterruptManager] = None,
) -> InterruptWebSocketHandler:
    """
    Create a WebSocket interrupt handler.
    
    Args:
        manager: Optional manager to use
    
    Returns:
        InterruptWebSocketHandler instance
    """
    return InterruptWebSocketHandler(manager)
