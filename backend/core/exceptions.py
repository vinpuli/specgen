"""
Custom exceptions and error handling for LangGraph and the specgen application.

This module defines a hierarchy of exceptions for the Agentic Spec Builder,
with specific focus on LangGraph-related errors, agent errors, and state errors.
"""

from typing import Any, Optional, Dict, List
from enum import Enum
from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorSeverity(str, Enum):
    """Error severity levels for categorization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categories for error classification."""
    VALIDATION = "validation"
    STATE_MANAGEMENT = "state_management"
    LLM_GENERATION = "llm_generation"
    CHECKPOINT = "checkpoint"
    NODE_EXECUTION = "node_execution"
    EDGE_ROUTING = "edge_routing"
    HUMAN_INTERRUPT = "human_interrupt"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"


class SpecGenException(Exception):
    """
    Base exception for the SpecGen application.
    
    All custom exceptions inherit from this class, providing
    a consistent interface for error handling.
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.VALIDATION,
    ):
        self.message = message
        self.details = details or {}
        self.severity = severity
        self.category = category
        super().__init__(self.message)


# ==================== HTTP Exceptions ====================

class HTTPBadRequestException(HTTPException):
    """400 Bad Request exception."""
    
    def __init__(self, detail: str = "Bad Request"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class HTTPUnauthorizedException(HTTPException):
    """401 Unauthorized exception."""
    
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class HTTPForbiddenException(HTTPException):
    """403 Forbidden exception."""
    
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class HTTPNotFoundException(HTTPException):
    """404 Not Found exception."""
    
    def __init__(self, detail: str = "Not Found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class HTTPConflictException(HTTPException):
    """409 Conflict exception."""
    
    def __init__(self, detail: str = "Conflict"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class HTTPUnprocessableEntityException(HTTPException):
    """422 Unprocessable Entity exception."""
    
    def __init__(self, detail: str = "Unprocessable Entity"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


# ==================== LangGraph Exceptions ====================

class LangGraphException(SpecGenException):
    """
    Base exception for LangGraph-related errors.
    
    Handles errors related to graph construction, execution,
    state management, and checkpointing.
    """
    
    def __init__(
        self,
        message: str,
        node_name: Optional[str] = None,
        graph_name: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["node_name"] = node_name
        details["graph_name"] = graph_name
        super().__init__(
            message=message,
            details=details,
            category=ErrorCategory.STATE_MANAGEMENT,
            **kwargs,
        )


class GraphConstructionError(LangGraphException):
    """Raised when graph construction fails."""
    
    def __init__(
        self,
        message: str,
        node_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=f"Graph construction error: {message}",
            node_name=node_name,
            graph_name="unknown",
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class NodeExecutionError(LangGraphException):
    """
    Raised when a node fails during execution.
    
    This is a critical error that halts graph execution.
    """
    
    def __init__(
        self,
        node_name: str,
        original_error: Optional[Exception] = None,
        retry_count: int = 0,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["retry_count"] = retry_count
        if original_error:
            details["original_error"] = str(original_error)
            details["original_error_type"] = type(original_error).__name__
        
        message = f"Node '{node_name}' execution failed"
        if original_error:
            message += f": {str(original_error)}"
        
        super().__init__(
            message=message,
            node_name=node_name,
            graph_name="unknown",
            details=details,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NODE_EXECUTION,
            **kwargs,
        )
    
    def with_retry_info(self, retry_count: int, max_retries: int) -> "NodeExecutionError":
        """Add retry information to the error."""
        self.details["retry_count"] = retry_count
        self.details["max_retries"] = max_retries
        self.details["can_retry"] = retry_count < max_retries
        return self


class EdgeRoutingError(LangGraphException):
    """Raised when edge routing fails to find a valid next node."""
    
    def __init__(
        self,
        current_node: str,
        routing_value: Any,
        available_edges: List[str],
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["current_node"] = current_node
        details["routing_value"] = str(routing_value)
        details["available_edges"] = available_edges
        
        super().__init__(
            message=f"No valid edge from node '{current_node}' with routing value '{routing_value}'",
            node_name=current_node,
            details=details,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.EDGE_ROUTING,
            **kwargs,
        )


class CheckpointError(LangGraphException):
    """Raised when checkpoint save/load fails."""
    
    def __init__(
        self,
        operation: str,  # "save" or "load"
        thread_id: str,
        checkpoint_id: Optional[str] = None,
        original_error: Optional[Exception] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["operation"] = operation
        details["thread_id"] = thread_id
        details["checkpoint_id"] = checkpoint_id
        if original_error:
            details["original_error"] = str(original_error)
        
        super().__init__(
            message=f"Checkpoint {operation} failed for thread '{thread_id}'",
            details=details,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.CHECKPOINT,
            **kwargs,
        )


class StateValidationError(LangGraphException):
    """Raised when state validation fails."""
    
    def __init__(
        self,
        state_field: str,
        expected_type: str,
        actual_value: Any,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["state_field"] = state_field
        details["expected_type"] = expected_type
        details["actual_type"] = type(actual_value).__name__
        
        super().__init__(
            message=f"State validation failed for field '{state_field}': expected {expected_type}",
            details=details,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


# ==================== Agent Exceptions ====================

class AgentException(SpecGenException):
    """Base exception for agent-related errors."""
    
    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            details={"agent_name": agent_name},
            **kwargs,
        )


class InterrogationAgentError(AgentException):
    """Raised when interrogation agent encounters an error."""
    
    def __init__(
        self,
        message: str,
        question_id: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["question_id"] = question_id
        super().__init__(
            message=f"Interrogation agent error: {message}",
            agent_name="InterrogationAgent",
            details=details,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


class SpecificationAgentError(AgentException):
    """Raised when specification agent encounters an error."""
    
    def __init__(
        self,
        message: str,
        artifact_type: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["artifact_type"] = artifact_type
        super().__init__(
            message=f"Specification agent error: {message}",
            agent_name="SpecificationAgent",
            details=details,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


class ValidationAgentError(AgentException):
    """Raised when validation agent encounters an error."""
    
    def __init__(
        self,
        message: str,
        validation_type: Optional[str] = None,
        contradictions_found: int = 0,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["validation_type"] = validation_type
        details["contradictions_found"] = contradictions_found
        super().__init__(
            message=f"Validation agent error: {message}",
            agent_name="ValidationAgent",
            details=details,
            severity=ErrorSeverity.HIGH if contradictions_found > 0 else ErrorSeverity.MEDIUM,
            **kwargs,
        )


class ContextMemoryError(AgentException):
    """Raised when context memory agent encounters an error."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,  # "retrieve", "store", "search"
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["operation"] = operation
        super().__init__(
            message=f"Context memory error: {message}",
            agent_name="ContextMemoryAgent",
            details=details,
            category=ErrorCategory.STATE_MANAGEMENT,
            **kwargs,
        )


# ==================== LLM Exceptions ====================

class LLMException(SpecGenException):
    """Base exception for LLM-related errors."""
    
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["provider"] = provider
        details["model"] = model
        super().__init__(
            message=message,
            details=details,
            category=ErrorCategory.LLM_GENERATION,
            **kwargs,
        )


class LLMGenerationError(LLMException):
    """Raised when LLM text generation fails."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        model: str,
        prompt_length: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["prompt_length"] = prompt_length
        super().__init__(
            message=f"LLM generation failed: {message}",
            provider=provider,
            model=model,
            details=details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class LLMTimeoutError(LLMException):
    """Raised when LLM request times out."""
    
    def __init__(
        self,
        provider: str,
        model: str,
        timeout_seconds: float,
        **kwargs,
    ):
        super().__init__(
            message=f"LLM request timed out after {timeout_seconds}s",
            provider=provider,
            model=model,
            details={"timeout_seconds": timeout_seconds},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.TIMEOUT,
            **kwargs,
        )


class LLMRateLimitError(LLMException):
    """Raised when LLM rate limit is exceeded."""
    
    def __init__(
        self,
        provider: str,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["retry_after"] = retry_after
        super().__init__(
            message=f"Rate limit exceeded for {provider}",
            provider=provider,
            details=details,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.RESOURCE,
            **kwargs,
        )


# ==================== Human-in-the-Loop Exceptions ====================

class HumanInterruptException(SpecGenException):
    """Base exception for human-in-the-loop interruptions."""
    
    def __init__(
        self,
        message: str,
        interrupt_type: str,
        node_name: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["interrupt_type"] = interrupt_type
        details["node_name"] = node_name
        super().__init__(
            message=message,
            details=details,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.HUMAN_INTERRUPT,
            **kwargs,
        )


class HumanTimeoutException(HumanInterruptException):
    """Raised when human response times out."""
    
    def __init__(
        self,
        node_name: str,
        timeout_seconds: int,
        **kwargs,
    ):
        super().__init__(
            message=f"Human response timed out after {timeout_seconds}s at node '{node_name}'",
            interrupt_type="timeout",
            node_name=node_name,
            details={"timeout_seconds": timeout_seconds},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.TIMEOUT,
            **kwargs,
        )


class HumanRejectException(HumanInterruptException):
    """Raised when human rejects an action during interrupt."""
    
    def __init__(
        self,
        node_name: str,
        reason: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=f"Human rejected action at node '{node_name}'",
            interrupt_type="reject",
            node_name=node_name,
            details={"reason": reason},
            severity=ErrorSeverity.LOW,
            **kwargs,
        )


# ==================== Vector Store Exceptions ====================

class VectorStoreException(SpecGenException):
    """Base exception for vector store operations."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["operation"] = operation
        super().__init__(
            message=message,
            details=details,
            category=ErrorCategory.STATE_MANAGEMENT,
            **kwargs,
        )


class VectorSearchError(VectorStoreException):
    """Raised when vector similarity search fails."""
    
    def __init__(
        self,
        query: str,
        top_k: int,
        original_error: Optional[Exception] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["query_length"] = len(query)
        details["top_k"] = top_k
        if original_error:
            details["original_error"] = str(original_error)
        
        super().__init__(
            message=f"Vector search failed for query (length={len(query)}, top_k={top_k})",
            operation="search",
            details=details,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


class VectorStoreUpsertError(VectorStoreException):
    """Raised when vector store upsert fails."""
    
    def __init__(
        self,
        document_id: str,
        original_error: Optional[Exception] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["document_id"] = document_id
        if original_error:
            details["original_error"] = str(original_error)
        
        super().__init__(
            message=f"Vector store upsert failed for document '{document_id}'",
            operation="upsert",
            details=details,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


# ==================== Exception Handlers ====================

class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str
    details: Dict[str, Any] = {}
    severity: str = "medium"
    category: str = "validation"


def format_exception(e: Exception) -> ErrorResponse:
    """Format an exception into a standard error response."""
    if isinstance(e, SpecGenException):
        return ErrorResponse(
            error=e.message,
            details=e.details,
            severity=e.severity.value,
            category=e.category.value,
        )
    elif isinstance(e, HTTPException):
        return ErrorResponse(
            error=e.detail,
            details={},
            severity=ErrorSeverity.LOW.value,
            category=ErrorCategory.VALIDATION.value,
        )
    else:
        return ErrorResponse(
            error=str(e),
            details={"exception_type": type(e).__name__},
            severity=ErrorSeverity.HIGH.value,
            category=ErrorCategory.VALIDATION.value,
        )


def get_exception_chain(e: Exception) -> List[str]:
    """Get the full exception chain as a list of strings."""
    chain = []
    current = e
    while current is not None:
        chain.append(f"{type(current).__name__}: {str(current)}")
        current = getattr(current, "__cause__", None)
    return chain
