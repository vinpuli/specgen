"""
LangGraph Streaming and Events for real-time agent output.

Provides comprehensive streaming capabilities:
- astream_events for real-time agent streaming
- astream_log for structured output streaming
- Custom event handlers
- Token-by-token streaming
- WebSocket integration for frontend
- Checkpoint streaming
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set
from uuid import UUID


class EventType(str, Enum):
    """Types of events for streaming."""

    # LLM Events
    LLM_START = "on_llm_start"
    LLM_END = "on_llm_end"
    LLM_STREAM = "on_llm_stream"
    LLM_NEW_TOKEN = "on_llm_new_token"

    # Tool Events
    TOOL_START = "on_tool_start"
    TOOL_END = "on_tool_end"
    TOOL_ERROR = "on_tool_error"

    # Agent Events
    AGENT_START = "on_agent_start"
    AGENT_END = "on_agent_end"
    AGENT_UPDATE = "on_agent_update"

    # Graph Events
    GRAPH_START = "on_graph_start"
    GRAPH_END = "on_graph_end"
    GRAPH_UPDATE = "on_graph_update"
    GRAPH_CHECKPOINT = "on_graph_checkpoint"

    # Custom Events
    CUSTOM = "on_custom_event"
    PROGRESS = "on_progress"
    METRIC = "on_metric"


class StreamEventCategory(str, Enum):
    """Categories of stream events."""

    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"
    GRAPH = "graph"
    CUSTOM = "custom"


@dataclass
class StreamEvent:
    """A streaming event from LangGraph."""

    event_type: EventType
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    name: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    category: StreamEventCategory = StreamEventCategory.CUSTOM
    data: Dict[str, Any] = field(default_factory=dict)
    agent_name: Optional[str] = None
    node_name: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "name": self.name,
            "tags": self.tags,
            "metadata": self.metadata,
            "category": self.category.value,
            "data": self.data,
            "agent_name": self.agent_name,
            "node_name": self.node_name,
            "error": self.error,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class EventBatch:
    """Represents a batch of stream events aggregated for efficient transport."""

    batch_id: str
    events: List[StreamEvent]
    start_time: str
    end_time: str
    size: int
    categories: List[str] = field(default_factory=list)
    event_types: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert batch to a dictionary payload."""
        return {
            "batch_id": self.batch_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "size": self.size,
            "categories": self.categories,
            "event_types": self.event_types,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass
class TokenEvent:
    """Token-level streaming event."""

    token: str
    is_start: bool = False
    is_end: bool = False
    chunk_index: int = 0
    total_chunks: int = 0
    agent_name: Optional[str] = None
    node_name: Optional[str] = None


@dataclass
class StreamingConfig:
    """Configuration for token streaming."""

    buffer_size: int = 1  # Tokens to buffer before emitting
    emit_on_word_boundary: bool = False  # Emit tokens at word boundaries
    emit_on_sentence_boundary: bool = False  # Emit at sentence boundaries
    min_tokens_per_emit: int = 1  # Minimum tokens before emitting
    timeout_ms: int = 0  # Timeout in milliseconds (0 = no timeout)


class TokenBuffer:
    """
    Buffer for accumulating tokens before emission.

    Features:
    - Configurable buffer size
    - Word boundary detection
    - Sentence boundary detection
    - Timeout-based emission
    """

    def __init__(self, config: Optional[StreamingConfig] = None):
        """
        Initialize token buffer.

        Args:
            config: Streaming configuration
        """
        self.config = config or StreamingConfig()
        self._tokens: List[str] = []
        self._buffer = ""
        self._lastEmitTime = datetime.utcnow()

    def add_token(self, token: str) -> List[str]:
        """
        Add a token to the buffer.

        Args:
            token: Token to add

        Returns:
            List of tokens to emit (empty if still buffering)
        """
        self._tokens.append(token)
        self._buffer += token

        tokens_to_emit = []

        # Check if we should emit based on buffer size
        if len(self._tokens) >= self.config.buffer_size:
            tokens_to_emit = self._tokens.copy()
            self._tokens.clear()
            self._lastEmitTime = datetime.utcnow()
            return tokens_to_emit

        # Check word boundary if enabled
        if self.config.emit_on_word_boundary and self._buffer.strip().endswith((" ", "\n", "\t")):
            if len(self._tokens) >= self.config.min_tokens_per_emit:
                tokens_to_emit = self._tokens.copy()
                self._tokens.clear()
                self._lastEmitTime = datetime.utcnow()
                return tokens_to_emit

        # Check sentence boundary if enabled
        if self.config.emit_on_sentence_boundary and self._buffer.strip().endswith((".", "!", "?", ":", ";")):
            if len(self._tokens) >= self.config.min_tokens_per_emit:
                tokens_to_emit = self._tokens.copy()
                self._tokens.clear()
                self._lastEmitTime = datetime.utcnow()
                return tokens_to_emit

        return tokens_to_emit

    def flush(self) -> List[str]:
        """
        Flush remaining tokens.

        Returns:
            Remaining tokens to emit
        """
        tokens = self._tokens.copy()
        self._tokens.clear()
        self._buffer = ""
        return tokens

    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self._tokens) == 0

    def get_buffered_text(self) -> str:
        """Get current buffered text."""
        return self._buffer


class TokenStreamingManager:
    """
    Advanced token streaming manager with buffering and timing.

    Features:
    - Token buffering with configurable strategies
    - Token accumulation tracking
    - Timing metrics (tokens per second, estimated time remaining)
    - Start/end signal handling
    """

    def __init__(self, config: Optional[StreamingConfig] = None):
        """
        Initialize token streaming manager.

        Args:
            config: Streaming configuration
        """
        self.config = config or StreamingConfig()
        self._buffer = TokenBuffer(self.config)
        self._chunk_index = 0
        self._total_tokens = 0
        self._start_time: Optional[datetime] = None
        self._stream_start_time: Optional[datetime] = None
        self._is_streaming = False
        self._on_token: Optional[Callable] = None
        self._on_start: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    def on_token(self, callback: Callable[[TokenEvent], None]) -> None:
        """
        Set callback for token events.

        Args:
            callback: Function(TokenEvent)
        """
        self._on_token = callback

    def on_start(self, callback: Callable[[], None]) -> None:
        """
        Set callback for stream start.

        Args:
            callback: Function()
        """
        self._on_start = callback

    def on_complete(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set callback for stream completion.

        Args:
            callback: Function(metrics)
        """
        self._on_complete = callback

    async def stream_tokens(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[TokenEvent, None]:
        """
        Stream individual tokens from LLM responses with buffering.

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration

        Yields:
            TokenEvent instances
        """
        self._chunk_index = 0
        self._total_tokens = 0
        self._start_time = datetime.utcnow()
        self._is_streaming = True
        self._stream_start_time = datetime.utcnow()

        if self._on_start:
            self._on_start()

        try:
            async for event in self._stream_events(graph, input_data, config):
                if event.event_type in [EventType.LLM_START]:
                    # Signal start of stream
                    self._chunk_index += 1
                    yield TokenEvent(
                        token="",
                        is_start=True,
                        chunk_index=self._chunk_index,
                        agent_name=event.agent_name,
                        node_name=event.node_name,
                    )

                elif event.event_type in [EventType.LLM_STREAM, EventType.LLM_NEW_TOKEN]:
                    # Get token from event
                    token = event.data.get("chunk", "")
                    if token:
                        # Add to buffer and get tokens to emit
                        tokens_to_emit = self._buffer.add_token(token)

                        for token_text in tokens_to_emit:
                            self._chunk_index += 1
                            self._total_tokens += 1

                            token_event = TokenEvent(
                                token=token_text,
                                is_start=self._total_tokens == 1,
                                chunk_index=self._chunk_index,
                                agent_name=event.agent_name,
                                node_name=event.node_name,
                            )

                            if self._on_token:
                                self._on_token(token_event)

                            yield token_event

                elif event.event_type == EventType.LLM_END:
                    # Flush remaining buffer
                    remaining_tokens = self._buffer.flush()
                    for token_text in remaining_tokens:
                        self._chunk_index += 1
                        self._total_tokens += 1

                        token_event = TokenEvent(
                            token=token_text,
                            chunk_index=self._chunk_index,
                            agent_name=event.agent_name,
                            node_name=event.node_name,
                        )

                        if self._on_token:
                            self._on_token(token_event)

                        yield token_event

                    # Signal end of stream
                    self._chunk_index += 1
                    yield TokenEvent(
                        token="",
                        is_end=True,
                        chunk_index=self._chunk_index,
                        total_chunks=self._total_tokens,
                        agent_name=event.agent_name,
                        node_name=event.node_name,
                    )

        finally:
            self._is_streaming = False

            if self._on_complete:
                metrics = self.get_metrics()
                self._on_complete(metrics)

    async def _stream_events(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream LLM events from graph."""
        async for event in graph.astream_events(input_data, config=config):
            stream_event = self._convert_event(event)
            if stream_event:
                yield stream_event

    def _convert_event(self, event: Dict[str, Any]) -> Optional[StreamEvent]:
        """Convert LangGraph event."""
        try:
            event_type_str = event.get("event", "")
            event_type = self._parse_event_type(event_type_str)

            category = StreamEventCategory.CUSTOM
            if "llm" in event_type_str:
                category = StreamEventCategory.LLM

            return StreamEvent(
                event_type=event_type,
                run_id=event.get("run_id"),
                parent_run_id=event.get("parent_run_id"),
                name=event.get("name"),
                tags=event.get("tags", []),
                metadata=event.get("metadata", {}),
                category=category,
                data=event.get("data", {}),
                agent_name=event.get("metadata", {}).get("agent_name"),
                node_name=event.get("metadata", {}).get("node_name"),
            )
        except Exception as e:
            logging.warning(f"Failed to convert event: {e}")
            return None

    def _parse_event_type(self, event_type_str: str) -> EventType:
        """Parse event type string."""
        mapping = {
            "on_llm_start": EventType.LLM_START,
            "on_llm_end": EventType.LLM_END,
            "on_llm_stream": EventType.LLM_STREAM,
            "on_llm_new_token": EventType.LLM_NEW_TOKEN,
        }
        return mapping.get(event_type_str, EventType.CUSTOM)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get streaming metrics.

        Returns:
            Dictionary containing streaming metrics
        """
        elapsed = 0.0
        if self._start_time:
            elapsed = (datetime.utcnow() - self._start_time).total_seconds()

        return {
            "total_tokens": self._total_tokens,
            "total_chunks": self._chunk_index,
            "elapsed_seconds": elapsed,
            "tokens_per_second": self._total_tokens / elapsed if elapsed > 0 else 0,
            "is_streaming": self._is_streaming,
        }

    def reset(self) -> None:
        """Reset the streaming manager."""
        self._buffer = TokenBuffer(self.config)
        self._chunk_index = 0
        self._total_tokens = 0
        self._start_time = None
        self._is_streaming = False


# Convenience functions
def create_token_streaming_manager(config: Optional[StreamingConfig] = None) -> TokenStreamingManager:
    """Create a new token streaming manager."""
    return TokenStreamingManager(config)


def create_token_buffer(config: Optional[StreamingConfig] = None) -> TokenBuffer:
    """Create a new token buffer."""
    return TokenBuffer(config)


@dataclass
class CheckpointEvent:
    """Checkpoint streaming event."""

    checkpoint_id: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    agent_name: Optional[str] = None
    progress: float = 0.0  # 0-100


@dataclass
class ProgressEvent:
    """Progress update event."""

    current_step: int
    total_steps: int
    message: str
    percentage: float = 0.0
    agent_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgressMilestone:
    """A progress milestone for tracking key checkpoints."""

    name: str
    target_step: int
    description: str = ""
    achieved: bool = False
    achieved_at: Optional[str] = None


@dataclass
class ProgressPhase:
    """A phase in the overall progress with its own milestones."""

    name: str
    start_step: int
    end_step: int
    description: str = ""
    milestones: List[ProgressMilestone] = field(default_factory=list)


@dataclass
class ProgressConfig:
    """Configuration for progress tracking."""

    total_steps: int = 10
    auto_estimate_eta: bool = True
    update_interval: int = 1  # Emit progress every N steps
    include_phases: bool = True
    include_milestones: bool = True
    enable_eta: bool = True
    eta_window_size: int = 5  # Number of recent checkpoints for ETA calculation


class ProgressTracker:
    """
    Advanced progress tracker with ETA, phases, and milestones.

    Features:
    - ETA calculation based on historical checkpoints
    - Progress phases for multi-stage workflows
    - Milestone tracking with achievements
    - Configurable update intervals
    - Progress callbacks
    """

    def __init__(
        self,
        config: Optional[ProgressConfig] = None,
        phases: Optional[List[ProgressPhase]] = None,
    ):
        """
        Initialize the progress tracker.

        Args:
            config: Progress tracking configuration
            phases: Optional list of progress phases
        """
        self.config = config or ProgressConfig()
        self._phases = phases or []
        self._current_step = 0
        self._total_steps = self.config.total_steps
        self._start_time: Optional[datetime] = None
        self._checkpoint_times: List[datetime] = []
        self._checkpoint_steps: List[int] = []
        self._milestones: Dict[str, ProgressMilestone] = {}
        self._current_phase: Optional[ProgressPhase] = None
        self._on_progress: Optional[Callable[[ProgressEvent], None]] = None
        self._on_milestone: Optional[Callable[[ProgressMilestone], None]] = None
        self._on_phase_change: Optional[Callable[[ProgressPhase, ProgressPhase], None]] = None

    def on_progress(self, callback: Callable[[ProgressEvent], None]) -> None:
        """
        Set callback for progress events.

        Args:
            callback: Function(ProgressEvent)
        """
        self._on_progress = callback

    def on_milestone(self, callback: Callable[[ProgressMilestone], None]) -> None:
        """
        Set callback for milestone achievements.

        Args:
            callback: Function(ProgressMilestone)
        """
        self._on_milestone = callback

    def on_phase_change(self, callback: Callable[[ProgressPhase, ProgressPhase], None]) -> None:
        """
        Set callback for phase changes.

        Args:
            callback: Function(old_phase, new_phase)
        """
        self._on_phase_change = callback

    def start(self) -> ProgressEvent:
        """
        Start tracking progress.

        Returns:
            Initial progress event
        """
        self._start_time = datetime.utcnow()
        self._checkpoint_times = []
        self._checkpoint_steps = []
        self._current_step = 0

        # Initialize milestones
        for phase in self._phases:
            for milestone in phase.milestones:
                self._milestones[milestone.name] = milestone

        return self._create_progress_event("Progress tracking started")

    def update(self, step: int, message: str = "") -> Optional[ProgressEvent]:
        """
        Update progress to a specific step.

        Args:
            step: Current step number
            message: Optional message for the progress event

        Returns:
            ProgressEvent if an update should be emitted, None otherwise
        """
        self._current_step = step
        self._checkpoint_times.append(datetime.utcnow())
        self._checkpoint_steps.append(step)

        # Keep only the last N checkpoints for ETA calculation
        if len(self._checkpoint_times) > self.config.eta_window_size:
            self._checkpoint_times = self._checkpoint_times[-self.config.eta_window_size:]
            self._checkpoint_steps = self._checkpoint_steps[-self.config.eta_window_size:]

        # Check for phase changes
        self._check_phase_change()

        # Check for milestone achievements
        self._check_milestones()

        # Create progress event
        progress_event = self._create_progress_event(message)

        # Emit if update interval reached
        if step % self.config.update_interval == 0 or step >= self._total_steps:
            if self._on_progress:
                self._on_progress(progress_event)
            return progress_event

        return None

    def checkpoint(self, checkpoint_data: Dict[str, Any]) -> Optional[ProgressEvent]:
        """
        Update progress from checkpoint data.

        Args:
            checkpoint_data: Checkpoint event data

        Returns:
            ProgressEvent if update should be emitted
        """
        step = checkpoint_data.get("step", 0)
        message = checkpoint_data.get("message", f"Checkpoint {step}")
        return self.update(step, message)

    def complete(self, message: str = "Progress completed") -> ProgressEvent:
        """
        Mark progress as complete.

        Args:
            message: Completion message

        Returns:
            Final progress event
        """
        self._current_step = self._total_steps
        progress_event = self._create_progress_event(message)

        if self._on_progress:
            self._on_progress(progress_event)

        return progress_event

    def _create_progress_event(self, message: str) -> ProgressEvent:
        """Create a progress event."""
        percentage = (self._current_step / self._total_steps) * 100 if self._total_steps > 0 else 0

        eta_seconds = None
        if self.config.enable_eta and self._start_time:
            eta_seconds = self._calculate_eta()

        details = {
            "elapsed_seconds": self._get_elapsed_seconds(),
            "eta_seconds": eta_seconds,
            "steps_remaining": self._total_steps - self._current_step,
            "phases_completed": self._get_phases_completed(),
            "milestones_achieved": self._get_milestones_achieved(),
        }

        return ProgressEvent(
            current_step=self._current_step,
            total_steps=self._total_steps,
            message=message,
            percentage=percentage,
            agent_name=None,
            details=details,
        )

    def _calculate_eta(self) -> Optional[float]:
        """Calculate estimated time to completion."""
        if len(self._checkpoint_times) < 2:
            return None

        # Calculate average time per step
        elapsed = (self._checkpoint_times[-1] - self._checkpoint_times[0]).total_seconds()
        steps_completed = self._checkpoint_steps[-1] - self._checkpoint_steps[0]

        if steps_completed <= 0:
            return None

        avg_time_per_step = elapsed / steps_completed
        remaining_steps = self._total_steps - self._current_step

        return remaining_steps * avg_time_per_step

    def _get_elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if not self._start_time:
            return 0.0
        return (datetime.utcnow() - self._start_time).total_seconds()

    def _check_phase_change(self) -> None:
        """Check and handle phase changes."""
        if not self.config.include_phases:
            return

        for phase in self._phases:
            if (
                self._current_step >= phase.start_step
                and self._current_step <= phase.end_step
                and self._current_phase != phase
            ):
                old_phase = self._current_phase
                self._current_phase = phase

                if self._on_phase_change and old_phase:
                    self._on_phase_change(old_phase, phase)

    def _check_milestones(self) -> None:
        """Check and handle milestone achievements."""
        if not self.config.include_milestones:
            return

        for name, milestone in self._milestones.items():
            if (
                not milestone.achieved
                and self._current_step >= milestone.target_step
            ):
                milestone.achieved = True
                milestone.achieved_at = datetime.utcnow().isoformat()

                if self._on_milestone:
                    self._on_milestone(milestone)

    def _get_phases_completed(self) -> int:
        """Get number of completed phases."""
        if not self._current_phase:
            return 0

        completed = 0
        for phase in self._phases:
            if self._current_step >= phase.end_step:
                completed += 1
        return completed

    def _get_milestones_achieved(self) -> int:
        """Get number of achieved milestones."""
        return sum(1 for m in self._milestones.values() if m.achieved)

    def get_progress(self) -> Dict[str, Any]:
        """
        Get current progress status.

        Returns:
            Dictionary containing progress status
        """
        return {
            "current_step": self._current_step,
            "total_steps": self._total_steps,
            "percentage": (self._current_step / self._total_steps) * 100 if self._total_steps > 0 else 0,
            "elapsed_seconds": self._get_elapsed_seconds(),
            "eta_seconds": self._calculate_eta() if self.config.enable_eta else None,
            "phases": [
                {
                    "name": p.name,
                    "completed": self._current_step >= p.end_step,
                    "current": self._current_phase == p,
                }
                for p in self._phases
            ],
            "milestones_achieved": self._get_milestones_achieved(),
            "total_milestones": len(self._milestones),
        }

    def reset(self) -> None:
        """Reset the progress tracker."""
        self._current_step = 0
        self._start_time = None
        self._checkpoint_times = []
        self._checkpoint_steps = []
        self._current_phase = None

        for milestone in self._milestones.values():
            milestone.achieved = False
            milestone.achieved_at = None


class CheckpointProgressHandler(StreamHandler):
    """
    Enhanced handler for checkpoint events with progress tracking.

    Features:
    - Automatic progress calculation
    - ETA estimation
    - Milestone tracking
    - Phase-based progress
    """

    def __init__(
        self,
        total_steps: int = 10,
        progress_config: Optional[ProgressConfig] = None,
        phases: Optional[List[ProgressPhase]] = None,
    ):
        """
        Initialize the checkpoint progress handler.

        Args:
            total_steps: Estimated total steps for progress calculation
            progress_config: Progress tracking configuration
            phases: Optional list of progress phases
        """
        super().__init__()
        self._total_steps = total_steps
        self._current_step = 0
        self._progress_tracker = ProgressTracker(progress_config, phases)
        self._on_checkpoint: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None
        self._on_eta_update: Optional[Callable] = None

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register event handlers."""
        self.register_handler(
            lambda e: self._handle_checkpoint(e),
            event_type=EventType.GRAPH_CHECKPOINT,
        )
        self.register_handler(
            lambda e: self._handle_agent_update(e),
            event_type=EventType.AGENT_UPDATE,
        )

    def on_checkpoint(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set callback for checkpoint events.

        Args:
            callback: Function(checkpoint_data)
        """
        self._on_checkpoint = callback

    def on_progress(self, callback: Callable[[ProgressEvent], None]) -> None:
        """
        Set callback for progress updates.

        Args:
            callback: Function(ProgressEvent)
        """
        self._on_progress = callback
        self._progress_tracker.on_progress(callback)

    def on_eta_update(self, callback: Callable[[Optional[float]], None]) -> None:
        """
        Set callback for ETA updates.

        Args:
            callback: Function(eta_seconds)
        """
        self._on_eta_update = callback
        self._progress_tracker.on_progress(
            lambda e: callback(e.details.get("eta_seconds")) if e.details else None
        )

    def _handle_checkpoint(self, event: StreamEvent) -> None:
        """Handle checkpoint creation."""
        self._current_step += 1

        checkpoint_data = {
            "checkpoint_id": event.data.get("checkpoint_id"),
            "run_id": event.run_id,
            "step": self._current_step,
            "total_steps": self._total_steps,
            "progress": (self._current_step / self._total_steps) * 100 if self._total_steps > 0 else 0,
            "state": event.data.get("state", {}),
            "metadata": event.metadata,
            "timestamp": event.timestamp,
        }

        # Update progress tracker
        progress_event = self._progress_tracker.checkpoint(checkpoint_data)

        if self._on_checkpoint:
            self._on_checkpoint(checkpoint_data)

    def _handle_agent_update(self, event: StreamEvent) -> None:
        """Handle agent update events."""
        step = event.data.get("step", self._current_step + 1)
        message = event.data.get("message", f"Step {step}")

        self._progress_tracker.update(step, message)

    def start_tracking(self, message: str = "Started tracking") -> ProgressEvent:
        """
        Start progress tracking.

        Args:
            message: Initial message

        Returns:
            Initial progress event
        """
        return self._progress_tracker.start()

    def complete_tracking(self, message: str = "Completed") -> ProgressEvent:
        """
        Complete progress tracking.

        Args:
            message: Completion message

        Returns:
            Final progress event
        """
        return self._progress_tracker.complete(message)

    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """Get all recorded checkpoints."""
        return self._progress_tracker.get_progress()

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress status."""
        return self._progress_tracker.get_progress()

    def get_eta(self) -> Optional[float]:
        """Get estimated time to completion."""
        return self._progress_tracker._calculate_eta()


# Convenience functions for progress tracking
def create_progress_tracker(
    total_steps: int = 10,
    config: Optional[ProgressConfig] = None,
    phases: Optional[List[ProgressPhase]] = None,
) -> ProgressTracker:
    """Create a new progress tracker."""
    return ProgressTracker(config, phases)


def create_checkpoint_progress_handler(
    total_steps: int = 10,
    progress_config: Optional[ProgressConfig] = None,
    phases: Optional[List[ProgressPhase]] = None,
) -> CheckpointProgressHandler:
    """Create a new checkpoint progress handler."""
    return CheckpointProgressHandler(total_steps, progress_config, phases)


def create_default_phases() -> List[ProgressPhase]:
    """
    Create default progress phases for specification generation.

    Returns:
        List of default phases
    """
    return [
        ProgressPhase(
            name="Analysis",
            start_step=0,
            end_step=3,
            description="Analyzing requirements and dependencies",
            milestones=[
                ProgressMilestone(name="analyze_complete", target_step=3, description="Analysis complete"),
            ],
        ),
        ProgressPhase(
            name="Generation",
            start_step=3,
            end_step=7,
            description="Generating specification artifacts",
            milestones=[
                ProgressMilestone(name="prd_generated", target_step=4, description="PRD generated"),
                ProgressMilestone(name="api_generated", target_step=5, description="API contracts generated"),
                ProgressMilestone(name="schema_generated", target_step=6, description="Database schema generated"),
            ],
        ),
        ProgressPhase(
            name="Validation",
            start_step=7,
            end_step=9,
            description="Validating generated artifacts",
            milestones=[
                ProgressMilestone(name="validation_complete", target_step=9, description="Validation complete"),
            ],
        ),
        ProgressPhase(
            name="Delivery",
            start_step=9,
            end_step=10,
            description="Exporting final deliverables",
            milestones=[
                ProgressMilestone(name="delivery_complete", target_step=10, description="Delivery complete"),
            ],
        ),
    ]


class StreamHandler:
    """Base class for stream event handlers."""

    def __init__(self):
        """Initialize the handler."""
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._category_handlers: Dict[StreamEventCategory, List[Callable]] = {}

    def register_handler(
        self,
        handler: Callable,
        event_type: Optional[EventType] = None,
        category: Optional[StreamEventCategory] = None,
    ) -> None:
        """
        Register an event handler.

        Args:
            handler: Handler function
            event_type: Specific event type to handle
            category: Event category to handle
        """
        if event_type:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

        if category:
            if category not in self._category_handlers:
                self._category_handlers[category] = []
            self._category_handlers[category].append(handler)

    async def handle_event(self, event: StreamEvent) -> None:
        """Handle a stream event."""
        # Call specific event handlers
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                await handler(event)

        # Call category handlers
        if event.category in self._category_handlers:
            for handler in self._category_handlers[event.category]:
                await handler(event)


class LLMOutputHandler(StreamHandler):
    """
    Specialized handler for LLM streaming outputs.

    Features:
    - Collects streaming tokens
    - Tracks token counts
    - Calculates timing metrics
    - Supports partial and final output aggregation
    """

    def __init__(self):
        """Initialize the LLM output handler."""
        super().__init__()
        self._current_outputs: Dict[str, str] = {}  # run_id -> accumulated output
        self._token_counts: Dict[str, int] = {}
        self._start_times: Dict[str, datetime] = {}
        self._on_token: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    def on_token(self, callback: Callable[[str, str, int], None]) -> None:
        """
        Set callback for token events.

        Args:
            callback: Function(run_id, token, total_tokens)
        """
        self._on_token = callback
        self.register_handler(
            lambda e: self._handle_token(e),
            event_type=EventType.LLM_STREAM,
        )
        self.register_handler(
            lambda e: self._handle_new_token(e),
            event_type=EventType.LLM_NEW_TOKEN,
        )

    def on_complete(self, callback: Callable[[str, str, float], None]) -> None:
        """
        Set callback for LLM completion events.

        Args:
            callback: Function(run_id, full_output, duration_seconds)
        """
        self._on_complete = callback
        self.register_handler(
            lambda e: self._handle_complete(e),
            event_type=EventType.LLM_END,
        )

    def _handle_token(self, event: StreamEvent) -> None:
        """Handle LLM stream token."""
        run_id = event.run_id or "default"
        token = event.data.get("chunk", "")

        if run_id not in self._current_outputs:
            self._current_outputs[run_id] = ""
            self._token_counts[run_id] = 0
            self._start_times[run_id] = datetime.utcnow()

        self._current_outputs[run_id] += token
        self._token_counts[run_id] += 1

        if self._on_token:
            self._on_token(run_id, token, self._token_counts[run_id])

    def _handle_new_token(self, event: StreamEvent) -> None:
        """Handle new token event."""
        self._handle_token(event)

    def _handle_complete(self, event: StreamEvent) -> None:
        """Handle LLM completion."""
        run_id = event.run_id or "default"
        start_time = self._start_times.get(run_id)
        duration = (datetime.utcnow() - start_time).total_seconds() if start_time else 0

        output = self._current_outputs.get(run_id, "")

        if self._on_complete:
            self._on_complete(run_id, output, duration)

        # Cleanup
        self._current_outputs.pop(run_id, None)
        self._token_counts.pop(run_id, None)
        self._start_times.pop(run_id, None)

    def get_current_output(self, run_id: str = "default") -> str:
        """Get current accumulated output for a run."""
        return self._current_outputs.get(run_id, "")

    def get_token_count(self, run_id: str = "default") -> int:
        """Get token count for a run."""
        return self._token_counts.get(run_id, 0)


class ToolOutputHandler(StreamHandler):
    """
    Specialized handler for tool execution outputs.

    Features:
    - Tracks tool execution status
    - Collects tool inputs and outputs
    - Records execution duration
    - Handles errors gracefully
    """

    def __init__(self):
        """Initialize the tool output handler."""
        super().__init__()
        self._executions: Dict[str, Dict[str, Any]] = {}
        self._on_start: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    def on_start(self, callback: Callable[[str, str, Dict], None]) -> None:
        """
        Set callback for tool start events.

        Args:
            callback: Function(run_id, tool_name, input_data)
        """
        self._on_start = callback
        self.register_handler(
            lambda e: self._handle_start(e),
            event_type=EventType.TOOL_START,
        )

    def on_complete(self, callback: Callable[[str, str, Any, float], None]) -> None:
        """
        Set callback for tool completion events.

        Args:
            callback: Function(run_id, tool_name, output, duration)
        """
        self._on_complete = callback
        self.register_handler(
            lambda e: self._handle_complete(e),
            event_type=EventType.TOOL_END,
        )

    def on_error(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Set callback for tool error events.

        Args:
            callback: Function(run_id, tool_name, error_message)
        """
        self._on_error = callback
        self.register_handler(
            lambda e: self._handle_error(e),
            event_type=EventType.TOOL_ERROR,
        )

    def _handle_start(self, event: StreamEvent) -> None:
        """Handle tool execution start."""
        run_id = event.run_id or "default"
        tool_name = event.name or "unknown"
        input_data = event.data.get("input", {})

        self._executions[run_id] = {
            "tool_name": tool_name,
            "input": input_data,
            "start_time": datetime.utcnow(),
        }

        if self._on_start:
            self._on_start(run_id, tool_name, input_data)

    def _handle_complete(self, event: StreamEvent) -> None:
        """Handle tool execution completion."""
        run_id = event.run_id or "default"
        execution = self._executions.get(run_id, {})
        tool_name = execution.get("tool_name", event.name or "unknown")
        start_time = execution.get("start_time")
        duration = (datetime.utcnow() - start_time).total_seconds() if start_time else 0
        output = event.data.get("output")

        if self._on_complete:
            self._on_complete(run_id, tool_name, output, duration)

        self._executions.pop(run_id, None)

    def _handle_error(self, event: StreamEvent) -> None:
        """Handle tool execution error."""
        run_id = event.run_id or "default"
        tool_name = event.name or "unknown"
        error = event.error or event.data.get("error", "Unknown error")

        if self._on_error:
            self._on_error(run_id, tool_name, error)

        self._executions.pop(run_id, None)

    def get_execution_status(self, run_id: str = "default") -> Optional[Dict[str, Any]]:
        """Get current execution status for a run."""
        return self._executions.get(run_id)


class AgentOutputHandler(StreamHandler):
    """
    Specialized handler for agent-level outputs.

    Features:
    - Tracks agent state transitions
    - Collects agent decisions
    - Records node execution details
    """

    def __init__(self):
        """Initialize the agent output handler."""
        super().__init__()
        self._state_history: List[Dict[str, Any]] = []
        self._on_state_change: Optional[Callable] = None
        self._on_agent_action: Optional[Callable] = None

    def on_state_change(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set callback for agent state changes.

        Args:
            callback: Function(state_data)
        """
        self._on_state_change = callback
        self.register_handler(
            lambda e: self._handle_state_change(e),
            category=StreamEventCategory.AGENT,
        )

    def on_agent_action(self, callback: Callable[[str, str, Dict], None]) -> None:
        """
        Set callback for agent actions.

        Args:
            callback: Function(run_id, action_type, action_data)
        """
        self._on_agent_action = callback
        self.register_handler(
            lambda e: self._handle_agent_action(e),
            category=StreamEventCategory.AGENT,
        )

    def _handle_state_change(self, event: StreamEvent) -> None:
        """Handle agent state change."""
        state_data = {
            "run_id": event.run_id,
            "event_type": event.event_type.value,
            "name": event.name,
            "data": event.data,
            "timestamp": event.timestamp,
        }
        self._state_history.append(state_data)

        if self._on_state_change:
            self._on_state_change(state_data)

    def _handle_agent_action(self, event: StreamEvent) -> None:
        """Handle agent action."""
        if self._on_agent_action:
            self._on_agent_action(
                event.run_id or "default",
                event.event_type.value,
                event.data,
            )

    def get_state_history(self) -> List[Dict[str, Any]]:
        """Get full state transition history."""
        return self._state_history.copy()


class CheckpointHandler(StreamHandler):
    """
    Specialized handler for checkpoint events.

    Features:
    - Tracks checkpoint creation
    - Records state snapshots
    - Calculates progress percentage
    """

    def __init__(self, total_steps: int = 10):
        """
        Initialize the checkpoint handler.

        Args:
            total_steps: Estimated total steps for progress calculation
        """
        super().__init__()
        self._total_steps = total_steps
        self._current_step = 0
        self._checkpoints: List[Dict[str, Any]] = []
        self._on_checkpoint: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None

    def on_checkpoint(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set callback for checkpoint events.

        Args:
            callback: Function(checkpoint_data)
        """
        self._on_checkpoint = callback
        self.register_handler(
            lambda e: self._handle_checkpoint(e),
            event_type=EventType.GRAPH_CHECKPOINT,
        )

    def on_progress(self, callback: Callable[[float, int, int], None]) -> None:
        """
        Set callback for progress updates.

        Args:
            callback: Function(percentage, current_step, total_steps)
        """
        self._on_progress = callback

    def _handle_checkpoint(self, event: StreamEvent) -> None:
        """Handle checkpoint creation."""
        self._current_step += 1
        progress = (self._current_step / self._total_steps) * 100 if self._total_steps > 0 else 0

        checkpoint_data = {
            "checkpoint_id": event.data.get("checkpoint_id"),
            "run_id": event.run_id,
            "step": self._current_step,
            "total_steps": self._total_steps,
            "progress": progress,
            "state": event.data.get("state", {}),
            "metadata": event.metadata,
            "timestamp": event.timestamp,
        }
        self._checkpoints.append(checkpoint_data)

        if self._on_checkpoint:
            self._on_checkpoint(checkpoint_data)

        if self._on_progress:
            self._on_progress(progress, self._current_step, self._total_steps)

    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """Get all recorded checkpoints."""
        return self._checkpoints.copy()

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress status."""
        return {
            "current_step": self._current_step,
            "total_steps": self._total_steps,
            "percentage": (self._current_step / self._total_steps) * 100 if self._total_steps > 0 else 0,
        }


class CompositeHandler(StreamHandler):
    """
    Handler that combines multiple specialized handlers.

    Features:
    - Combines LLM, tool, agent, and checkpoint handlers
    - Centralized event processing
    - Easy to add/remove handlers dynamically
    """

    def __init__(self):
        """Initialize the composite handler."""
        super().__init__()
        self.llm_handler = LLMOutputHandler()
        self.tool_handler = ToolOutputHandler()
        self.agent_handler = AgentOutputHandler()
        self.checkpoint_handler = CheckpointHandler()

    def add_handler(self, handler: StreamHandler) -> None:
        """Add a custom handler to the composite."""
        super().add_handler(handler)

    def remove_handler(self, handler: StreamHandler) -> None:
        """Remove a handler from the composite."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def handle_event(self, event: StreamEvent) -> None:
        """Handle event with all registered handlers."""
        # Handle with specialized handlers
        await self.llm_handler.handle_event(event)
        await self.tool_handler.handle_event(event)
        await self.agent_handler.handle_event(event)
        await self.checkpoint_handler.handle_event(event)

        # Handle with custom handlers
        await super().handle_event(event)


# Convenience function for creating common handlers
def create_llm_handler() -> LLMOutputHandler:
    """Create a new LLM output handler."""
    return LLMOutputHandler()


def create_tool_handler() -> ToolOutputHandler:
    """Create a new tool output handler."""
    return ToolOutputHandler()


def create_agent_handler() -> AgentOutputHandler:
    """Create a new agent output handler."""
    return AgentOutputHandler()


def create_checkpoint_handler(total_steps: int = 10) -> CheckpointHandler:
    """Create a new checkpoint handler."""
    return CheckpointHandler(total_steps)


def create_composite_handler() -> CompositeHandler:
    """Create a new composite handler with all standard handlers."""
    return CompositeHandler()


class StreamingManager:
    """
    Manage real-time streaming for LangGraph agents.

    Features:
    - astream_events integration
    - Event filtering and transformation
    - Multiple output formats
    - WebSocket broadcasting
    - Progress tracking
    """

    def __init__(self):
        """Initialize the streaming manager."""
        self._handlers: List[StreamHandler] = []
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._filter_event_types: Set[EventType] = set()
        self._filter_categories: Set[StreamEventCategory] = set()
        self._custom_filter_predicate: Optional[Callable[[StreamEvent], bool]] = None

    def add_handler(self, handler: StreamHandler) -> None:
        """
        Add a stream handler.

        Args:
            handler: Handler to add
        """
        self._handlers.append(handler)

    def remove_handler(self, handler: StreamHandler) -> None:
        """Remove a stream handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def set_event_filter(
        self,
        event_types: Optional[List[EventType]] = None,
        categories: Optional[List[StreamEventCategory]] = None,
        custom_predicate: Optional[Callable[[StreamEvent], bool]] = None,
    ) -> None:
        """
        Set filters for events.

        Args:
            event_types: Specific event types to include
            categories: Event categories to include
            custom_predicate: Optional custom predicate for advanced filtering
        """
        self._filter_event_types = set(event_types) if event_types else set()
        self._filter_categories = set(categories) if categories else set()
        self._custom_filter_predicate = custom_predicate

    def clear_filters(self) -> None:
        """Clear all event filters."""
        self._filter_event_types.clear()
        self._filter_categories.clear()
        self._custom_filter_predicate = None

    def _event_passes_filters(self, event: StreamEvent) -> bool:
        """Check whether event passes all active filter criteria."""
        if self._filter_event_types and event.event_type not in self._filter_event_types:
            return False
        if self._filter_categories and event.category not in self._filter_categories:
            return False
        if self._custom_filter_predicate and not self._custom_filter_predicate(event):
            return False
        return True

    async def _process_event(self, event: StreamEvent) -> None:
        """Process and distribute an event."""
        if not self._event_passes_filters(event):
            return

        # Distribute to handlers
        for handler in self._handlers:
            await handler.handle_event(event)

    async def stream_events(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        event_types: Optional[List[EventType]] = None,
        categories: Optional[List[StreamEventCategory]] = None,
        event_filter: Optional["EventFilter"] = None,
        chat_model_filter: Optional["ChatModelEventFilter"] = None,
        tool_event_filter: Optional["ToolEventFilter"] = None,
        agent_event_filter: Optional["AgentEventFilter"] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream events from a LangGraph.

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration
            event_types: Optional event types to filter
            categories: Optional event categories to filter
            event_filter: Optional composable EventFilter
            chat_model_filter: Optional ChatModelEventFilter for LLM events
            tool_event_filter: Optional ToolEventFilter for tool execution events
            agent_event_filter: Optional AgentEventFilter for custom agent events

        Yields:
            StreamEvent instances
        """
        predicates: List[Callable[[StreamEvent], bool]] = []
        if event_filter:
            predicates.append(event_filter.matches)
        if chat_model_filter:
            predicates.append(chat_model_filter.matches)
        if tool_event_filter:
            predicates.append(tool_event_filter.matches)
        if agent_event_filter:
            predicates.append(agent_event_filter.matches)
        custom_predicate: Optional[Callable[[StreamEvent], bool]] = None
        if predicates:
            custom_predicate = lambda e: all(predicate(e) for predicate in predicates)

        self.set_event_filter(
            event_types=event_types,
            categories=categories,
            custom_predicate=custom_predicate,
        )

        try:
            # Use astream_events from LangGraph
            async for event in graph.astream_events(input_data, config=config):
                stream_event = self._convert_langgraph_event(event)
                if stream_event and self._event_passes_filters(stream_event):
                    await self._process_event(stream_event)
                    yield stream_event
        finally:
            self.clear_filters()

    async def stream_event_batches(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        event_types: Optional[List[EventType]] = None,
        categories: Optional[List[StreamEventCategory]] = None,
        event_filter: Optional["EventFilter"] = None,
        chat_model_filter: Optional["ChatModelEventFilter"] = None,
        tool_event_filter: Optional["ToolEventFilter"] = None,
        agent_event_filter: Optional["AgentEventFilter"] = None,
        batch_size: int = 20,
        batch_interval_ms: int = 50,
    ) -> AsyncGenerator[EventBatch, None]:
        """
        Stream events as aggregated batches for efficient downstream updates.

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional graph configuration
            event_types: Optional event type filter
            categories: Optional category filter
            event_filter: Optional generic event filter
            chat_model_filter: Optional chat model event filter
            tool_event_filter: Optional tool event filter
            agent_event_filter: Optional agent event filter
            batch_size: Maximum number of events per batch
            batch_interval_ms: Maximum age of a batch before flush

        Yields:
            EventBatch instances
        """
        aggregator = EventBatchAggregator(
            max_batch_size=batch_size,
            max_wait_ms=batch_interval_ms,
        )

        async for event in self.stream_events(
            graph=graph,
            input_data=input_data,
            config=config,
            event_types=event_types,
            categories=categories,
            event_filter=event_filter,
            chat_model_filter=chat_model_filter,
            tool_event_filter=tool_event_filter,
            agent_event_filter=agent_event_filter,
        ):
            batch = aggregator.add_event(event)
            if batch:
                yield batch

        final_batch = aggregator.flush()
        if final_batch:
            yield final_batch

    def _convert_langgraph_event(self, event: Dict[str, Any]) -> Optional[StreamEvent]:
        """Convert a LangGraph event to our StreamEvent format."""
        try:
            event_type_str = event.get("event", "")
            event_type = self._parse_event_type(event_type_str)

            # Map to our event type
            if "llm" in event_type_str:
                category = StreamEventCategory.LLM
            elif "tool" in event_type_str:
                category = StreamEventCategory.TOOL
            elif "agent" in event_type_str:
                category = StreamEventCategory.AGENT
            elif "graph" in event_type_str:
                category = StreamEventCategory.GRAPH
            else:
                category = StreamEventCategory.CUSTOM

            return StreamEvent(
                event_type=event_type,
                run_id=event.get("run_id"),
                parent_run_id=event.get("parent_run_id"),
                name=event.get("name"),
                tags=event.get("tags", []),
                metadata=event.get("metadata", {}),
                category=category,
                data=event.get("data", {}),
                agent_name=event.get("metadata", {}).get("agent_name"),
                node_name=event.get("metadata", {}).get("node_name"),
            )
        except Exception as e:
            logging.warning(f"Failed to convert LangGraph event: {e}")
            return None

    def _parse_event_type(self, event_type_str: str) -> EventType:
        """Parse event type string to enum."""
        mapping = {
            "on_llm_start": EventType.LLM_START,
            "on_llm_end": EventType.LLM_END,
            "on_llm_stream": EventType.LLM_STREAM,
            "on_llm_new_token": EventType.LLM_NEW_TOKEN,
            "on_tool_start": EventType.TOOL_START,
            "on_tool_end": EventType.TOOL_END,
            "on_tool_error": EventType.TOOL_ERROR,
            "on_agent_start": EventType.AGENT_START,
            "on_agent_end": EventType.AGENT_END,
            "on_agent_update": EventType.AGENT_UPDATE,
            "on_graph_start": EventType.GRAPH_START,
            "on_graph_end": EventType.GRAPH_END,
            "on_graph_update": EventType.GRAPH_UPDATE,
            "on_graph_checkpoint": EventType.GRAPH_CHECKPOINT,
        }
        return mapping.get(event_type_str, EventType.CUSTOM)

    async def stream_tokens(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[TokenEvent, None]:
        """
        Stream individual tokens from LLM responses.

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration

        Yields:
            TokenEvent instances
        """
        chunk_buffer = ""
        chunk_index = 0

        async for event in self.stream_events(graph, input_data, config):
            if event.event_type in [EventType.LLM_STREAM, EventType.LLM_NEW_TOKEN]:
                # Extract token from data
                token = event.data.get("chunk", "")
                if token:
                    chunk_buffer += token
                    chunk_index += 1

                    # Yield token event
                    yield TokenEvent(
                        token=token,
                        is_start=chunk_index == 1,
                        chunk_index=chunk_index,
                        agent_name=event.agent_name,
                        node_name=event.node_name,
                    )

            elif event.event_type == EventType.LLM_END:
                # Signal end of stream
                yield TokenEvent(
                    token="",
                    is_end=True,
                    chunk_index=chunk_index,
                    agent_name=event.agent_name,
                    node_name=event.node_name,
                )

    async def stream_checkpoints(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        total_steps: int = 10,
    ) -> AsyncGenerator[CheckpointEvent, None]:
        """
        Stream checkpoint events.

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration
            total_steps: Estimated total steps for progress calculation

        Yields:
            CheckpointEvent instances
        """
        current_step = 0

        async for event in self.stream_events(graph, input_data, config):
            if event.event_type == EventType.GRAPH_CHECKPOINT:
                checkpoint_id = event.data.get("checkpoint_id", "")
                metadata = event.metadata or {}
                state = event.data.get("state", {})

                # Calculate progress
                current_step += 1
                progress = (current_step / total_steps) * 100 if total_steps > 0 else 0

                yield CheckpointEvent(
                    checkpoint_id=checkpoint_id,
                    timestamp=datetime.utcnow().isoformat(),
                    metadata=metadata,
                    state=state,
                    agent_name=event.agent_name,
                    progress=progress,
                )

    async def stream_progress(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        total_steps: int = 10,
        progress_config: Optional[ProgressConfig] = None,
        phases: Optional[List[ProgressPhase]] = None,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """
        Stream progress events with ETA, phases, and milestones.

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration
            total_steps: Estimated total steps for progress calculation
            progress_config: Progress tracking configuration
            phases: Optional list of progress phases

        Yields:
            ProgressEvent instances with detailed progress information
        """
        tracker = ProgressTracker(progress_config, phases)
        tracker._total_steps = total_steps

        # Emit start event
        start_event = tracker.start()
        yield start_event

        current_step = 0

        async for event in self.stream_events(graph, input_data, config):
            if event.event_type == EventType.GRAPH_CHECKPOINT:
                current_step += 1
                checkpoint_id = event.data.get("checkpoint_id", f"checkpoint_{current_step}")

                progress_event = tracker.checkpoint({
                    "checkpoint_id": checkpoint_id,
                    "step": current_step,
                    "message": f"Checkpoint {current_step}: {event.name or 'Processing'}",
                })

                if progress_event:
                    yield progress_event

            elif event.event_type == EventType.AGENT_UPDATE:
                step = event.data.get("step", current_step + 1)
                message = event.data.get("message", event.name or "Processing")

                progress_event = tracker.update(step, message)
                if progress_event:
                    yield progress_event

            elif event.event_type == EventType.LLM_START:
                progress_event = tracker.update(current_step, f"Generating: {event.name or 'LLM'}")
                if progress_event:
                    yield progress_event

            elif event.event_type == EventType.LLM_END:
                progress_event = tracker.update(current_step, f"Completed: {event.name or 'LLM'}")
                if progress_event:
                    yield progress_event

            elif event.event_type == EventType.TOOL_START:
                progress_event = tracker.update(current_step, f"Executing: {event.name or 'Tool'}")
                if progress_event:
                    yield progress_event

            elif event.event_type == EventType.TOOL_END:
                progress_event = tracker.update(current_step, f"Completed: {event.name or 'Tool'}")
                if progress_event:
                    yield progress_event

        # Emit completion event
        completion_event = tracker.complete("All tasks completed")
        yield completion_event

    async def stream_checkpoints_with_eta(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        total_steps: int = 10,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream checkpoints with ETA estimation.

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration
            total_steps: Estimated total steps for progress calculation

        Yields:
            Dictionary containing checkpoint data with ETA
        """
        tracker = ProgressTracker(enable_eta=True)
        tracker._total_steps = total_steps

        # Emit start
        yield {
            "event_type": "start",
            "message": "Progress tracking started",
            "total_steps": total_steps,
            "timestamp": datetime.utcnow().isoformat(),
        }

        current_step = 0
        checkpoint_times: List[datetime] = []
        checkpoint_steps: List[int] = []

        async for event in self.stream_events(graph, input_data, config):
            if event.event_type == EventType.GRAPH_CHECKPOINT:
                current_step += 1
                now = datetime.utcnow()
                checkpoint_times.append(now)
                checkpoint_steps.append(current_step)

                # Calculate ETA
                eta_seconds = None
                if len(checkpoint_times) >= 2:
                    elapsed = (checkpoint_times[-1] - checkpoint_times[0]).total_seconds()
                    steps_completed = checkpoint_steps[-1] - checkpoint_steps[0]
                    if steps_completed > 0:
                        avg_time = elapsed / steps_completed
                        remaining_steps = total_steps - current_step
                        eta_seconds = remaining_steps * avg_time

                yield {
                    "event_type": "checkpoint",
                    "checkpoint_id": event.data.get("checkpoint_id"),
                    "step": current_step,
                    "total_steps": total_steps,
                    "progress": (current_step / total_steps) * 100,
                    "eta_seconds": eta_seconds,
                    "elapsed_seconds": (now - checkpoint_times[0]).total_seconds() if checkpoint_times else 0,
                    "timestamp": now.isoformat(),
                    "agent_name": event.agent_name,
                }

        # Emit completion
        yield {
            "event_type": "complete",
            "message": "All tasks completed",
            "total_steps": total_steps,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def stream_log(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        include_outputs: bool = True,
        auto_refresh: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream structured output from LangGraph using astream_log.

        Provides detailed execution metadata including:
        - Step-by-step execution trace
        - Output values at each step
        - Node metadata and timing
        - Graph state changes

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration
            include_outputs: Whether to include output values in the stream
            auto_refresh: Whether to auto-refresh during execution

        Yields:
            Dictionary containing log entries with structured data
        """
        try:
            async for log_entry in graph.astream_log(
                input_data,
                config=config,
                include_outputs=include_outputs,
                auto_refresh=auto_refresh,
            ):
                yield self._format_log_entry(log_entry)
        except Exception as e:
            logging.error(f"Error in stream_log: {e}")
            yield {
                "event_type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _format_log_entry(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a LangGraph log entry for easier consumption.

        Args:
            log_entry: Raw log entry from LangGraph

        Returns:
            Formatted log entry
        """
        formatted = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": log_entry.get("event", "unknown"),
            "run_id": log_entry.get("run_id"),
            "parent_run_id": log_entry.get("parent_run_id"),
            "metadata": log_entry.get("metadata", {}),
        }

        # Extract node information
        if "node" in log_entry:
            formatted["node"] = {
                "name": log_entry["node"].get("name") if isinstance(log_entry["node"], dict) else log_entry["node"],
                "id": log_entry["node"].get("id") if isinstance(log_entry["node"], dict) else None,
            }

        # Extract output if present
        if "output" in log_entry:
            formatted["output"] = log_entry["output"]

        # Extract input if present
        if "input" in log_entry:
            formatted["input"] = log_entry["input"]

        # Extract state changes
        if "state" in log_entry:
            formatted["state"] = log_entry["state"]

        # Extract timing if present
        if "latent" in log_entry:
            formatted["timing"] = {
                "latent": log_entry["latent"],
            }
        if "thumbnail" in log_entry:
            formatted["timing"] = formatted.get("timing", {})
            formatted["timing"]["thumbnail"] = log_entry["thumbnail"]

        return formatted

    async def stream_with_metadata(
        self,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        stream_mode: str = "updates",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream from LangGraph with flexible mode selection.

        Supported stream modes:
        - "values": Stream state values at each step
        - "updates": Stream only state updates
        - "messages": Stream LLM messages only
        - "messages_and_updates": Stream both messages and updates
        - "all": Stream all events

        Args:
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration
            stream_mode: Mode for streaming

        Yields:
            Dictionary containing streamed data
        """
        try:
            async for chunk in graph.astream(
                input_data,
                config=config,
                mode=stream_mode,
            ):
                yield {
                    "event_type": "chunk",
                    "timestamp": datetime.utcnow().isoformat(),
                    "mode": stream_mode,
                    "data": chunk,
                }
        except Exception as e:
            logging.error(f"Error in stream_with_metadata: {e}")
            yield {
                "event_type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


class FrontendEventType(str, Enum):
    """Frontend event types for WebSocket messages."""

    # Connection events
    CONNECT = "connection_established"
    DISCONNECT = "connection_closed"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"

    # Stream events
    STREAM_START = "stream_start"
    STREAM_END = "stream_end"
    STREAM_ERROR = "stream_error"
    BATCH_UPDATE = "batch_update"

    # Agent events
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_UPDATE = "agent_update"

    # LLM events
    LLM_TOKEN = "llm_token"
    LLM_START = "llm_start"
    LLM_END = "llm_end"

    # Tool events
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"

    # Progress events
    PROGRESS_UPDATE = "progress_update"
    CHECKPOINT = "checkpoint"
    MILESTONE = "milestone"
    PHASE_CHANGE = "phase_change"

    # Artifact events
    ARTIFACT_START = "artifact_start"
    ARTIFACT_PROGRESS = "artifact_progress"
    ARTIFACT_COMPLETE = "artifact_complete"

    # Interrupt events
    INTERRUPT = "interrupt"
    INTERRUPT_RESOLVED = "interrupt_resolved"


@dataclass
class FrontendStreamConfig:
    """Configuration for frontend streaming."""

    enable_token_streaming: bool = True
    enable_progress_streaming: bool = True
    enable_artifact_streaming: bool = True
    batch_events: bool = True
    batch_interval_ms: int = 50
    include_timestamps: bool = True
    include_run_id: bool = True
    compress_tokens: bool = True  # Send tokens as array for efficiency
    enable_event_debouncing: bool = True
    debounce_interval_ms: int = 100
    debounce_event_types: List[EventType] = field(
        default_factory=lambda: [EventType.AGENT_UPDATE]
    )


class EventDebouncer:
    """Debounce high-frequency events to reduce frontend update pressure."""

    def __init__(
        self,
        enabled: bool = True,
        debounce_interval_ms: int = 100,
        debounce_event_types: Optional[List[EventType]] = None,
    ):
        self.enabled = enabled
        self.debounce_interval_ms = max(1, debounce_interval_ms)
        self.debounce_event_types = set(debounce_event_types or [EventType.AGENT_UPDATE])
        self._last_emit_at: Dict[str, datetime] = {}

    def should_emit(self, stream_id: str, event: StreamEvent) -> bool:
        """Return True if event should be emitted based on debounce rules."""
        if not self.enabled:
            return True

        if event.event_type not in self.debounce_event_types:
            return True

        key = "|".join(
            [
                stream_id,
                event.event_type.value,
                event.agent_name or "",
                event.node_name or "",
                event.name or "",
            ]
        )
        now = datetime.utcnow()
        previous = self._last_emit_at.get(key)
        if previous is None:
            self._last_emit_at[key] = now
            return True

        elapsed_ms = (now - previous).total_seconds() * 1000
        if elapsed_ms >= self.debounce_interval_ms:
            self._last_emit_at[key] = now
            return True

        return False

    def clear_stream(self, stream_id: str) -> None:
        """Clear debounce cache entries for a specific stream."""
        prefix = f"{stream_id}|"
        for key in [k for k in self._last_emit_at.keys() if k.startswith(prefix)]:
            del self._last_emit_at[key]


class FrontendWebSocketBridge:
    """
    WebSocket bridge for streaming events to frontend.

    Features:
    - Frontend-specific event formatting
    - Token streaming with buffering
    - Progress tracking and updates
    - Artifact generation streaming
    - Connection lifecycle management
    - Event batching for performance
    - Heartbeat and reconnection support
    """

    def __init__(self, config: Optional[FrontendStreamConfig] = None):
        """
        Initialize the frontend WebSocket bridge.

        Args:
            config: Frontend streaming configuration
        """
        self.config = config or FrontendStreamConfig()
        self._connections: Dict[str, Dict[str, Any]] = {}  # connection_id -> connection_info
        self._streams: Dict[str, Dict[str, Any]] = {}  # stream_id -> stream_info
        self._manager: Optional[StreamingManager] = None
        self._token_buffers: Dict[str, List[str]] = {}  # connection_id -> tokens
        self._progress_trackers: Dict[str, ProgressTracker] = {}  # stream_id -> tracker
        self._debouncer = EventDebouncer(
            enabled=self.config.enable_event_debouncing,
            debounce_interval_ms=self.config.debounce_interval_ms,
            debounce_event_types=self.config.debounce_event_types,
        )
        self._on_connection: Optional[Callable] = None
        self._on_disconnection: Optional[Callable] = None

    def set_streaming_manager(self, manager: StreamingManager) -> None:
        """Set the underlying streaming manager."""
        self._manager = manager

    def on_connection(self, callback: Callable[[str], None]) -> None:
        """
        Set callback for connection events.

        Args:
            callback: Function(connection_id)
        """
        self._on_connection = callback

    def on_disconnection(self, callback: Callable[[str], None]) -> None:
        """
        Set callback for disconnection events.

        Args:
            callback: Function(connection_id)
        """
        self._on_disconnection = callback

    async def connect(
        self,
        websocket: Any,
        connection_id: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
            user_id: Optional user identifier
            project_id: Optional project identifier
        """
        self._connections[connection_id] = {
            "websocket": websocket,
            "user_id": user_id,
            "project_id": project_id,
            "subscriptions": set(),
            "connected_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
        }

        self._token_buffers[connection_id] = []

        # Send connection confirmation
        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.CONNECT,
                "connection_id": connection_id,
                "user_id": user_id,
                "project_id": project_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        if self._on_connection:
            self._on_connection(connection_id)

    async def disconnect(self, connection_id: str, reason: str = "client_disconnect") -> None:
        """
        Handle WebSocket disconnection.

        Args:
            connection_id: Connection identifier
            reason: Disconnection reason
        """
        if connection_id in self._connections:
            del self._connections[connection_id]

        if connection_id in self._token_buffers:
            del self._token_buffers[connection_id]

        # Clean up streams for this connection
        streams_to_remove = [
            sid for sid, stream in self._streams.items()
            if stream.get("connection_id") == connection_id
        ]
        for sid in streams_to_remove:
            del self._streams[sid]
            if sid in self._progress_trackers:
                del self._progress_trackers[sid]
            self._debouncer.clear_stream(sid)

        # Send disconnect notification
        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.DISCONNECT,
                "connection_id": connection_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        if self._on_disconnection:
            self._on_disconnection(connection_id)

    async def subscribe(
        self,
        connection_id: str,
        event_types: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        stream_id: Optional[str] = None,
    ) -> None:
        """
        Subscribe to event types.

        Args:
            connection_id: Connection identifier
            event_types: Event types to subscribe to
            categories: Event categories to subscribe to
            stream_id: Optional stream identifier for progress tracking
        """
        if connection_id not in self._connections:
            return

        subscription = self._connections[connection_id]["subscriptions"]

        if event_types:
            subscription.update(event_types)
        if categories:
            subscription.update(categories)

        if stream_id:
            self._streams[stream_id] = {
                "connection_id": connection_id,
                "started_at": datetime.utcnow().isoformat(),
            }

    async def unsubscribe(self, connection_id: str, event_types: Optional[List[str]] = None) -> None:
        """Unsubscribe from event types."""
        if connection_id in self._connections and event_types:
            subscription = self._connections[connection_id]["subscriptions"]
            for event_type in event_types:
                subscription.discard(event_type)

    async def start_stream(
        self,
        connection_id: str,
        stream_id: str,
        graph,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        event_types: Optional[List[str]] = None,
    ) -> None:
        """
        Start streaming to a connection.

        Args:
            connection_id: Connection identifier
            stream_id: Unique stream identifier
            graph: LangGraph to execute
            input_data: Input data for the graph
            config: Optional configuration
            event_types: Event types to stream
        """
        if connection_id not in self._connections:
            return

        self._streams[stream_id] = {
            "connection_id": connection_id,
            "graph": graph,
            "input_data": input_data,
            "config": config,
            "event_types": event_types,
            "started_at": datetime.utcnow().isoformat(),
        }

        # Initialize progress tracker
        self._progress_trackers[stream_id] = ProgressTracker()

        # Send stream start event
        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.STREAM_START,
                "stream_id": stream_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Start streaming in background
        asyncio.create_task(self._stream_to_connection(connection_id, stream_id))

    async def stop_stream(self, connection_id: str, stream_id: str, reason: str = "stopped") -> None:
        """
        Stop streaming to a connection.

        Args:
            connection_id: Connection identifier
            stream_id: Stream identifier
            reason: Stop reason
        """
        if stream_id in self._streams:
            del self._streams[stream_id]

        if stream_id in self._progress_trackers:
            del self._progress_trackers[stream_id]
        self._debouncer.clear_stream(stream_id)

        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.STREAM_END,
                "stream_id": stream_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def _stream_to_connection(
        self,
        connection_id: str,
        stream_id: str,
    ) -> None:
        """Stream events to a connection."""
        if stream_id not in self._streams:
            return

        stream = self._streams[stream_id]
        graph = stream["graph"]
        input_data = stream["input_data"]
        config = stream["config"]
        event_types = stream.get("event_types")
        parsed_event_types: Optional[List[EventType]] = None
        if event_types:
            parsed_event_types = []
            for event_type in event_types:
                try:
                    parsed_event_types.append(EventType(event_type))
                except ValueError:
                    logging.debug(f"Ignoring unknown event type subscription: {event_type}")

        try:
            if self.config.batch_events:
                async for batch in self._manager.stream_event_batches(
                    graph=graph,
                    input_data=input_data,
                    config=config,
                    event_types=parsed_event_types,
                    batch_size=20,
                    batch_interval_ms=self.config.batch_interval_ms,
                ):
                    await self._handle_event_batch(connection_id, stream_id, batch)
            else:
                async for event in self._manager.stream_events(
                    graph=graph,
                    input_data=input_data,
                    config=config,
                    event_types=parsed_event_types,
                ):
                    if not self._debouncer.should_emit(stream_id, event):
                        continue

                    # Format event for frontend
                    formatted = self._format_for_frontend(event, stream_id)

                    if formatted:
                        # Handle token events specially
                        if event.event_type in [EventType.LLM_STREAM, EventType.LLM_NEW_TOKEN]:
                            await self._handle_token_event(connection_id, stream_id, event)
                        # Handle progress events
                        elif event.event_type == EventType.GRAPH_CHECKPOINT:
                            await self._handle_checkpoint_event(connection_id, stream_id, event)
                        # Handle other events
                        else:
                            await self._send_message(connection_id, formatted)

        except Exception as e:
            logging.error(f"Error streaming to connection {connection_id}: {e}")
            await self._send_message(
                connection_id,
                {
                    "type": FrontendEventType.STREAM_ERROR,
                    "stream_id": stream_id,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        # Send stream end
        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.STREAM_END,
                "stream_id": stream_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        self._debouncer.clear_stream(stream_id)

    async def _handle_event_batch(
        self,
        connection_id: str,
        stream_id: str,
        batch: EventBatch,
    ) -> None:
        """Handle a batch of events and emit a compact frontend batch update."""
        batch_payload: List[Dict[str, Any]] = []

        for event in batch.events:
            if not self._debouncer.should_emit(stream_id, event):
                continue

            if event.event_type in [EventType.LLM_STREAM, EventType.LLM_NEW_TOKEN]:
                await self._handle_token_event(connection_id, stream_id, event)
                continue

            if event.event_type == EventType.GRAPH_CHECKPOINT:
                await self._handle_checkpoint_event(connection_id, stream_id, event)
                continue

            formatted = self._format_for_frontend(event, stream_id)
            if formatted:
                batch_payload.append(formatted)

        if batch_payload:
            await self._send_message(
                connection_id,
                {
                    "type": FrontendEventType.BATCH_UPDATE,
                    "stream_id": stream_id,
                    "batch_id": batch.batch_id,
                    "batch_size": len(batch_payload),
                    "events": batch_payload,
                    "timestamp": batch.end_time if self.config.include_timestamps else None,
                },
            )

    def _format_for_frontend(
        self,
        event: StreamEvent,
        stream_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Format a stream event for frontend consumption."""
        # Check if event should be sent
        subscriptions = set()
        for conn in self._connections.values():
            subscriptions.update(conn["subscriptions"])

        if subscriptions and event.event_type.value not in subscriptions:
            return None

        formatted = {
            "type": self._map_event_type(event.event_type),
            "stream_id": stream_id,
            "timestamp": event.timestamp if self.config.include_timestamps else None,
            "run_id": event.run_id if self.config.include_run_id else None,
        }

        # Add event-specific data
        if event.name:
            formatted["name"] = event.name

        if event.agent_name:
            formatted["agent_name"] = event.agent_name

        if event.node_name:
            formatted["node_name"] = event.node_name

        if event.category:
            formatted["category"] = event.category.value

        # Add event data based on type
        if event.event_type == EventType.LLM_START:
            formatted["type"] = FrontendEventType.LLM_START
        elif event.event_type == EventType.LLM_END:
            formatted["type"] = FrontendEventType.LLM_END
            if event.data:
                formatted["output"] = event.data.get("output")
        elif event.event_type == EventType.TOOL_START:
            formatted["type"] = FrontendEventType.TOOL_START
            if event.data:
                formatted["input"] = event.data.get("input")
        elif event.event_type == EventType.TOOL_END:
            formatted["type"] = FrontendEventType.TOOL_END
            if event.data:
                formatted["output"] = event.data.get("output")
                formatted["duration_ms"] = event.data.get("duration_ms")
        elif event.event_type == EventType.TOOL_ERROR:
            formatted["type"] = FrontendEventType.TOOL_ERROR
            formatted["error"] = event.error or event.data.get("error")
        elif event.event_type == EventType.AGENT_START:
            formatted["type"] = FrontendEventType.AGENT_START
        elif event.event_type == EventType.AGENT_END:
            formatted["type"] = FrontendEventType.AGENT_END
        elif event.event_type == EventType.AGENT_UPDATE:
            formatted["type"] = FrontendEventType.AGENT_UPDATE
            if event.data:
                formatted["update"] = event.data
        elif event.event_type == EventType.GRAPH_CHECKPOINT:
            formatted["type"] = FrontendEventType.CHECKPOINT
            if event.data:
                formatted["state"] = event.data.get("state")
                formatted["checkpoint_id"] = event.data.get("checkpoint_id")

        return formatted

    def _map_event_type(self, event_type: EventType) -> str:
        """Map internal event type to frontend event type."""
        mapping = {
            EventType.LLM_START: FrontendEventType.LLM_START,
            EventType.LLM_END: FrontendEventType.LLM_END,
            EventType.LLM_STREAM: FrontendEventType.LLM_TOKEN,
            EventType.LLM_NEW_TOKEN: FrontendEventType.LLM_TOKEN,
            EventType.TOOL_START: FrontendEventType.TOOL_START,
            EventType.TOOL_END: FrontendEventType.TOOL_END,
            EventType.TOOL_ERROR: FrontendEventType.TOOL_ERROR,
            EventType.AGENT_START: FrontendEventType.AGENT_START,
            EventType.AGENT_END: FrontendEventType.AGENT_END,
            EventType.AGENT_UPDATE: FrontendEventType.AGENT_UPDATE,
            EventType.GRAPH_CHECKPOINT: FrontendEventType.CHECKPOINT,
            EventType.GRAPH_START: FrontendEventType.STREAM_START,
            EventType.GRAPH_END: FrontendEventType.STREAM_END,
        }
        return mapping.get(event_type, event_type.value)

    async def _handle_token_event(
        self,
        connection_id: str,
        stream_id: str,
        event: StreamEvent,
    ) -> None:
        """Handle token events with buffering."""
        token = event.data.get("chunk", "")
        if not token:
            return

        self._token_buffers[connection_id].append(token)

        # Send tokens periodically
        tokens = self._token_buffers[connection_id]
        if len(tokens) >= 5 or event.event_type == EventType.LLM_END:
            await self._send_message(
                connection_id,
                {
                    "type": FrontendEventType.LLM_TOKEN,
                    "stream_id": stream_id,
                    "tokens": tokens,
                    "is_end": event.event_type == EventType.LLM_END,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            self._token_buffers[connection_id] = []

    async def _handle_checkpoint_event(
        self,
        connection_id: str,
        stream_id: str,
        event: StreamEvent,
    ) -> None:
        """Handle checkpoint events with progress updates."""
        if stream_id not in self._progress_trackers:
            return

        tracker = self._progress_trackers[stream_id]
        step = len(tracker.get_progress().get("checkpoints", [])) + 1

        progress_event = tracker.checkpoint({
            "checkpoint_id": event.data.get("checkpoint_id"),
            "step": step,
            "message": f"Checkpoint {step}",
        })

        if progress_event:
            await self._send_message(
                connection_id,
                {
                    "type": FrontendEventType.PROGRESS_UPDATE,
                    "stream_id": stream_id,
                    "current_step": progress_event.current_step,
                    "total_steps": progress_event.total_steps,
                    "percentage": progress_event.percentage,
                    "message": progress_event.message,
                    "details": progress_event.details,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def send_progress(
        self,
        connection_id: str,
        stream_id: str,
        current_step: int,
        total_steps: int,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a progress update to a connection.

        Args:
            connection_id: Connection identifier
            stream_id: Stream identifier
            current_step: Current step
            total_steps: Total steps
            message: Progress message
            details: Optional additional details
        """
        percentage = (current_step / total_steps) * 100 if total_steps > 0 else 0

        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.PROGRESS_UPDATE,
                "stream_id": stream_id,
                "current_step": current_step,
                "total_steps": total_steps,
                "percentage": percentage,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def send_milestone(
        self,
        connection_id: str,
        stream_id: str,
        milestone_name: str,
        description: str,
    ) -> None:
        """
        Send a milestone achievement notification.

        Args:
            connection_id: Connection identifier
            stream_id: Stream identifier
            milestone_name: Milestone name
            description: Milestone description
        """
        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.MILESTONE,
                "stream_id": stream_id,
                "name": milestone_name,
                "description": description,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def send_interrupt(
        self,
        connection_id: str,
        stream_id: str,
        interrupt_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send an interrupt notification to frontend.

        Args:
            connection_id: Connection identifier
            stream_id: Stream identifier
            interrupt_type: Type of interrupt
            message: Interrupt message
            details: Optional additional details
        """
        await self._send_message(
            connection_id,
            {
                "type": FrontendEventType.INTERRUPT,
                "stream_id": stream_id,
                "interrupt_type": interrupt_type,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def _send_message(self, connection_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a connection."""
        if connection_id not in self._connections:
            return

        try:
            websocket = self._connections[connection_id]["websocket"]
            await websocket.send_json(message)

            # Update last activity
            self._connections[connection_id]["last_activity"] = datetime.utcnow().isoformat()
        except Exception:
            logging.warning(f"Failed to send message to {connection_id}")
            await self.disconnect(connection_id, "send_failed")

    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get connection information.

        Args:
            connection_id: Connection identifier

        Returns:
            Connection info dictionary
        """
        return self._connections.get(connection_id)

    def get_active_connections(self) -> List[str]:
        """Get list of active connection IDs."""
        return list(self._connections.keys())

    def get_active_streams(self) -> List[str]:
        """Get list of active stream IDs."""
        return list(self._streams.keys())

    async def broadcast(
        self,
        message: Dict[str, Any],
        connection_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Broadcast a message to multiple connections.

        Args:
            message: Message to broadcast
            connection_ids: Specific connections to broadcast to (all if None)
        """
        targets = connection_ids or list(self._connections.keys())
        for conn_id in targets:
            await self._send_message(conn_id, message)


class WebSocketStreamManager:
    """
    WebSocket integration for streaming events to frontend.

    Features:
    - WebSocket connection management
    - Event broadcasting
    - Client subscriptions
    - Heartbeat for connection health
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        self._connections: Dict[str, Any] = {}  # connection_id -> websocket
        self._subscriptions: Dict[str, Set[str]] = {}  # connection_id -> event_types
        self._manager: Optional[StreamingManager] = None

    def set_streaming_manager(self, manager: StreamingManager) -> None:
        """Set the underlying streaming manager."""
        self._manager = manager

    async def connect(self, websocket: Any, connection_id: str) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
        """
        self._connections[connection_id] = websocket
        self._subscriptions[connection_id] = set()
        # Send connection confirmation
        await self._send_message(
            connection_id,
            {
                "type": "connection_established",
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def disconnect(self, connection_id: str) -> None:
        """Handle WebSocket disconnection."""
        if connection_id in self._connections:
            del self._connections[connection_id]
        if connection_id in self._subscriptions:
            del self._subscriptions[connection_id]

    async def subscribe(
        self,
        connection_id: str,
        event_types: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> None:
        """
        Subscribe to event types.

        Args:
            connection_id: Connection identifier
            event_types: Event types to subscribe to
            categories: Event categories to subscribe to
        """
        if connection_id not in self._subscriptions:
            self._subscriptions[connection_id] = set()

        if event_types:
            self._subscriptions[connection_id].update(event_types)
        if categories:
            self._subscriptions[connection_id].update(categories)

    async def unsubscribe(
        self, connection_id: str, event_types: Optional[List[str]] = None
    ) -> None:
        """Unsubscribe from event types."""
        if connection_id in self._subscriptions and event_types:
            for event_type in event_types:
                self._subscriptions[connection_id].discard(event_type)

    async def broadcast_event(self, event: StreamEvent) -> None:
        """
        Broadcast an event to subscribed clients.

        Args:
            event: Event to broadcast
        """
        for connection_id, connection in self._connections.items():
            subscriptions = self._subscriptions.get(connection_id, set())
            # Check if client is subscribed to this event
            should_send = (
                not subscriptions
                or event.event_type.value in subscriptions
                or event.category.value in subscriptions
            )
            if should_send:
                await self._send_message(connection_id, event.to_dict())

    async def _send_message(self, connection_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a connection."""
        if connection_id in self._connections:
            try:
                await self._connections[connection_id].send_json(message)
            except Exception:
                # Connection might be closed
                await self.disconnect(connection_id)


# Convenience functions
def create_streaming_manager() -> StreamingManager:
    """Create a new streaming manager."""
    return StreamingManager()


def create_websocket_manager() -> WebSocketStreamManager:
    """Create a new WebSocket manager."""
    return WebSocketStreamManager()


def create_frontend_websocket_bridge(
    config: Optional[FrontendStreamConfig] = None,
) -> FrontendWebSocketBridge:
    """Create a new frontend WebSocket bridge."""
    return FrontendWebSocketBridge(config)


# Event filter helper functions
def filter_llm_events(events: List[EventType]) -> List[EventType]:
    """Filter list to only LLM events."""
    llm_types = [
        EventType.LLM_START,
        EventType.LLM_END,
        EventType.LLM_STREAM,
        EventType.LLM_NEW_TOKEN,
    ]
    return [e for e in events if e in llm_types]


def filter_tool_events(events: List[EventType]) -> List[EventType]:
    """Filter list to only tool events."""
    tool_types = [EventType.TOOL_START, EventType.TOOL_END, EventType.TOOL_ERROR]
    return [e for e in events if e in tool_types]


def filter_agent_events(events: List[EventType]) -> List[EventType]:
    """Filter list to only agent events."""
    agent_types = [
        EventType.AGENT_START,
        EventType.AGENT_END,
        EventType.AGENT_UPDATE,
    ]
    return [e for e in events if e in agent_types]


class EventBatchAggregator:
    """
    Aggregate stream events into configurable batches.

    Flush conditions:
    - Batch size reaches `max_batch_size`
    - Batch age reaches `max_wait_ms` when a new event arrives
    - Explicit flush at stream end
    """

    def __init__(self, max_batch_size: int = 20, max_wait_ms: int = 50):
        self.max_batch_size = max(1, max_batch_size)
        self.max_wait_ms = max(1, max_wait_ms)
        self._events: List[StreamEvent] = []
        self._batch_start: Optional[datetime] = None
        self._batch_counter = 0

    def add_event(self, event: StreamEvent) -> Optional[EventBatch]:
        """Add an event and return a batch if flush conditions are met."""
        now = datetime.utcnow()

        if not self._events:
            self._batch_start = now

        self._events.append(event)

        elapsed_ms = 0.0
        if self._batch_start:
            elapsed_ms = (now - self._batch_start).total_seconds() * 1000

        if len(self._events) >= self.max_batch_size or elapsed_ms >= self.max_wait_ms:
            return self._flush(now)

        return None

    def flush(self) -> Optional[EventBatch]:
        """Force flush current batch, if any."""
        if not self._events:
            return None
        return self._flush(datetime.utcnow())

    def _flush(self, end_time: datetime) -> EventBatch:
        """Internal flush implementation."""
        self._batch_counter += 1
        start_time = self._batch_start or end_time
        events = self._events.copy()

        self._events.clear()
        self._batch_start = None

        categories = sorted({event.category.value for event in events if event.category})
        event_types = sorted({event.event_type.value for event in events if event.event_type})

        return EventBatch(
            batch_id=f"batch_{self._batch_counter}",
            events=events,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            size=len(events),
            categories=categories,
            event_types=event_types,
        )


# ============================================================================
# Event Filtering - TICKET-243: Chat Model Stream Event Filters
# ============================================================================


@dataclass
class EventFilter:
    """
    Composable event filter for stream events.
    
    Supports multiple filter criteria that can be combined:
    - Event types (llm_start, llm_end, etc.)
    - Event categories (llm, tool, agent, graph, custom)
    - Custom predicates based on event attributes
    - Tags and metadata filtering
    
    Examples:
        # Filter only LLM streaming events
        filter = EventFilter(event_types=[EventType.LLM_STREAM])
        
        # Filter LLM events for specific model
        filter = EventFilter(
            categories=[StreamEventCategory.LLM],
            metadata_keys={"model_name": ["gpt-4", "claude-3"]}
        )
        
        # Combine filters
        combined = filter1 & filter2  # AND combination
        combined = filter1 | filter2  # OR combination
    """

    event_types: Optional[List[EventType]] = None
    categories: Optional[List[StreamEventCategory]] = None
    tags: Optional[List[str]] = None
    exclude_tags: Optional[List[str]] = None
    metadata_keys: Optional[Dict[str, List[str]]] = None
    exclude_metadata_keys: Optional[Dict[str, List[str]]] = None
    custom_predicate: Optional[Callable[[StreamEvent], bool]] = None
    name_patterns: Optional[List[str]] = None
    node_names: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize filter sets for efficient lookup."""
        self._event_type_set = set(self.event_types) if self.event_types else None
        self._category_set = set(self.categories) if self.categories else None
        self._tag_set = set(self.tags) if self.tags else None
        self._exclude_tag_set = set(self.exclude_tags) if self.exclude_tags else None
        self._node_name_set = set(self.node_names) if self.node_names else None
        
        # Compile name patterns for regex matching
        self._name_patterns = None
        if self.name_patterns:
            try:
                self._name_patterns = [re.compile(p) for p in self.name_patterns]
            except re.error as e:
                logging.warning(f"Invalid name pattern: {e}")
                self._name_patterns = None

    def matches(self, event: StreamEvent) -> bool:
        """
        Check if an event matches this filter.
        
        Args:
            event: StreamEvent to check
            
        Returns:
            True if event matches all filter criteria
        """
        # Check event type
        if self._event_type_set is not None:
            if event.event_type not in self._event_type_set:
                return False
        
        # Check category
        if self._category_set is not None:
            if event.category not in self._category_set:
                return False
        
        # Check tags (event must have ALL specified tags)
        if self._tag_set is not None:
            if not self._tag_set.issubset(set(event.tags)):
                return False
        
        # Check exclude tags (event must NOT have any excluded tags)
        if self._exclude_tag_set is not None:
            if self._exclude_tag_set.intersection(set(event.tags)):
                return False
        
        # Check metadata keys
        if self.metadata_keys is not None:
            for key, expected_values in self.metadata_keys.items():
                actual_value = event.metadata.get(key)
                if actual_value not in expected_values:
                    return False
        
        # Check exclude metadata keys
        if self.exclude_metadata_keys is not None:
            for key, excluded_values in self.exclude_metadata_keys.items():
                actual_value = event.metadata.get(key)
                if actual_value in excluded_values:
                    return False
        
        # Check node names
        if self._node_name_set is not None:
            if event.node_name not in self._node_name_set:
                return False
        
        # Check name patterns
        if self._name_patterns is not None and event.name:
            if not any(pattern.match(event.name) for pattern in self._name_patterns):
                return False
        
        # Check custom predicate
        if self.custom_predicate is not None:
            if not self.custom_predicate(event):
                return False
        
        return True

    def __and__(self, other: "EventFilter") -> "EventFilter":
        """AND combination of two filters."""
        return EventFilter(
            event_types=self.event_types or other.event_types,
            categories=self.categories or other.categories,
            tags=list(set(self.tags or []) | set(other.tags or [])),
            exclude_tags=list(set(self.exclude_tags or []) | set(other.exclude_tags or [])),
            metadata_keys={**(self.metadata_keys or {}), **(other.metadata_keys or {})},
            exclude_metadata_keys={**(self.exclude_metadata_keys or {}), **(other.exclude_metadata_keys or {})},
            custom_predicate=self._combine_predicates(other, "and"),
            name_patterns=(self.name_patterns or []) + (other.name_patterns or []),
            node_names=(self.node_names or []) + (other.node_names or []),
        )

    def __or__(self, other: "EventFilter") -> "EventFilter":
        """OR combination of two filters."""
        return EventFilter(
            event_types=(self.event_types or []) + (other.event_types or []),
            categories=(self.categories or []) + (other.categories or []),
            custom_predicate=self._combine_predicates(other, "or"),
        )

    def _combine_predicates(
        self, other: "EventFilter", mode: str = "and"
    ) -> Optional[Callable[[StreamEvent], bool]]:
        """Combine custom predicates from two filters."""
        self_pred = self.custom_predicate
        other_pred = other.custom_predicate
        
        if self_pred is None and other_pred is None:
            return None
        elif self_pred is None:
            return other_pred
        elif other_pred is None:
            return self_pred
        
        if mode == "and":
            return lambda e: self_pred(e) and other_pred(e)
        else:
            return lambda e: self_pred(e) or other_pred(e)

    def invert(self) -> "EventFilter":
        """Return an inverted filter (negates all conditions)."""
        # Create a wrapper predicate that inverts the result
        original_predicate = self.custom_predicate
        
        def inverted_predicate(event: StreamEvent) -> bool:
            # For the inverted filter, we need to check if the original would NOT match
            # This is complex, so we create a new filter with negated logic
            return not self._matches_internal(event)
        
        return EventFilter(
            custom_predicate=inverted_predicate,
        )

    def _matches_internal(self, event: StreamEvent) -> bool:
        """Internal matching logic (for use in invert())."""
        # Simplified check for internal use
        if self._event_type_set is not None and event.event_type not in self._event_type_set:
            return False
        if self._category_set is not None and event.category not in self._category_set:
            return False
        if self._tag_set is not None and not self._tag_set.issubset(set(event.tags)):
            return False
        if self._node_name_set is not None and event.node_name not in self._node_name_set:
            return False
        if self.custom_predicate is not None and not self.custom_predicate(event):
            return False
        return True


class ChatModelEventFilter:
    """
    Specialized filter for LLM/Chat Model stream events.
    
    Provides convenient methods for filtering LLM-specific events:
    - Streaming events (token-by-token output)
    - Start/End events (lifecycle events)
    - Model-specific filtering (by model name, provider)
    - Token count and timing filters
    - Output length filters
    
    Examples:
        # Only streaming events
        filter = ChatModelEventFilter().streaming_only()
        
        # Only complete generations
        filter = ChatModelEventFilter().completion_only()
        
        # Specific model
        filter = ChatModelEventFilter().by_model("gpt-4")
        
        # Complex filter
        filter = (
            ChatModelEventFilter()
            .streaming_only()
            .with_min_tokens(10)
            .exclude_internal_tags()
        )
    """

    def __init__(self):
        """Initialize the LLM event filter."""
        self._filters: List[Callable[[StreamEvent], bool]] = []
        self._base_event_types = [
            EventType.LLM_START,
            EventType.LLM_END,
            EventType.LLM_STREAM,
            EventType.LLM_NEW_TOKEN,
        ]

    def streaming_only(self) -> "ChatModelEventFilter":
        """Filter to only include streaming events (token output)."""
        self._filters.append(
            lambda e: e.event_type in [EventType.LLM_STREAM, EventType.LLM_NEW_TOKEN]
        )
        return self

    def completion_only(self) -> "ChatModelEventFilter":
        """Filter to only include completion events."""
        self._filters.append(lambda e: e.event_type == EventType.LLM_END)
        return self

    def start_only(self) -> "ChatModelEventFilter":
        """Filter to only include start events."""
        self._filters.append(lambda e: e.event_type == EventType.LLM_START)
        return self

    def lifecycle_only(self) -> "ChatModelEventFilter":
        """Filter to only include lifecycle events (start/end)."""
        self._filters.append(
            lambda e: e.event_type in [EventType.LLM_START, EventType.LLM_END]
        )
        return self

    def by_model(self, model_name: str) -> "ChatModelEventFilter":
        """Filter to events from a specific model."""
        self._filters.append(
            lambda e: e.metadata.get("model_name") == model_name
        )
        return self

    def by_model_pattern(self, pattern: str) -> "ChatModelEventFilter":
        """Filter to events from models matching a pattern."""
        try:
            regex = re.compile(pattern)
            self._filters.append(
                lambda e: (
                    e.metadata.get("model_name") and
                    regex.match(e.metadata.get("model_name"))
                )
            )
        except re.error:
            logging.warning(f"Invalid model pattern: {pattern}")
        return self

    def by_provider(self, provider: str) -> "ChatModelEventFilter":
        """Filter to events from a specific provider."""
        self._filters.append(
            lambda e: e.metadata.get("provider") == provider
        )
        return self

    def with_tag(self, tag: str) -> "ChatModelEventFilter":
        """Filter to events containing a specific tag."""
        self._filters.append(lambda e: tag in e.tags)
        return self

    def with_any_tag(self, tags: List[str]) -> "ChatModelEventFilter":
        """Filter to events containing any of the specified tags."""
        tag_set = set(tags)
        self._filters.append(lambda e: bool(tag_set.intersection(e.tags)))
        return self

    def exclude_internal_tags(self) -> "ChatModelEventFilter":
        """Exclude events with internal/debug tags."""
        self._filters.append(
            lambda e: not any(t.startswith("_") or "debug" in t for t in e.tags)
        )
        return self

    def by_node_name(self, node_name: str) -> "ChatModelEventFilter":
        """Filter to events from a specific node."""
        self._filters.append(lambda e: e.node_name == node_name)
        return self

    def by_node_pattern(self, pattern: str) -> "ChatModelEventFilter":
        """Filter to events from nodes matching a pattern."""
        try:
            regex = re.compile(pattern)
            self._filters.append(
                lambda e: e.node_name and regex.match(e.node_name)
            )
        except re.error:
            logging.warning(f"Invalid node pattern: {pattern}")
        return self

    def by_agent_name(self, agent_name: str) -> "ChatModelEventFilter":
        """Filter to events from a specific agent."""
        self._filters.append(lambda e: e.agent_name == agent_name)
        return self

    def with_min_tokens(self, min_tokens: int) -> "ChatModelEventFilter":
        """Filter to events with minimum token count (for streaming)."""
        self._filters.append(
            lambda e: e.metadata.get("token_count", 0) >= min_tokens
        )
        return self

    def with_max_tokens(self, max_tokens: int) -> "ChatModelEventFilter":
        """Filter to events with maximum token count."""
        self._filters.append(
            lambda e: e.metadata.get("token_count", float("inf")) <= max_tokens
        )
        return self

    def with_duration_range(
        self, min_ms: Optional[float] = None, max_ms: Optional[float] = None
    ) -> "ChatModelEventFilter":
        """Filter to events with duration in range (in milliseconds)."""
        def check_duration(e: StreamEvent) -> bool:
            duration = e.metadata.get("duration_ms", 0)
            if min_ms is not None and duration < min_ms:
                return False
            if max_ms is not None and duration > max_ms:
                return False
            return True
        
        self._filters.append(check_duration)
        return self

    def with_system_prompt(self) -> "ChatModelEventFilter":
        """Filter to events where system prompt was used."""
        self._filters.append(
            lambda e: e.metadata.get("has_system_prompt", False)
        )
        return self

    def with_custom_data(self, key: str) -> "ChatModelEventFilter":
        """Filter to events containing specific data key."""
        self._filters.append(lambda e: key in e.data)
        return self

    def custom(self, predicate: Callable[[StreamEvent], bool]) -> "ChatModelEventFilter":
        """Add a custom filter predicate."""
        self._filters.append(predicate)
        return self

    def build(self) -> EventFilter:
        """
        Build an EventFilter from the accumulated criteria.
        
        Returns:
            EventFilter that matches all accumulated criteria
        """
        # Combine all predicates into a single filter
        def combined_predicate(event: StreamEvent) -> bool:
            # First check it's an LLM event
            if event.event_type not in self._base_event_types:
                return False
            # Then apply all accumulated filters
            for filter_func in self._filters:
                if not filter_func(event):
                    return False
            return True

        return EventFilter(custom_predicate=combined_predicate)

    def matches(self, event: StreamEvent) -> bool:
        """Check if an event matches this filter."""
        # First check it's an LLM event
        if event.event_type not in self._base_event_types:
            return False
        # Then apply all accumulated filters
        for filter_func in self._filters:
            if not filter_func(event):
                return False
        return True


class ToolEventFilter:
    """
    Specialized filter for tool execution events.

    Provides convenient methods for filtering tool-specific events:
    - Lifecycle events (start/end/error)
    - Tool name, node, and agent filters
    - Metadata-based timing and tags
    - Input/output payload key checks
    """

    def __init__(self):
        """Initialize the tool event filter."""
        self._filters: List[Callable[[StreamEvent], bool]] = []
        self._base_event_types = [
            EventType.TOOL_START,
            EventType.TOOL_END,
            EventType.TOOL_ERROR,
        ]

    def execution_only(self) -> "ToolEventFilter":
        """Filter to include only successful execution events."""
        self._filters.append(
            lambda e: e.event_type in [EventType.TOOL_START, EventType.TOOL_END]
        )
        return self

    def lifecycle_only(self) -> "ToolEventFilter":
        """Filter to include tool lifecycle events (start/end/error)."""
        self._filters.append(lambda e: e.event_type in self._base_event_types)
        return self

    def start_only(self) -> "ToolEventFilter":
        """Filter to include only tool start events."""
        self._filters.append(lambda e: e.event_type == EventType.TOOL_START)
        return self

    def completion_only(self) -> "ToolEventFilter":
        """Filter to include only tool completion events."""
        self._filters.append(lambda e: e.event_type == EventType.TOOL_END)
        return self

    def error_only(self) -> "ToolEventFilter":
        """Filter to include only tool error events."""
        self._filters.append(lambda e: e.event_type == EventType.TOOL_ERROR)
        return self

    def by_tool_name(self, tool_name: str) -> "ToolEventFilter":
        """Filter to events from a specific tool."""
        self._filters.append(lambda e: e.name == tool_name)
        return self

    def by_tool_name_pattern(self, pattern: str) -> "ToolEventFilter":
        """Filter to events from tool names matching a regex pattern."""
        try:
            regex = re.compile(pattern)
            self._filters.append(lambda e: bool(e.name and regex.match(e.name)))
        except re.error:
            logging.warning(f"Invalid tool name pattern: {pattern}")
        return self

    def by_agent_name(self, agent_name: str) -> "ToolEventFilter":
        """Filter to events from a specific agent."""
        self._filters.append(lambda e: e.agent_name == agent_name)
        return self

    def by_node_name(self, node_name: str) -> "ToolEventFilter":
        """Filter to events from a specific node."""
        self._filters.append(lambda e: e.node_name == node_name)
        return self

    def with_tag(self, tag: str) -> "ToolEventFilter":
        """Filter to events containing a specific tag."""
        self._filters.append(lambda e: tag in e.tags)
        return self

    def with_any_tag(self, tags: List[str]) -> "ToolEventFilter":
        """Filter to events containing any of the specified tags."""
        tag_set = set(tags)
        self._filters.append(lambda e: bool(tag_set.intersection(e.tags)))
        return self

    def exclude_internal_tags(self) -> "ToolEventFilter":
        """Exclude events with internal/debug tags."""
        self._filters.append(
            lambda e: not any(t.startswith("_") or "debug" in t for t in e.tags)
        )
        return self

    def with_duration_range(
        self, min_ms: Optional[float] = None, max_ms: Optional[float] = None
    ) -> "ToolEventFilter":
        """Filter to events with duration in range (in milliseconds)."""

        def check_duration(e: StreamEvent) -> bool:
            duration = e.data.get("duration_ms", e.metadata.get("duration_ms", 0))
            if min_ms is not None and duration < min_ms:
                return False
            if max_ms is not None and duration > max_ms:
                return False
            return True

        self._filters.append(check_duration)
        return self

    def with_input_key(self, key: str) -> "ToolEventFilter":
        """Filter to tool start events containing an input key."""
        self._filters.append(
            lambda e: (
                e.event_type != EventType.TOOL_START
                or key in (e.data.get("input", {}) or {})
            )
        )
        return self

    def with_output_key(self, key: str) -> "ToolEventFilter":
        """Filter to tool end events containing an output key."""
        self._filters.append(
            lambda e: (
                e.event_type != EventType.TOOL_END
                or key in (e.data.get("output", {}) or {})
            )
        )
        return self

    def custom(self, predicate: Callable[[StreamEvent], bool]) -> "ToolEventFilter":
        """Add a custom filter predicate."""
        self._filters.append(predicate)
        return self

    def build(self) -> EventFilter:
        """
        Build an EventFilter from the accumulated criteria.

        Returns:
            EventFilter that matches all accumulated criteria
        """

        def combined_predicate(event: StreamEvent) -> bool:
            if event.event_type not in self._base_event_types:
                return False
            for filter_func in self._filters:
                if not filter_func(event):
                    return False
            return True

        return EventFilter(custom_predicate=combined_predicate)

    def matches(self, event: StreamEvent) -> bool:
        """Check if an event matches this filter."""
        if event.event_type not in self._base_event_types:
            return False
        for filter_func in self._filters:
            if not filter_func(event):
                return False
        return True


class AgentEventFilter:
    """
    Specialized filter for custom agent events.

    Provides convenient methods for filtering agent-specific events:
    - Lifecycle events (start/end/update)
    - Agent and node scoping
    - Tag and metadata filters
    - Update payload key checks for custom event content
    """

    def __init__(self):
        """Initialize the agent event filter."""
        self._filters: List[Callable[[StreamEvent], bool]] = []
        self._base_event_types = [
            EventType.AGENT_START,
            EventType.AGENT_END,
            EventType.AGENT_UPDATE,
        ]

    def lifecycle_only(self) -> "AgentEventFilter":
        """Filter to include agent lifecycle events (start/end)."""
        self._filters.append(
            lambda e: e.event_type in [EventType.AGENT_START, EventType.AGENT_END]
        )
        return self

    def update_only(self) -> "AgentEventFilter":
        """Filter to include only agent update events."""
        self._filters.append(lambda e: e.event_type == EventType.AGENT_UPDATE)
        return self

    def start_only(self) -> "AgentEventFilter":
        """Filter to include only agent start events."""
        self._filters.append(lambda e: e.event_type == EventType.AGENT_START)
        return self

    def end_only(self) -> "AgentEventFilter":
        """Filter to include only agent end events."""
        self._filters.append(lambda e: e.event_type == EventType.AGENT_END)
        return self

    def all_agent_events(self) -> "AgentEventFilter":
        """Filter to include all agent event types."""
        self._filters.append(lambda e: e.event_type in self._base_event_types)
        return self

    def by_agent_name(self, agent_name: str) -> "AgentEventFilter":
        """Filter to events from a specific agent."""
        self._filters.append(lambda e: e.agent_name == agent_name)
        return self

    def by_node_name(self, node_name: str) -> "AgentEventFilter":
        """Filter to events from a specific node."""
        self._filters.append(lambda e: e.node_name == node_name)
        return self

    def with_tag(self, tag: str) -> "AgentEventFilter":
        """Filter to events containing a specific tag."""
        self._filters.append(lambda e: tag in e.tags)
        return self

    def with_any_tag(self, tags: List[str]) -> "AgentEventFilter":
        """Filter to events containing any of the specified tags."""
        tag_set = set(tags)
        self._filters.append(lambda e: bool(tag_set.intersection(e.tags)))
        return self

    def exclude_internal_tags(self) -> "AgentEventFilter":
        """Exclude events with internal/debug tags."""
        self._filters.append(
            lambda e: not any(t.startswith("_") or "debug" in t for t in e.tags)
        )
        return self

    def with_metadata(self, key: str, value: Any) -> "AgentEventFilter":
        """Filter to events where metadata key equals value."""
        self._filters.append(lambda e: e.metadata.get(key) == value)
        return self

    def with_update_key(self, key: str) -> "AgentEventFilter":
        """Filter to agent update events containing a specific data key."""
        self._filters.append(
            lambda e: (
                e.event_type != EventType.AGENT_UPDATE
                or key in (e.data or {})
            )
        )
        return self

    def with_name_pattern(self, pattern: str) -> "AgentEventFilter":
        """Filter to events with names matching a regex pattern."""
        try:
            regex = re.compile(pattern)
            self._filters.append(lambda e: bool(e.name and regex.match(e.name)))
        except re.error:
            logging.warning(f"Invalid agent event name pattern: {pattern}")
        return self

    def custom(self, predicate: Callable[[StreamEvent], bool]) -> "AgentEventFilter":
        """Add a custom filter predicate."""
        self._filters.append(predicate)
        return self

    def build(self) -> EventFilter:
        """
        Build an EventFilter from the accumulated criteria.

        Returns:
            EventFilter that matches all accumulated criteria
        """

        def combined_predicate(event: StreamEvent) -> bool:
            if event.event_type not in self._base_event_types:
                return False
            for filter_func in self._filters:
                if not filter_func(event):
                    return False
            return True

        return EventFilter(custom_predicate=combined_predicate)

    def matches(self, event: StreamEvent) -> bool:
        """Check if an event matches this filter."""
        if event.event_type not in self._base_event_types:
            return False
        for filter_func in self._filters:
            if not filter_func(event):
                return False
        return True


class EventFilterPipeline:
    """
    Pipeline for filtering events through multiple stages.
    
    Allows chaining multiple filters with different purposes:
    1. Pre-filtering (coarse-grained)
    2. Category filtering
    3. Detail filtering (fine-grained)
    4. Transformation
    
    Examples:
        pipeline = (
            EventFilterPipeline()
            .add_filter(EventFilter(categories=[StreamEventCategory.LLM]))
            .add_filter(ChatModelEventFilter().streaming_only().build())
        )
        
        async for event in pipeline.filter_events(stream):
            process(event)
    """

    def __init__(self):
        """Initialize the filter pipeline."""
        self._filters: List[EventFilter] = []
        self._transformers: List[Callable[[StreamEvent], Optional[StreamEvent]]] = []

    def add_filter(self, filter: EventFilter) -> "EventFilterPipeline":
        """Add a filter to the pipeline."""
        self._filters.append(filter)
        return self

    def add_transformer(
        self, transformer: Callable[[StreamEvent], Optional[StreamEvent]]
    ) -> "EventFilterPipeline":
        """Add a transformer to the pipeline."""
        self._transformers.append(transformer)
        return self

    async def filter_events(
        self, event_stream: AsyncGenerator[StreamEvent, None]
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Filter events through the pipeline.
        
        Args:
            event_stream: Input event stream
            
        Yields:
            Filtered and transformed events
        """
        async for event in event_stream:
            # Apply all filters
            passes_all = True
            for filter in self._filters:
                if not filter.matches(event):
                    passes_all = False
                    break
            
            if not passes_all:
                continue
            
            # Apply all transformers
            transformed = event
            for transformer in self._transformers:
                transformed = transformer(transformed)
                if transformed is None:
                    break
            
            if transformed is not None:
                yield transformed

    def filter_list(self, events: List[StreamEvent]) -> List[StreamEvent]:
        """Filter a list of events through the pipeline."""
        result = []
        for event in events:
            # Apply all filters
            passes_all = True
            for filter in self._filters:
                if not filter.matches(event):
                    passes_all = False
                    break
            
            if passes_all:
                result.append(event)
        return result


# Factory functions for common LLM event filters

def create_llm_streaming_filter() -> EventFilter:
    """
    Create a filter for LLM streaming events (token-by-token output).
    
    Returns:
        EventFilter matching LLM stream events
    """
    return EventFilter(
        event_types=[EventType.LLM_STREAM, EventType.LLM_NEW_TOKEN],
        categories=[StreamEventCategory.LLM],
    )


def create_llm_completion_filter() -> EventFilter:
    """
    Create a filter for LLM completion events.
    
    Returns:
        EventFilter matching LLM end events
    """
    return EventFilter(
        event_types=[EventType.LLM_END],
        categories=[StreamEventCategory.LLM],
    )


def create_llm_lifecycle_filter() -> EventFilter:
    """
    Create a filter for LLM lifecycle events (start/end).
    
    Returns:
        EventFilter matching LLM start and end events
    """
    return EventFilter(
        event_types=[EventType.LLM_START, EventType.LLM_END],
        categories=[StreamEventCategory.LLM],
    )


def create_llm_all_filter() -> EventFilter:
    """
    Create a filter for all LLM events.
    
    Returns:
        EventFilter matching all LLM events
    """
    return EventFilter(
        event_types=[
            EventType.LLM_START,
            EventType.LLM_END,
            EventType.LLM_STREAM,
            EventType.LLM_NEW_TOKEN,
        ],
        categories=[StreamEventCategory.LLM],
    )


def create_tool_execution_filter() -> EventFilter:
    """
    Create a filter for tool execution events.

    Returns:
        EventFilter matching tool start and end events
    """
    return EventFilter(
        event_types=[EventType.TOOL_START, EventType.TOOL_END],
        categories=[StreamEventCategory.TOOL],
    )


def create_tool_error_filter() -> EventFilter:
    """
    Create a filter for tool error events.

    Returns:
        EventFilter matching tool error events
    """
    return EventFilter(
        event_types=[EventType.TOOL_ERROR],
        categories=[StreamEventCategory.TOOL],
    )


def create_tool_all_filter() -> EventFilter:
    """
    Create a filter for all tool events.

    Returns:
        EventFilter matching all tool events
    """
    return EventFilter(
        event_types=[EventType.TOOL_START, EventType.TOOL_END, EventType.TOOL_ERROR],
        categories=[StreamEventCategory.TOOL],
    )


def create_agent_lifecycle_filter() -> EventFilter:
    """
    Create a filter for agent lifecycle events (start/end).

    Returns:
        EventFilter matching agent start and end events
    """
    return EventFilter(
        event_types=[EventType.AGENT_START, EventType.AGENT_END],
        categories=[StreamEventCategory.AGENT],
    )


def create_agent_update_filter() -> EventFilter:
    """
    Create a filter for custom agent update events.

    Returns:
        EventFilter matching agent update events
    """
    return EventFilter(
        event_types=[EventType.AGENT_UPDATE],
        categories=[StreamEventCategory.AGENT],
    )


def create_agent_all_filter() -> EventFilter:
    """
    Create a filter for all agent events.

    Returns:
        EventFilter matching all agent events
    """
    return EventFilter(
        event_types=[EventType.AGENT_START, EventType.AGENT_END, EventType.AGENT_UPDATE],
        categories=[StreamEventCategory.AGENT],
    )


def create_fast_llm_filter(min_tokens_per_second: float = 10.0) -> EventFilter:
    """
    Create a filter for fast LLM responses (for real-time streaming).
    
    Args:
        min_tokens_per_second: Minimum tokens per second to consider "fast"
        
    Returns:
        EventFilter matching fast LLM streaming events
    """
    def fast_predicate(event: StreamEvent) -> bool:
        duration_ms = event.metadata.get("duration_ms", 0)
        token_count = event.metadata.get("token_count", 0)
        
        if duration_ms <= 0 or token_count <= 0:
            return True  # Can't calculate, include by default
        
        tokens_per_second = (token_count / duration_ms) * 1000
        return tokens_per_second >= min_tokens_per_second
    
    return EventFilter(
        event_types=[EventType.LLM_STREAM, EventType.LLM_NEW_TOKEN],
        categories=[StreamEventCategory.LLM],
        custom_predicate=fast_predicate,
    )


def create_quality_llm_filter(
    min_token_count: int = 50,
    max_duration_ms: Optional[float] = None,
) -> EventFilter:
    """
    Create a filter for quality LLM responses.
    
    Args:
        min_token_count: Minimum tokens for quality response
        max_duration_ms: Maximum duration for quality response (None = no limit)
        
    Returns:
        EventFilter matching quality LLM events
    """
    def quality_predicate(event: StreamEvent) -> bool:
        token_count = event.metadata.get("token_count", 0)
        if token_count < min_token_count:
            return False
        
        if max_duration_ms is not None:
            duration_ms = event.metadata.get("duration_ms", 0)
            if duration_ms > max_duration_ms:
                return False
        
        return True
    
    return EventFilter(
        event_types=[EventType.LLM_END],
        categories=[StreamEventCategory.LLM],
        custom_predicate=quality_predicate,
    )


# Convenience function for quick filtering

def filter_events(
    events: List[StreamEvent],
    event_types: Optional[List[EventType]] = None,
    categories: Optional[List[StreamEventCategory]] = None,
    tags: Optional[List[str]] = None,
    custom_predicate: Optional[Callable[[StreamEvent], bool]] = None,
) -> List[StreamEvent]:
    """
    Quick filter function for filtering a list of events.
    
    Args:
        events: List of events to filter
        event_types: Event types to include
        categories: Event categories to include
        tags: Tags to include
        custom_predicate: Custom filter function
        
    Returns:
        Filtered list of events
    """
    result = events
    
    if event_types:
        result = [e for e in result if e.event_type in event_types]
    
    if categories:
        result = [e for e in result if e.category in categories]
    
    if tags:
        tag_set = set(tags)
        result = [e for e in result if tag_set.issubset(set(e.tags))]
    
    if custom_predicate:
        result = [e for e in result if custom_predicate(e)]
    
    return result


# Example usage
async def example_streaming():
    """Example of using the streaming system."""
    from langgraph.graph import StateGraph

    # Create a simple graph
    def create_example_graph():
        builder = StateGraph(dict)
        builder.add_node("start", lambda x: {"result": "started"})
        builder.add_node("process", lambda x: {"result": "processed"})
        builder.add_node("end", lambda x: {"result": "ended"})
        builder.add_edge("start", "process")
        builder.add_edge("process", "end")
        return builder.compile()

    # Create streaming manager
    manager = create_streaming_manager()

    # Create event handler
    handler = StreamHandler()

    async def print_event(event: StreamEvent):
        print(f"Event: {event.event_type.value} - {event.name}")

    handler.register_handler(category=StreamEventCategory.LLM, handler=print_event)
    handler.register_handler(category=StreamEventCategory.TOOL, handler=print_event)
    manager.add_handler(handler)

    # Stream events from graph
    graph = create_example_graph()
    async for event in manager.stream_events(graph, {"input": "test"}):
        print(f"Received: {event.event_type.value}")
