"""
Frontend interrupt response handling for human-in-the-loop workflows.

This module provides:
1. Interrupt state management for frontend
2. Response submission handling
3. Timeout countdown and auto-submit
4. Interrupt UI state machine
"""

from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
from datetime import datetime, timedelta
from uuid import uuid4
from pydantic import BaseModel, Field
from dataclasses import dataclass, field

from .human_in_the_loop import (
    HumanInterruptConfig,
    InterruptResponse,
    InterruptStatus,
    InterruptType,
    InterruptPriority,
)


class InterruptUIState(str, Enum):
    """States for interrupt UI display."""
    IDLE = "idle"
    LOADING = "loading"
    PENDING = "pending"
    RESPONDING = "responding"
    SUBMITTED = "submitted"
    ERROR = "error"
    TIMEOUT = "timeout"


class ResponseAction(str, Enum):
    """Actions a user can take on an interrupt."""
    APPROVE = "approve"
    REJECT = "reject"
    IGNORE = "ignore"
    CUSTOM = "custom"
    DEFER = "defer"


@dataclass
class FrontendInterrupt:
    """Frontend representation of an interrupt."""
    interrupt_id: str
    interrupt_type: str
    title: str
    description: str
    priority: str
    options: List[str] = field(default_factory=list)
    thread_id: str
    project_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    timeout_seconds: Optional[int] = None
    expires_at: Optional[datetime] = None
    allow_ignore: bool = True
    allow_response: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    ui_state: InterruptUIState = InterruptUIState.IDLE
    error_message: Optional[str] = None


class FrontendInterruptResponse(BaseModel):
    """Response submitted from frontend."""
    response_id: str = Field(default_factory=lambda: str(uuid4()))
    interrupt_id: str
    action: ResponseAction
    response: Optional[str] = None
    comment: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FrontendInterruptHandler:
    """
    Handles interrupt state and responses on the frontend.
    
    Provides:
    1. Interrupt state management
    2. Response validation and submission
    3. Timeout tracking
    4. UI state machine
    """
    
    def __init__(self):
        """Initialize the frontend interrupt handler."""
        self._current_interrupt: Optional[FrontendInterrupt] = None
        self._interrupt_history: List[FrontendInterrupt] = []
        self._response_callbacks: Dict[str, Callable] = {}
        self._state_callbacks: List[Callable] = []
        self._timeout_callback: Optional[Callable] = None
        self._countdown_task = None
    
    @property
    def current_interrupt(self) -> Optional[FrontendInterrupt]:
        """Get the current interrupt being displayed."""
        return self._current_interrupt
    
    @property
    def interrupt_history(self) -> List[FrontendInterrupt]:
        """Get list of past interrupts."""
        return self._interrupt_history.copy()
    
    def register_response_callback(
        self,
        interrupt_id: str,
        callback: Callable[[FrontendInterruptResponse], None],
    ) -> None:
        """Register a callback for when a response is submitted."""
        self._response_callbacks[interrupt_id] = callback
    
    def unregister_response_callback(self, interrupt_id: str) -> None:
        """Unregister a response callback."""
        self._response_callbacks.pop(interrupt_id, None)
    
    def register_state_callback(
        self,
        callback: Callable[[InterruptUIState, Optional[FrontendInterrupt]], None],
    ) -> None:
        """Register a callback for UI state changes."""
        self._state_callbacks.append(callback)
    
    def register_timeout_callback(
        self,
        callback: Callable[[], None],
    ) -> None:
        """Register a callback for when interrupt times out."""
        self._timeout_callback = callback
    
    def _notify_state_change(
        self,
        state: InterruptUIState,
        interrupt: Optional[FrontendInterrupt] = None,
    ) -> None:
        """Notify all state callbacks of a change."""
        for callback in self._state_callbacks:
            try:
                callback(state, interrupt)
            except Exception:
                pass
    
    def load_interrupt(
        self,
        interrupt_data: Dict[str, Any],
        thread_id: str,
    ) -> FrontendInterrupt:
        """
        Load an interrupt from server data.
        
        Args:
            interrupt_data: Interrupt data from server
            thread_id: Thread ID for context
        
        Returns:
            FrontendInterrupt instance
        """
        # Calculate expiry time
        timeout_seconds = interrupt_data.get("timeout_seconds")
        expires_at = None
        if timeout_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        
        interrupt = FrontendInterrupt(
            interrupt_id=interrupt_data.get("interrupt_id", str(uuid4())),
            interrupt_type=interrupt_data.get("interrupt_type", "custom"),
            title=interrupt_data.get("title", "Interrupt"),
            description=interrupt_data.get("description", ""),
            priority=interrupt_data.get("priority", "medium"),
            options=interrupt_data.get("options", []),
            thread_id=thread_id,
            project_id=interrupt_data.get("project_id"),
            timeout_seconds=timeout_seconds,
            expires_at=expires_at,
            allow_ignore=interrupt_data.get("allow_ignore", True),
            allow_response=interrupt_data.get("allow_response", True),
            metadata=interrupt_data.get("metadata", {}),
            ui_state=InterruptUIState.PENDING,
        )
        
        self._current_interrupt = interrupt
        self._notify_state_change(InterruptUIState.PENDING, interrupt)
        
        return interrupt
    
    def load_interrupt_from_config(
        self,
        config: HumanInterruptConfig,
        thread_id: str,
    ) -> FrontendInterrupt:
        """Load interrupt from HumanInterruptConfig."""
        return self.load_interrupt(
            config.to_interrupt_value() if hasattr(config, "to_interrupt_value") else {
                "interrupt_id": config.interrupt_id,
                "interrupt_type": config.interrupt_type.value,
                "title": config.title,
                "description": config.description,
                "priority": config.priority.value,
                "options": config.options,
                "timeout_seconds": config.timeout_seconds,
                "allow_ignore": config.allow_ignore,
                "allow_response": config.allow_response,
                "metadata": config.metadata,
            },
            thread_id,
        )
    
    def submit_response(
        self,
        action: ResponseAction,
        response: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Optional[FrontendInterruptResponse]:
        """
        Submit a response to the current interrupt.
        
        Args:
            action: The action taken
            response: Optional custom response
            comment: Optional comment
        
        Returns:
            FrontendInterruptResponse or None if no interrupt
        """
        if not self._current_interrupt:
            return None
        
        # Update UI state
        self._current_interrupt.ui_state = InterruptUIState.RESPONDING
        self._notify_state_change(InterruptUIState.RESPONDING, self._current_interrupt)
        
        # Map action to interrupt status
        status_map = {
            ResponseAction.APPROVE: InterruptStatus.APPROVED,
            ResponseAction.REJECT: InterruptStatus.REJECTED,
            ResponseAction.IGNORE: InterruptStatus.IGNORED,
            ResponseAction.DEFER: InterruptStatus.IGNORED,
            ResponseAction.CUSTOM: InterruptStatus.APPROVED,
        }
        
        # Create response
        frontend_response = FrontendInterruptResponse(
            interrupt_id=self._current_interrupt.interrupt_id,
            action=action,
            response=response,
            comment=comment,
        )
        
        # Create full response for backend
        backend_response = InterruptResponse(
            interrupt_id=frontend_response.interrupt_id,
            status=status_map.get(action, InterruptStatus.APPROVED),
            response=frontend_response.response,
            comment=frontend_response.comment,
        )
        
        # Trigger callback if registered
        callback = self._response_callbacks.get(self._current_interrupt.interrupt_id)
        if callback:
            try:
                callback(frontend_response)
            except Exception as e:
                self._current_interrupt.error_message = str(e)
                self._current_interrupt.ui_state = InterruptUIState.ERROR
                self._notify_state_change(InterruptUIState.ERROR, self._current_interrupt)
                return None
        
        # Move to history
        self._current_interrupt.ui_state = InterruptUIState.SUBMITTED
        self._interrupt_history.append(self._current_interrupt)
        self._notify_state_change(InterruptUIState.SUBMITTED, self._current_interrupt)
        
        # Clear current
        self._current_interrupt = None
        
        return frontend_response
    
    def approve(
        self,
        response: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Optional[FrontendInterruptResponse]:
        """Approve the current interrupt."""
        return self.submit_response(ResponseAction.APPROVE, response, comment)
    
    def reject(
        self,
        response: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Optional[FrontendInterruptResponse]:
        """Reject the current interrupt."""
        return self.submit_response(ResponseAction.REJECT, response, comment)
    
    def ignore(
        self,
        comment: Optional[str] = None,
    ) -> Optional[FrontendInterruptResponse]:
        """Ignore the current interrupt."""
        return self.submit_response(ResponseAction.IGNORE, comment=comment)
    
    def submit_custom_response(
        self,
        response: str,
        comment: Optional[str] = None,
    ) -> Optional[FrontendInterruptResponse]:
        """Submit a custom response."""
        if not self._current_interrupt or not self._current_interrupt.allow_response:
            return None
        return self.submit_response(ResponseAction.CUSTOM, response, comment)
    
    def defer(self) -> Optional[FrontendInterruptResponse]:
        """Defer the current interrupt."""
        return self.submit_response(ResponseAction.DEFER)
    
    def cancel(self) -> None:
        """Cancel and dismiss the current interrupt."""
        if self._current_interrupt:
            self._interrupt_history.append(self._current_interrupt)
            self._notify_state_change(InterruptUIState.IDLE)
            self._current_interrupt = None
    
    def get_remaining_seconds(self) -> Optional[int]:
        """Get remaining seconds before timeout."""
        if not self._current_interrupt or not self._current_interrupt.expires_at:
            return None
        
        remaining = (self._current_interrupt.expires_at - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    def is_expired(self) -> bool:
        """Check if the current interrupt is expired."""
        if not self._current_interrupt:
            return False
        return self._current_interrupt.expires_at is not None and \
               datetime.utcnow() > self._current_interrupt.expires_at
    
    def handle_timeout(self) -> None:
        """Handle interrupt timeout."""
        if self._current_interrupt:
            self._current_interrupt.ui_state = InterruptUIState.TIMEOUT
            self._notify_state_change(InterruptUIState.TIMEOUT, self._current_interrupt)
            
            # Trigger timeout callback
            if self._timeout_callback:
                try:
                    self._timeout_callback()
                except Exception:
                    pass
    
    def get_available_actions(self) -> List[ResponseAction]:
        """Get list of available actions for current interrupt."""
        if not self._current_interrupt:
            return []
        
        actions = []
        
        if self._current_interrupt.options:
            actions.append(ResponseAction.APPROVE)
            if "Reject" in self._current_interrupt.options or "request changes" in [o.lower() for o in self._current_interrupt.options]:
                actions.append(ResponseAction.REJECT)
        
        if self._current_interrupt.allow_ignore:
            actions.append(ResponseAction.IGNORE)
        
        if self._current_interrupt.allow_response:
            actions.append(ResponseAction.CUSTOM)
        
        actions.append(ResponseAction.DEFER)
        
        return actions
    
    def clear_history(self) -> None:
        """Clear interrupt history."""
        self._interrupt_history.clear()
    
    def get_interrupt_by_id(self, interrupt_id: str) -> Optional[FrontendInterrupt]:
        """Get an interrupt from history by ID."""
        for interrupt in self._interrupt_history:
            if interrupt.interrupt_id == interrupt_id:
                return interrupt
        return None


class InterruptResponseBuilder:
    """
    Builder for constructing interrupt responses.
    
    Provides:
    1. Fluent API for building responses
    2. Validation before submission
    3. Auto-mapping of actions
    """
    
    def __init__(self, interrupt_id: str):
        """
        Initialize the response builder.
        
        Args:
            interrupt_id: ID of the interrupt being responded to
        """
        self.interrupt_id = interrupt_id
        self._action: Optional[ResponseAction] = None
        self._response: Optional[str] = None
        self._comment: Optional[str] = None
        self._metadata: Dict[str, Any] = {}
    
    def approve(self, response: Optional[str] = None) -> "InterruptResponseBuilder":
        """Set action to approve."""
        self._action = ResponseAction.APPROVE
        self._response = response
        return self
    
    def reject(
        self,
        response: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> "InterruptResponseBuilder":
        """Set action to reject."""
        self._action = ResponseAction.REJECT
        self._response = response
        self._comment = comment
        return self
    
    def ignore(self, comment: Optional[str] = None) -> "InterruptResponseBuilder":
        """Set action to ignore."""
        self._action = ResponseAction.IGNORE
        self._comment = comment
        return self
    
    def custom(self, response: str, comment: Optional[str] = None) -> "InterruptResponseBuilder":
        """Set action to custom response."""
        self._action = ResponseAction.CUSTOM
        self._response = response
        self._comment = comment
        return self
    
    def defer(self) -> "InterruptResponseBuilder":
        """Set action to defer."""
        self._action = ResponseAction.DEFER
        return self
    
    def with_metadata(self, key: str, value: Any) -> "InterruptResponseBuilder":
        """Add metadata to the response."""
        self._metadata[key] = value
        return self
    
    def build(self) -> FrontendInterruptResponse:
        """Build the response object."""
        if not self._action:
            raise ValueError("Response action must be set before building")
        
        return FrontendInterruptResponse(
            interrupt_id=self.interrupt_id,
            action=self._action,
            response=self._response,
            comment=self._comment,
            metadata=self._metadata,
        )
    
    def validate(self, available_options: List[str]) -> tuple[bool, str]:
        """
        Validate the response against available options.
        
        Args:
            available_options: Options provided by the interrupt
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if self._action == ResponseAction.CUSTOM and not self._response:
            return False, "Custom response is required"
        
        if self._response and self._response not in available_options and available_options:
            return False, f"Response '{self._response}' is not in available options"
        
        return True, ""


# ==================== Factory Functions ====================

def create_frontend_interrupt_handler() -> FrontendInterruptHandler:
    """
    Create a frontend interrupt handler.
    
    Returns:
        FrontendInterruptHandler instance
    """
    return FrontendInterruptHandler()


def create_response_builder(interrupt_id: str) -> InterruptResponseBuilder:
    """
    Create a response builder for an interrupt.
    
    Args:
        interrupt_id: ID of the interrupt
    
    Returns:
        InterruptResponseBuilder instance
    """
    return InterruptResponseBuilder(interrupt_id)
