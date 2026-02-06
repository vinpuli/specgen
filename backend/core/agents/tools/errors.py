"""
Tool Error Handling for LangGraph agents.

Provides custom error handling for tool failures including:
- Tool-specific error classes
- Error categorization and severity levels
- Error recovery strategies
- Error logging and monitoring integration
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Type
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ToolErrorSeverity(str, Enum):
    """Severity levels for tool errors."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ToolErrorCategory(str, Enum):
    """Categories for tool errors."""

    # Infrastructure errors
    CONNECTION_FAILED = "connection_failed"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"

    # Validation errors
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_FORMAT = "invalid_format"

    # Permission errors
    PERMISSION_DENIED = "permission_denied"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"

    # Data errors
    NOT_FOUND = "not_found"
    DATA_CORRUPTION = "data_corruption"
    CONFLICT = "conflict"

    # Execution errors
    EXECUTION_FAILED = "execution_failed"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    UNEXPECTED_STATE = "unexpected_state"

    # System errors
    OUT_OF_MEMORY = "out_of_memory"
    DISK_FULL = "disk_full"
    PROCESS_KILLED = "process_killed"

    # Unknown errors
    UNKNOWN = "unknown"


class ToolErrorCode(str, Enum):
    """Specific error codes for tools."""

    # Database errors
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    DB_QUERY_ERROR = "DB_QUERY_ERROR"
    DB_CONSTRAINT_VIOLATION = "DB_CONSTRAINT_VIOLATION"
    DB_DEADLOCK = "DB_DEADLOCK"

    # Vector store errors
    VECTOR_CONNECTION_ERROR = "VECTOR_CONNECTION_ERROR"
    VECTOR_SEARCH_ERROR = "VECTOR_SEARCH_ERROR"
    VECTOR_INDEX_ERROR = "VECTOR_INDEX_ERROR"

    # File system errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_PERMISSION_ERROR = "FILE_PERMISSION_ERROR"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"

    # Git errors
    GIT_REPO_NOT_FOUND = "GIT_REPO_NOT_FOUND"
    GIT_BRANCH_ERROR = "GIT_BRANCH_ERROR"
    GIT_COMMIT_ERROR = "GIT_COMMIT_ERROR"
    GIT_MERGE_CONFLICT = "GIT_MERGE_CONFLICT"

    # Network errors
    NETWORK_ERROR = "NETWORK_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    WEBSOCKET_ERROR = "WEBSOCKET_ERROR"


class ToolError(BaseModel):
    """Structured tool error representation."""

    error_id: str = Field(..., description="Unique error identifier")
    tool_name: str = Field(..., description="Name of the tool that failed")
    error_code: str = Field(..., description="Specific error code")
    category: ToolErrorCategory = Field(..., description="Error category")
    severity: ToolErrorSeverity = Field(
        default=ToolErrorSeverity.MEDIUM, description="Error severity"
    )
    message: str = Field(..., description="Human-readable error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")
    context: Dict[str, Any] = Field(default_factory=dict, description="Error context")
    retryable: bool = Field(default=False, description="Whether the error is retryable")
    timestamp: str = Field(
        default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat(),
        description="Error timestamp",
    )
    caused_by: Optional[str] = Field(None, description="Causing error ID if chained")


class ToolExecutionResult(BaseModel):
    """Result of tool execution with error handling."""

    tool_name: str = Field(..., description="Name of the tool")
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[Dict[str, Any]] = Field(None, description="Tool result data")
    error: Optional[ToolError] = Field(None, description="Error information if failed")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    warnings: List[str] = Field(default_factory=list, description="Execution warnings")


class ErrorRecoveryStrategy(str, Enum):
    """Strategies for recovering from errors."""

    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ESCALATE = "escalate"
    ABORT = "abort"


class ErrorRecoveryRule(BaseModel):
    """Rule for error recovery."""

    error_categories: List[ToolErrorCategory] = Field(
        ..., description="Categories this rule applies to"
    )
    error_codes: List[str] = Field(default_factory=list, description="Specific error codes")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_ms: int = Field(default=1000, description="Delay between retries")
    strategy: ErrorRecoveryStrategy = Field(
        default=ErrorRecoveryStrategy.RETRY, description="Recovery strategy"
    )
    fallback_tool: Optional[str] = Field(None, description="Fallback tool name")
    escalate_on_failure: bool = Field(default=False, description="Escalate after max retries")


class ToolErrorHandler:
    """
    Centralized error handler for tool operations.

    Features:
    - Error categorization and severity assignment
    - Recovery strategy application
    - Error logging and monitoring
    - Retry logic with exponential backoff
    """

    def __init__(self):
        """Initialize the error handler."""
        self.error_count: Dict[str, int] = {}
        self.recovery_rules: List[ErrorRecoveryRule] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """Register default error recovery rules."""
        # Connection errors - retry with backoff
        self.recovery_rules.append(
            ErrorRecoveryRule(
                error_categories=[
                    ToolErrorCategory.CONNECTION_FAILED,
                    ToolErrorCategory.TIMEOUT,
                ],
                error_codes=[],
                max_retries=3,
                retry_delay_ms=2000,
                strategy=ErrorRecoveryStrategy.RETRY,
            )
        )

        # Rate limiting - retry with longer backoff
        self.recovery_rules.append(
            ErrorRecoveryRule(
                error_categories=[ToolErrorCategory.RATE_LIMITED],
                error_codes=[],
                max_retries=5,
                retry_delay_ms=5000,
                strategy=ErrorRecoveryStrategy.RETRY,
            )
        )

        # Validation errors - don't retry, return immediately
        self.recovery_rules.append(
            ErrorRecoveryRule(
                error_categories=[
                    ToolErrorCategory.INVALID_INPUT,
                    ToolErrorCategory.MISSING_REQUIRED_FIELD,
                    ToolErrorCategory.INVALID_FORMAT,
                ],
                error_codes=[],
                max_retries=0,
                retry_delay_ms=0,
                strategy=ErrorRecoveryStrategy.ABORT,
            )
        )

        # Permission errors - don't retry
        self.recovery_rules.append(
            ErrorRecoveryRule(
                error_categories=[
                    ToolErrorCategory.PERMISSION_DENIED,
                    ToolErrorCategory.AUTHENTICATION_FAILED,
                ],
                error_codes=[],
                max_retries=0,
                retry_delay_ms=0,
                strategy=ErrorRecoveryStrategy.ESCALATE,
            )
        )

        # Not found errors - don't retry
        self.recovery_rules.append(
            ErrorRecoveryRule(
                error_categories=[ToolErrorCategory.NOT_FOUND],
                error_codes=["FILE_NOT_FOUND", "GIT_REPO_NOT_FOUND"],
                max_retries=0,
                retry_delay_ms=0,
                strategy=ErrorRecoveryStrategy.ABORT,
            )
        )

        # Resource exhaustion - retry with backoff
        self.recovery_rules.append(
            ErrorRecoveryRule(
                error_categories=[
                    ToolErrorCategory.RESOURCE_EXHAUSTED,
                    ToolErrorCategory.OUT_OF_MEMORY,
                    ToolErrorCategory.DISK_FULL,
                ],
                error_codes=[],
                max_retries=2,
                retry_delay_ms=3000,
                strategy=ErrorRecoveryStrategy.RETRY,
            )
        )

        # Git merge conflicts - escalate
        self.recovery_rules.append(
            ErrorRecoveryRule(
                error_categories=[ToolErrorCategory.CONFLICT],
                error_codes=["GIT_MERGE_CONFLICT"],
                max_retries=0,
                retry_delay_ms=0,
                strategy=ErrorRecoveryStrategy.ESCALATE,
            )
        )

    def categorize_error(self, error: Exception) -> ToolErrorCategory:
        """
        Categorize an exception into a tool error category.

        Args:
            error: The exception to categorize

        Returns:
            ToolErrorCategory for the exception
        """
        error_type = type(error).__name__
        error_message = str(error).lower()

        # Connection errors
        if any(
            keyword in error_message
            for keyword in ["connection", "network", "unreachable", "timeout"]
        ):
            if "timeout" in error_message:
                return ToolErrorCategory.TIMEOUT
            return ToolErrorCategory.CONNECTION_FAILED

        # Permission errors
        if any(
            keyword in error_message
            for keyword in ["permission", "access denied", "forbidden", "unauthorized"]
        ):
            if "auth" in error_message or "token" in error_message:
                return ToolErrorCategory.AUTHENTICATION_FAILED
            return ToolErrorCategory.PERMISSION_DENIED

        # Rate limiting
        if any(keyword in error_message for keyword in ["rate limit", "too many requests"]):
            return ToolErrorCategory.RATE_LIMITED

        # Not found
        if any(
            keyword in error_message
            for keyword in ["not found", "does not exist", "no such file", "404"]
        ):
            return ToolErrorCategory.NOT_FOUND

        # Validation errors
        if any(
            keyword in error_message
            for keyword in ["invalid", "validation", "schema", "type error"]
        ):
            if "required" in error_message or "missing" in error_message:
                return ToolErrorCategory.MISSING_REQUIRED_FIELD
            return ToolErrorCategory.INVALID_INPUT

        # Resource exhaustion
        if any(
            keyword in error_message
            for keyword in [
                "memory",
                "out of",
                "disk full",
                "quota exceeded",
                "limit exceeded",
            ]
        ):
            return ToolErrorCategory.RESOURCE_EXHAUSTED

        # Execution errors
        if any(
            keyword in error_message
            for keyword in ["execution", "failed", "error", "exception"]
        ):
            return ToolErrorCategory.EXECUTION_FAILED

        return ToolErrorCategory.UNKNOWN

    def determine_severity(
        self, category: ToolErrorCategory, error: Exception
    ) -> ToolErrorSeverity:
        """
        Determine error severity based on category and error.

        Args:
            category: Error category
            error: The exception

        Returns:
            ToolErrorSeverity level
        """
        critical_categories = {
            ToolErrorCategory.DATA_CORRUPTION,
            ToolErrorCategory.OUT_OF_MEMORY,
            ToolErrorCategory.DISK_FULL,
        }

        high_categories = {
            ToolErrorCategory.CONNECTION_FAILED,
            ToolErrorCategory.TIMEOUT,
            ToolErrorCategory.PERMISSION_DENIED,
            ToolErrorCategory.AUTHENTICATION_FAILED,
            ToolErrorCategory.RATE_LIMITED,
            ToolErrorCategory.RESOURCE_EXHAUSTED,
        }

        low_categories = {
            ToolErrorCategory.INVALID_INPUT,
            ToolErrorCategory.MISSING_REQUIRED_FIELD,
            ToolErrorCategory.INVALID_FORMAT,
        }

        if category in critical_categories:
            return ToolErrorSeverity.CRITICAL
        elif category in high_categories:
            return ToolErrorSeverity.HIGH
        elif category in low_categories:
            return ToolErrorSeverity.LOW

        return ToolErrorSeverity.MEDIUM

    def determine_retryable(self, category: ToolErrorCategory) -> bool:
        """Determine if an error category is retryable."""
        non_retryable = {
            ToolErrorCategory.INVALID_INPUT,
            ToolErrorCategory.MISSING_REQUIRED_FIELD,
            ToolErrorCategory.INVALID_FORMAT,
            ToolErrorCategory.PERMISSION_DENIED,
            ToolErrorCategory.AUTHENTICATION_FAILED,
            ToolErrorCategory.NOT_FOUND,
            ToolErrorCategory.DATA_CORRUPTION,
        }
        return category not in non_retryable

    def create_tool_error(
        self,
        tool_name: str,
        error: Exception,
        error_code: str = None,
        context: Dict[str, Any] = None,
        caused_by: str = None,
    ) -> ToolError:
        """
        Create a structured tool error from an exception.

        Args:
            tool_name: Name of the tool
            error: The exception
            error_code: Specific error code
            context: Error context
            caused_by: Causing error ID

        Returns:
            ToolError instance
        """
        category = self.categorize_error(error)
        severity = self.determine_severity(category, error)

        return ToolError(
            error_id=str(uuid4()),
            tool_name=tool_name,
            error_code=error_code or f"{type(error).__name__.upper()}_ERROR",
            category=category,
            severity=severity,
            message=str(error),
            details={
                "exception_type": type(error).__name__,
                "exception_module": type(error).__module__,
            },
            context=context or {},
            retryable=self.determine_retryable(category),
            caused_by=caused_by,
        )

    def get_recovery_rule(self, error: ToolError) -> ErrorRecoveryRule:
        """
        Get the recovery rule for an error.

        Args:
            error: The tool error

        Returns:
            Matching ErrorRecoveryRule
        """
        for rule in self.recovery_rules:
            if error.category in rule.error_categories:
                if error.error_code in rule.error_codes or not rule.error_codes:
                    return rule
        return ErrorRecoveryRule(
            error_categories=[error.category],
            max_retries=1,
            retry_delay_ms=1000,
            strategy=ErrorRecoveryStrategy.RETRY if error.retryable else ErrorRecoveryStrategy.ABORT,
        )

    def log_error(self, error: ToolError) -> None:
        """
        Log an error for monitoring.

        Args:
            error: The tool error to log
        """
        # Update error count
        self.error_count[error.tool_name] = self.error_count.get(error.tool_name, 0) + 1

        # In production, this would send to monitoring system
        # For now, just print
        import json

        log_entry = {
            "timestamp": error.timestamp,
            "error_id": error.error_id,
            "tool_name": error.tool_name,
            "error_code": error.error_code,
            "category": error.category.value,
            "severity": error.severity.value,
            "message": error.message,
            "retryable": error.retryable,
        }

        print(f"[TOOL_ERROR] {json.dumps(log_entry)}")

    def record_success(self, tool_name: str) -> None:
        """Record a successful tool execution."""
        # Could be used for success rate tracking
        pass

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            "error_counts": self.error_count.copy(),
            "total_errors": sum(self.error_count.values()),
            "recovery_rules_registered": len(self.recovery_rules),
        }


class ToolExecutor:
    """
    Wrapper for executing tools with error handling.

    Features:
    - Automatic error categorization
    - Retry logic with exponential backoff
    - Recovery strategy application
    - Result logging
    """

    def __init__(self, error_handler: ToolErrorHandler = None):
        """
        Initialize the tool executor.

        Args:
            error_handler: Optional custom error handler
        """
        self.error_handler = error_handler or ToolErrorHandler()

    async def execute_tool(
        self,
        tool_func,
        tool_name: str,
        *args,
        **kwargs,
    ) -> ToolExecutionResult:
        """
        Execute a tool with error handling.

        Args:
            tool_func: The tool function to execute
            tool_name: Name of the tool
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            ToolExecutionResult with success/error information
        """
        import time

        start_time = time.time()

        # Get recovery rule
        recovery_rule = self.error_handler.get_recovery_rule(
            ToolError(
                error_id="placeholder",
                tool_name=tool_name,
                error_code="PLACEHOLDER",
                category=ToolErrorCategory.UNKNOWN,
                message="placeholder",
            )
        )

        last_error: Optional[ToolError] = None
        retry_count = 0

        while retry_count <= recovery_rule.max_retries:
            try:
                # Execute the tool
                if hasattr(tool_func, "_arun"):
                    # Async tool
                    result = await tool_func._arun(*args, **kwargs)
                else:
                    # Sync tool
                    result = tool_func._run(*args, **kwargs)

                execution_time = (time.time() - start_time) * 1000

                self.error_handler.record_success(tool_name)

                return ToolExecutionResult(
                    tool_name=tool_name,
                    success=True,
                    result=result,
                    execution_time_ms=execution_time,
                    retry_count=retry_count,
                )

            except Exception as e:
                error = self.error_handler.create_tool_error(
                    tool_name=tool_name,
                    error=e,
                    context={"args": str(args), "kwargs": str(kwargs)},
                    caused_by=last_error.error_id if last_error else None,
                )

                self.error_handler.log_error(error)

                recovery_rule = self.error_handler.get_recovery_rule(error)

                if retry_count >= recovery_rule.max_retries:
                    # Max retries reached
                    if recovery_rule.strategy == ErrorRecoveryStrategy.ESCALATE:
                        # Escalate - return error for higher-level handling
                        return ToolExecutionResult(
                            tool_name=tool_name,
                            success=False,
                            error=error,
                            execution_time_ms=(time.time() - start_time) * 1000,
                            retry_count=retry_count,
                        )

                    elif recovery_rule.strategy == ErrorRecoveryStrategy.FALLBACK:
                        # Try fallback if available
                        if recovery_rule.fallback_tool:
                            return await self._execute_fallback(
                                recovery_rule.fallback_tool,
                                tool_name,
                                start_time,
                                args,
                                kwargs,
                            )

                    # Abort
                    return ToolExecutionResult(
                        tool_name=tool_name,
                        success=False,
                        error=error,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        retry_count=retry_count,
                    )

                # Retry with backoff
                retry_count += 1
                last_error = error

                if recovery_rule.retry_delay_ms > 0:
                    import asyncio

                    delay = recovery_rule.retry_delay_ms * (2 ** (retry_count - 1))
                    await asyncio.sleep(delay / 1000)

        # Should not reach here
        return ToolExecutionResult(
            tool_name=tool_name,
            success=False,
            error=last_error,
            execution_time_ms=(time.time() - start_time) * 1000,
            retry_count=retry_count,
        )

    async def _execute_fallback(
        self,
        fallback_tool: str,
        original_tool: str,
        start_time: float,
        args,
        kwargs,
    ) -> ToolExecutionResult:
        """Execute fallback tool."""
        # Implementation would depend on fallback tool availability
        return ToolExecutionResult(
            tool_name=original_tool,
            success=False,
            error=ToolError(
                error_id="fallback_required",
                tool_name=original_tool,
                error_code="FALLBACK_REQUIRED",
                category=ToolErrorCategory.UNEXPECTED_STATE,
                severity=ToolErrorSeverity.HIGH,
                message=f"Fallback to {fallback_tool} required",
                retryable=False,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )


# Convenience functions
def create_error_handler() -> ToolErrorHandler:
    """Create a new error handler with default rules."""
    return ToolErrorHandler()


def create_tool_executor(error_handler: ToolErrorHandler = None) -> ToolExecutor:
    """Create a new tool executor."""
    return ToolExecutor(error_handler=error_handler)


def with_error_handling(tool_func, tool_name: str):
    """
    Decorator for adding error handling to tools.

    Args:
        tool_func: Tool function to wrap
        tool_name: Name of the tool

    Returns:
        Wrapped function with error handling
    """
    executor = create_tool_executor()

    async def async_wrapper(*args, **kwargs):
        return await executor.execute_tool(tool_func, tool_name, *args, **kwargs)

    def sync_wrapper(*args, **kwargs):
        import asyncio

        return asyncio.run(async_wrapper(*args, **kwargs))

    return async_wrapper
