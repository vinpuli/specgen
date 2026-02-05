"""
LangGraph streaming implementation for real-time agent output.

This module provides streaming capabilities using LangGraph's astream_events
for real-time token-by-token output, progress updates, and event handling.
"""

import asyncio
import json
from typing import (
    Any, AsyncGenerator, Dict, List, Optional, Callable, Union,
    AsyncIterator, Awaitable
)
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
from functools import partial

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.callbacks.base import BaseCallbackHandler
from langgraph.types import StreamMode
from langgraph.checkpoint.base import Checkpoint

from .agents.types import AgentType


# ==================== Event Types ====================

class StreamEventType(str, Enum):
    """Types of streaming events."""
    CHAT_MODEL_START = "chat_model_start"
    CHAT_MODEL_STREAM = "chat_model_stream"
    CHAT_MODEL_END = "chat_model_end"
    CHAT_MODEL_ERROR = "chat_model_error"
    TOOL_START = "tool_start"
    TOOL_STREAM = "tool_stream"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"
    NODE_START = "node_start"
    NODE_END = "node_end"
    CHECKPOINT = "checkpoint"
    CUSTOM = "custom"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class StreamEvent:
    """A streaming event from LangGraph execution."""
    event_type: StreamEventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    node_name: Optional[str] = None
    run_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "node_name": self.node_name,
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())


# ==================== Callback Handlers ====================

class StreamingCallbackHandler(BaseCallbackHandler):
    """
    Callback handler for capturing LangGraph streaming events.
    
    This handler captures events from LangChain/LangGraph and
    converts them to our standardized StreamEvent format.
    """
    
    def __init__(
        self,
        on_event: Optional[Callable[[StreamEvent], Awaitable[None]]] = None,
        filter_events: Optional[List[StreamEventType]] = None,
    ):
        """
        Initialize the streaming callback handler.
        
        Args:
            on_event: Async callback function for each event
            filter_events: List of event types to capture (None = all)
        """
        self.on_event = on_event
        self.filter_events = filter_events
        self.events: List[StreamEvent] = []
        self.current_run_id: Optional[str] = None
    
    async def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[BaseMessage],
        run_id: str,
        **kwargs,
    ):
        """Handle chat model start event."""
        event = StreamEvent(
            event_type=StreamEventType.CHAT_MODEL_START,
            data={
                "serialized": serialized,
                "message_count": len(messages),
            },
            run_id=run_id,
        )
        await self._emit(event)
    
    async def on_chat_model_stream(
        self,
        token: str,
        run_id: str,
        **kwargs,
    ):
        """Handle chat model stream event (token-by-token)."""
        event = StreamEvent(
            event_type=StreamEventType.CHAT_MODEL_STREAM,
            data={"token": token},
            run_id=run_id,
        )
        await self._emit(event)
    
    async def on_chat_model_end(
        self,
        response: Any,
        run_id: str,
        **kwargs,
    ):
        """Handle chat model end event."""
        event = StreamEvent(
            event_type=StreamEventType.CHAT_MODEL_END,
            data={"response": str(response)},
            run_id=run_id,
        )
        await self._emit(event)
    
    async def on_chat_model_error(
        self,
        error: Exception,
        run_id: str,
        **kwargs,
    ):
        """Handle chat model error event."""
        event = StreamEvent(
            event_type=StreamEventType.CHAT_MODEL_ERROR,
            data={
                "error": str(error),
                "error_type": type(error).__name__,
            },
            run_id=run_id,
        )
        await self._emit(event)
    
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        run_id: str,
        **kwargs,
    ):
        """Handle tool start event."""
        event = StreamEvent(
            event_type=StreamEventType.TOOL_START,
            data={
                "tool": serialized.get("name", "unknown"),
                "input": input_str,
            },
            run_id=run_id,
        )
        await self._emit(event)
    
    async def on_tool_stream(
        self,
        token: str,
        run_id: str,
        **kwargs,
    ):
        """Handle tool stream event."""
        event = StreamEvent(
            event_type=StreamEventType.TOOL_STREAM,
            data={"token": token},
            run_id=run_id,
        )
        await self._emit(event)
    
    async def on_tool_end(
        self,
        output: Any,
        run_id: str,
        **kwargs,
    ):
        """Handle tool end event."""
        event = StreamEvent(
            event_type=StreamEventType.TOOL_END,
            data={"output": str(output)},
            run_id=run_id,
        )
        await self._emit(event)
    
    async def on_tool_error(
        self,
        error: Exception,
        run_id: str,
        **kwargs,
    ):
        """Handle tool error event."""
        event = StreamEvent(
            event_type=StreamEventType.TOOL_ERROR,
            data={
                "error": str(error),
                "error_type": type(error).__name__,
            },
            run_id=run_id,
        )
        await self._emit(event)
    
    async def _emit(self, event: StreamEvent):
        """Emit an event to the callback and storage."""
        self.events.append(event)
        if self.on_event:
            await self.on_event(event)
    
    def clear(self):
        """Clear stored events."""
        self.events.clear()


# ==================== Stream Manager ====================

class StreamManager:
    """
    Manages LangGraph streaming for real-time agent output.
    
    Provides high-level API for streaming agent execution
    with event filtering and transformation.
    """
    
    def __init__(
        self,
        websocket_manager: Optional[Any] = None,
        default_filters: Optional[List[StreamEventType]] = None,
    ):
        """
        Initialize the stream manager.
        
        Args:
            websocket_manager: Optional WebSocket manager for real-time client streaming
            default_filters: Default event types to capture
        """
        self.websocket_manager = websocket_manager
        self.default_filters = default_filters or [
            StreamEventType.CHAT_MODEL_STREAM,
            StreamEventType.NODE_START,
            StreamEventType.NODE_END,
            StreamEventType.CHECKPOINT,
        ]
        self.active_streams: Dict[str, asyncio.Task] = {}
    
    async def astream_events(
        self,
        graph: Runnable,
        input_data: Any,
        config: Optional[RunnableConfig] = None,
        event_callback: Optional[Callable[[StreamEvent], Awaitable[None]]] = None,
        stream_mode: Union[StreamMode, List[StreamMode]] = StreamMode.RUNS,
        interrupt_before: Optional[List[str]] = None,
        interrupt_after: Optional[List[str]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream events from LangGraph execution.
        
        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Runnable configuration
            event_callback: Optional callback for each event
            stream_mode: Stream mode (runs, messages, updates, etc.)
            interrupt_before: Nodes to interrupt before
            interrupt_after: Nodes to interrupt after
        
        Yields:
            StreamEvent objects from the execution
        """
        callback_handler = StreamingCallbackHandler(on_event=event_callback)
        
        run_config = RunnableConfig(
            callbacks=[callback_handler],
            max_tokens=4096,
        )
        if config:
            run_config = RunnableConfig(
                **config,
                callbacks=[callback_handler],
            )
        
        try:
            async for event in graph.astream_events(
                input=input_data,
                config=run_config,
                stream_mode=stream_mode,
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after,
            ):
                # Convert LangGraph event to our format
                stream_event = self._convert_event(event)
                if stream_event:
                    yield stream_event
                    
        except Exception as e:
            yield StreamEvent(
                event_type=StreamEventType.ERROR,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
    
    async def astream_messages(
        self,
        graph: Runnable,
        input_data: Any,
        config: Optional[RunnableConfig] = None,
    ) -> AsyncGenerator[BaseMessage, None]:
        """
        Stream messages from LangGraph execution.
        
        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Runnable configuration
        
        Yields:
            BaseMessage objects from the execution
        """
        async for event in self.astream_events(
            graph=graph,
            input_data=input_data,
            config=config,
            stream_mode=StreamMode.MESSAGES,
        ):
            if event.event_type == StreamEventType.CHAT_MODEL_STREAM:
                # Extract message content from event data
                yield AIMessage(content=event.data.get("token", ""))
    
    async def astream_tokens(
        self,
        graph: Runnable,
        input_data: Any,
        config: Optional[RunnableConfig] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream individual tokens from LLM output.
        
        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Runnable configuration
        
        Yields:
            Token strings from the LLM
        """
        async for event in self.astream_events(
            graph=graph,
            input_data=input_data,
            config=config,
        ):
            if event.event_type == StreamEventType.CHAT_MODEL_STREAM:
                yield event.data.get("token", "")
    
    async def astream_checkpoints(
        self,
        graph: Runnable,
        input_data: Any,
        config: Optional[RunnableConfig] = None,
    ) -> AsyncGenerator[Checkpoint, None]:
        """
        Stream checkpoints from LangGraph execution.
        
        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Runnable configuration
        
        Yields:
            Checkpoint objects from the execution
        """
        async for event in self.astream_events(
            graph=graph,
            input_data=input_data,
            config=config,
            stream_mode=StreamMode.UPDATES,
        ):
            if event.event_type == StreamEventType.CHECKPOINT:
                yield event.data
    
    def _convert_event(self, event: Dict[str, Any]) -> Optional[StreamEvent]:
        """Convert LangGraph event to StreamEvent."""
        event_type_str = event.get("event", "")
        
        # Map LangGraph event types to our types
        type_mapping = {
            "on_chat_model_start": StreamEventType.CHAT_MODEL_START,
            "on_chat_model_stream": StreamEventType.CHAT_MODEL_STREAM,
            "on_chat_model_end": StreamEventType.CHAT_MODEL_END,
            "on_chat_model_error": StreamEventType.CHAT_MODEL_ERROR,
            "on_tool_start": StreamEventType.TOOL_START,
            "on_tool_stream": StreamEventType.TOOL_STREAM,
            "on_tool_end": StreamEventType.TOOL_END,
            "on_tool_error": StreamEventType.TOOL_ERROR,
            "on_node_start": StreamEventType.NODE_START,
            "on_node_end": StreamEventType.NODE_END,
        }
        
        stream_type = type_mapping.get(event_type_str)
        if not stream_type:
            return None
        
        return StreamEvent(
            event_type=stream_type,
            data=event.get("data", {}),
            node_name=event.get("name"),
            run_id=event.get("run_id"),
            parent_run_id=event.get("parent_run_id"),
            tags=event.get("tags", []),
            metadata=event.get("metadata", {}),
        )
    
    async def stream_to_websocket(
        self,
        graph: Runnable,
        input_data: Any,
        room_id: str,
        config: Optional[RunnableConfig] = None,
    ):
        """
        Stream events to connected WebSocket clients.
        
        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            room_id: WebSocket room to stream to
            config: Runnable configuration
        """
        if not self.websocket_manager:
            raise ValueError("WebSocket manager not configured")
        
        async def emit_event(event: StreamEvent):
            await self.websocket_manager.broadcast_to_room(
                room_id=room_id,
                event={
                    "type": event.event_type.value,
                    "data": event.data,
                    "node": event.node_name,
                },
            )
        
        async for event in self.astream_events(
            graph=graph,
            input_data=input_data,
            config=config,
            event_callback=emit_event,
        ):
            # Events are already being streamed to WebSocket
            pass


# ==================== Progress Tracker ====================

class ProgressTracker:
    """
    Tracks progress during long-running agent operations.
    
    Provides progress updates and estimated time remaining.
    """
    
    def __init__(
        self,
        total_steps: int,
        step_name: str = "Processing",
        update_interval: float = 0.5,
    ):
        """
        Initialize the progress tracker.
        
        Args:
            total_steps: Total number of steps
            step_name: Name of the step for display
            update_interval: Minimum seconds between updates
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.step_name = step_name
        self.update_interval = update_interval
        self.start_time = datetime.utcnow()
        self.last_update = self.start_time
        self.step_times: List[float] = []
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_steps == 0:
            return 100.0
        return (self.current_step / self.total_steps) * 100
    
    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def estimated_total_seconds(self) -> float:
        """Estimate total time based on current progress."""
        if self.current_step == 0:
            return 0.0
        
        avg_step_time = self.elapsed_seconds / self.current_step
        return avg_step_time * self.total_steps
    
    @property
    def remaining_seconds(self) -> float:
        """Calculate estimated remaining time."""
        return self.estimated_total_seconds - self.elapsed_seconds
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress information."""
        return {
            "step_name": self.step_name,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "progress_percent": round(self.progress_percent, 1),
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "estimated_total_seconds": round(self.estimated_total_seconds, 1),
            "remaining_seconds": round(self.remaining_seconds, 1),
        }
    
    def update(self, step_delta: int = 1) -> Dict[str, Any]:
        """
        Update progress by a step delta.
        
        Args:
            step_delta: Number of steps to advance
        
        Returns:
            Current progress information
        """
        self.current_step = min(self.current_step + step_delta, self.total_steps)
        now = datetime.utcnow()
        
        # Calculate step time for estimation
        step_time = (now - self.last_update).total_seconds()
        if step_time > 0:
            self.step_times.append(step_time)
            # Keep only last 100 times for averaging
            self.step_times = self.step_times[-100:]
        
        self.last_update = now
        return self.get_progress()
    
    def complete(self) -> Dict[str, Any]:
        """
        Mark progress as complete.
        
        Returns:
            Final progress information
        """
        self.current_step = self.total_steps
        return self.get_progress()


# ==================== Stream Utilities ====================

async def stream_with_progress(
    generator: AsyncGenerator[Any, None],
    progress: ProgressTracker,
) -> AsyncGenerator[Any, None]:
    """
    Wrap a stream with progress tracking.
    
    Args:
        generator: The underlying async generator
        progress: Progress tracker instance
    
    Yields:
        Items from the generator with progress updates
    """
    async for item in generator:
        progress.update()
        yield item


def create_progress_event(
    progress: Dict[str, Any],
    status: str = "in_progress",
) -> StreamEvent:
    """
    Create a progress event for streaming.
    
    Args:
        progress: Progress dictionary
        status: Status of the operation
    
    Returns:
        StreamEvent with progress data
    """
    return StreamEvent(
        event_type=StreamEventType.CHECKPOINT,
        data={
            "progress": progress,
            "status": status,
        },
    )


# ==================== Factory ====================

def get_stream_manager(
    websocket_manager: Optional[Any] = None,
) -> StreamManager:
    """
    Create a stream manager instance.
    
    Args:
        websocket_manager: Optional WebSocket manager
    
    Returns:
        Configured StreamManager instance
    """
    return StreamManager(websocket_manager=websocket_manager)
