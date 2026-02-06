"""
Supervisor Agent for orchestrating all agents in the spec generation system.

This module provides the SupervisorAgent that coordinates the workflow between
all specialized agents:
- InterrogationAgent: Gathers user decisions through Q&A
- SpecificationAgent: Generates artifacts from decisions
- ValidationAgent: Validates decisions and artifacts
- ContextMemoryAgent: Manages RAG-based context retrieval
- DeliveryAgent: Exports and delivers artifacts
"""

from typing import Any, Dict, List, Optional, Callable, Union, Set
from enum import Enum
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph
from langgraph.types import Interrupt, Command
import asyncio
import threading

from .types import (
    AgentType,
    AgentTask,
    Message,
    MessageRole,
    Decision,
    Artifact,
    HumanInterrupt,
    InterruptType,
)
from .state import (
    SupervisorAgentState,
    create_supervisor_state,
    add_message,
)
from .human_in_the_loop import (
    InterruptManager,
    create_interrupt,
    resume_with_value,
)


# ==================== Supervisor Enums ====================

class SupervisorAction(str, Enum):
    """Actions the supervisor can take."""
    START_INTERROGATION = "start_interrogation"
    START_SPECIFICATION = "start_specification"
    START_VALIDATION = "start_validation"
    START_CONTEXT_MEMORY = "start_context_memory"
    START_DELIVERY = "start_delivery"
    ROUTE_TO_AGENT = "route_to_agent"
    CHECK_COMPLETION = "check_completion"
    HANDLE_INTERRUPT = "handle_interrupt"
    FINALIZE = "finalize"
    ERROR = "error"


class SupervisorStatus(str, Enum):
    """Status of the supervisor."""
    IDLE = "idle"
    ORCHESTRATING = "orchestrating"
    WAITING_FOR_AGENT = "waiting_for_agent"
    WAITING_FOR_INTERRUPT = "waiting_for_interrupt"
    COMPLETED = "completed"
    ERROR = "error"


class RoutingStrategy(str, Enum):
    """Strategies for routing tasks to agents."""
    SEQUENTIAL = "sequential"  # Process agents one after another
    PARALLEL = "parallel"  # Process independent agents concurrently
    PRIORITY = "priority"  # Route based on priority
    DEPENDENCY = "dependency"  # Route based on dependencies
    TASK_TYPE = "task_type"  # Route based on task type


class TaskType(str, Enum):
    """Types of tasks that can be routed to agents."""
    DECISION_GATHERING = "decision_gathering"  # InterrogationAgent: Gather decisions
    SPECIFICATION_GENERATION = "specification_generation"  # SpecificationAgent: Generate specs
    ARTIFACT_VALIDATION = "artifact_validation"  # ValidationAgent: Validate artifacts
    CONTEXT_RETRIEVAL = "context_retrieval"  # ContextMemoryAgent: Retrieve context
    ARTIFACT_EXPORT = "artifact_export"  # DeliveryAgent: Export artifacts
    CODEBASE_ANALYSIS = "codebase_analysis"  # ContextMemoryAgent: Analyze codebase
    CONFLICT_RESOLUTION = "conflict_resolution"  # ValidationAgent: Resolve conflicts
    IMPACT_ANALYSIS = "impact_analysis"  # ContextMemoryAgent: Analyze impact
    GENERAL_QUERY = "general_query"  # Route to appropriate agent based on content


# Task Type to Agent Mapping
TASK_TYPE_TO_AGENT: Dict[TaskType, AgentType] = {
    TaskType.DECISION_GATHERING: AgentType.INTERROGATION,
    TaskType.SPECIFICATION_GENERATION: AgentType.SPECIFICATION,
    TaskType.ARTIFACT_VALIDATION: AgentType.VALIDATION,
    TaskType.CONTEXT_RETRIEVAL: AgentType.CONTEXT_MEMORY,
    TaskType.ARTIFACT_EXPORT: AgentType.DELIVERY,
    TaskType.CODEBASE_ANALYSIS: AgentType.CONTEXT_MEMORY,
    TaskType.CONFLICT_RESOLUTION: AgentType.VALIDATION,
    TaskType.IMPACT_ANALYSIS: AgentType.CONTEXT_MEMORY,
}

# Agent to Task Types Mapping (reverse)
AGENT_TO_TASK_TYPES: Dict[AgentType, List[TaskType]] = {
    AgentType.INTERROGATION: [TaskType.DECISION_GATHERING],
    AgentType.SPECIFICATION: [TaskType.SPECIFICATION_GENERATION],
    AgentType.VALIDATION: [TaskType.ARTIFACT_VALIDATION, TaskType.CONFLICT_RESOLUTION],
    AgentType.CONTEXT_MEMORY: [TaskType.CONTEXT_RETRIEVAL, TaskType.CODEBASE_ANALYSIS, TaskType.IMPACT_ANALYSIS],
    AgentType.DELIVERY: [TaskType.ARTIFACT_EXPORT],
}


# Task Type Priority Order (higher = more urgent)
TASK_TYPE_PRIORITY: Dict[TaskType, int] = {
    TaskType.DECISION_GATHERING: 10,  # Must gather decisions first
    TaskType.CONFLICT_RESOLUTION: 9,  # Critical - resolve conflicts immediately
    TaskType.ARTIFACT_VALIDATION: 8,  # Validate before delivery
    TaskType.SPECIFICATION_GENERATION: 7,  # Generate specs from decisions
    TaskType.IMPACT_ANALYSIS: 6,  # Analysis can wait
    TaskType.CONTEXT_RETRIEVAL: 5,  # Context retrieval
    TaskType.ARTIFACT_EXPORT: 4,  # Export after validation
    TaskType.CODEBASE_ANALYSIS: 3,  # Lower priority
    TaskType.GENERAL_QUERY: 1,  # Lowest priority
}


# Task Dependencies (task type -> prerequisite task types)
TASK_DEPENDENCIES: Dict[TaskType, List[TaskType]] = {
    TaskType.SPECIFICATION_GENERATION: [TaskType.DECISION_GATHERING],
    TaskType.ARTIFACT_VALIDATION: [TaskType.SPECIFICATION_GENERATION],
    TaskType.ARTIFACT_EXPORT: [TaskType.ARTIFACT_VALIDATION],
    TaskType.CONFLICT_RESOLUTION: [TaskType.DECISION_GATHERING],
    TaskType.IMPACT_ANALYSIS: [TaskType.SPECIFICATION_GENERATION],
}


# Agent Selection Weights (for intelligent selection)
AGENT_SELECTION_WEIGHTS: Dict[AgentType, Dict[str, float]] = {
    AgentType.INTERROGATION: {
        "decision_gathering": 1.0,
        "context_retrieval": 0.3,
    },
    AgentType.SPECIFICATION: {
        "specification_generation": 1.0,
        "context_retrieval": 0.2,
    },
    AgentType.VALIDATION: {
        "artifact_validation": 1.0,
        "conflict_resolution": 1.0,
    },
    AgentType.CONTEXT_MEMORY: {
        "context_retrieval": 1.0,
        "codebase_analysis": 1.0,
        "impact_analysis": 1.0,
    },
    AgentType.DELIVERY: {
        "artifact_export": 1.0,
    },
}


# Agent Capability Matrix
AGENT_CAPABILITIES: Dict[AgentType, List[str]] = {
    AgentType.INTERROGATION: ["question_generation", "answer_validation", "decision_recording", "gap_analysis"],
    AgentType.SPECIFICATION: ["prd_generation", "api_generation", "schema_generation", "ticket_generation"],
    AgentType.VALIDATION: ["contradiction_detection", "dependency_checking", "impact_validation"],
    AgentType.CONTEXT_MEMORY: ["context_retrieval", "semantic_search", "codebase_analysis", "impact_analysis"],
    AgentType.DELIVERY: ["markdown_export", "json_export", "api_export", "pdf_generation"],
}


# ==================== Supervisor Configuration ====================

class SupervisorConfig(BaseModel):
    """Configuration for the supervisor agent."""
    default_routing_strategy: RoutingStrategy = RoutingStrategy.SEQUENTIAL
    max_retries: int = 3
    retry_delay_seconds: int = 5
    require_validation: bool = True
    require_delivery: bool = True
    interrupt_on_high_priority: bool = True
    auto_finalize: bool = False


class AgentResult(BaseModel):
    """Result from an agent execution."""
    agent_type: AgentType
    task_id: str
    success: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    interrupts_handled: int = 0


class TaskDelegationStatus(str, Enum):
    """Status of task delegation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskDelegation(BaseModel):
    """Task delegation record."""
    delegation_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    agent_type: AgentType
    task_type: TaskType
    status: TaskDelegationStatus = TaskDelegationStatus.PENDING
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0
    max_retries: int = 3


class SupervisorDecision(BaseModel):
    """Decision made by the supervisor about agent routing."""
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    action: SupervisorAction
    target_agent: Optional[AgentType] = None
    reasoning: str
    confidence: float = 1.0
    alternative_actions: List[SupervisorAction] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AggregationStatus(str, Enum):
    """Status of result aggregation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ResultAggregation(BaseModel):
    """Aggregation of results from multiple agents."""
    aggregation_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    status: AggregationStatus = AggregationStatus.PENDING
    agent_results: Dict[str, AgentResult] = Field(default_factory=dict)
    delegation_results: List[TaskDelegation] = Field(default_factory=list)
    aggregated_output: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def add_result(self, result: AgentResult) -> None:
        """Add an agent result to the aggregation."""
        self.agent_results[result.task_id] = result
        
    def add_delegation_result(self, delegation: TaskDelegation) -> None:
        """Add a delegation result to the aggregation."""
        self.delegation_results.append(delegation)
    
    def get_success_count(self) -> int:
        """Get count of successful results."""
        count = sum(1 for r in self.agent_results.values() if r.success)
        count += sum(1 for d in self.delegation_results if d.status == TaskDelegationStatus.COMPLETED)
        return count
    
    def get_failure_count(self) -> int:
        """Get count of failed results."""
        count = sum(1 for r in self.agent_results.values() if not r.success)
        count += sum(1 for d in self.delegation_results if d.status == TaskDelegationStatus.FAILED)
        return count
    
    def is_complete(self) -> bool:
        """Check if all expected results have been received."""
        return self.get_success_count() + self.get_failure_count() >= len(self.agent_results) + len(self.delegation_results)


class AggregatedArtifact(BaseModel):
    """Aggregated artifact from specification generation."""
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    artifact_type: str
    content: str
    format: str
    source_agent: AgentType
    metadata: Dict[str, Any] = Field(default_factory=dict)
    validation_status: str = "pending"
    dependencies: List[str] = Field(default_factory=list)


class ParallelExecutionStatus(str, Enum):
    """Status of parallel execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ParallelExecution(BaseModel):
    """Parallel execution of multiple agents."""
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    status: ParallelExecutionStatus = ParallelExecutionStatus.PENDING
    task_types: List[TaskType]
    agent_selections: Dict[TaskType, AgentType]
    results: Dict[TaskType, AgentResult] = Field(default_factory=dict)
    errors: Dict[TaskType, str] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_seconds: int = 300
    
    def add_result(self, task_type: TaskType, result: AgentResult) -> None:
        """Add a result for a task type."""
        self.results[task_type] = result
        
    def add_error(self, task_type: TaskType, error: str) -> None:
        """Add an error for a task type."""
        self.errors[task_type] = error
        
    def get_success_count(self) -> int:
        """Get count of successful results."""
        return sum(1 for r in self.results.values() if r.success)
    
    def get_failure_count(self) -> int:
        """Get count of failed results."""
        return len(self.results) + len(self.errors) - self.get_success_count()
    
    def is_complete(self) -> bool:
        """Check if all tasks are complete."""
        return len(self.results) + len(self.errors) >= len(self.task_types)
    
    def is_successful(self) -> bool:
        """Check if all tasks succeeded."""
        return self.get_failure_count() == 0 and len(self.results) == len(self.task_types)


# ==================== Agent Timeout & Fallback Mechanisms ====================


class TimeoutStrategy(str, Enum):
    """Strategies for handling agent timeouts."""
    FAIL = "fail"  # Fail the task immediately
    RETRY = "retry"  # Retry the same agent
    FALLBACK = "fallback"  # Route to fallback agent
    QUEUE = "queue"  # Queue for later processing
    ESCALATE = "escalate"  # Escalate to supervisor


class FallbackCondition(str, Enum):
    """Conditions for triggering fallback."""
    TIMEOUT = "timeout"  # Agent timed out
    ERROR = "error"  # Agent returned error
    UNAVAILABLE = "unavailable"  # Agent unavailable
    DEGRADED = "degraded"  # Agent performance degraded
    MANUAL = "manual"  # Manual trigger
    LOAD = "high_load"  # Agent has high load


class TimeoutConfig(BaseModel):
    """Configuration for timeout handling."""
    config_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    task_type: Optional[TaskType] = None
    timeout_seconds: int = 300  # Default 5 minutes
    soft_timeout_seconds: Optional[int] = None  # Warning before hard timeout
    retry_count: int = 0  # Number of retries before fallback
    retry_delay_seconds: int = 10  # Delay between retries
    fallback_agent: Optional[AgentType] = None  # Agent to fallback to
    fallback_strategy: TimeoutStrategy = TimeoutStrategy.FALLBACK
    escalate_on_max_retries: bool = True
    notify_on_timeout: bool = True
    record_metrics: bool = True


class FallbackRule(BaseModel):
    """Rule for fallback routing."""
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    primary_agent: AgentType
    fallback_agent: AgentType
    conditions: List[FallbackCondition] = Field(default_factory=list)
    priority: int = 0  # Higher priority rules applied first
    is_active: bool = True
    max_fallbacks: int = 3  # Max times this fallback can be used
    fallback_count: int = 0
    cooldown_seconds: Optional[int] = None  # Cooldown between fallbacks
    last_triggered: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def can_trigger(self) -> bool:
        """Check if fallback can be triggered."""
        if not self.is_active:
            return False
        
        if self.max_fallbacks > 0 and self.fallback_count >= self.max_fallbacks:
            return False
        
        if self.cooldown_seconds and self.last_triggered:
            elapsed = (datetime.utcnow() - self.last_triggered).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        
        return True
    
    def trigger(self) -> None:
        """Record that this fallback was triggered."""
        self.fallback_count += 1
        self.last_triggered = datetime.utcnow()


class TimeoutEvent(BaseModel):
    """Event when an agent timeout occurs."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    task_id: str
    task_type: TaskType
    timeout_seconds: int
    elapsed_seconds: float
    strategy: TimeoutStrategy
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = 0
    fallback_agent: Optional[AgentType] = None
    error_message: Optional[str] = None
    state_snapshot: Optional[Dict[str, Any]] = None


class RetryAttempt(BaseModel):
    """Record of a retry attempt."""
    attempt_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    agent_type: AgentType
    attempt_number: int
    previous_error: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    execution_time_ms: float = 0.0
    fallback_triggered: bool = False


class TimeoutManager(BaseModel):
    """Manager for handling agent timeouts and fallbacks."""
    manager_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    timeout_configs: Dict[str, TimeoutConfig] = Field(default_factory=dict)  # (agent_type, task_type) -> config
    fallback_rules: List[FallbackRule] = Field(default_factory=list)
    timeout_events: List[TimeoutEvent] = Field(default_factory=list)
    retry_history: Dict[str, List[RetryAttempt]] = Field(default_factory=dict)  # task_id -> attempts
    global_timeout_seconds: int = 600  # 10 minutes global timeout
    max_retries_per_task: int = 3
    enable_automatic_fallback: bool = True
    enable_retry_logic: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # ==================== Timeout Configuration ====================
    
    def set_timeout(
        self,
        agent_type: AgentType,
        timeout_seconds: int = 300,
        soft_timeout_seconds: Optional[int] = None,
        retry_count: int = 0,
        retry_delay_seconds: int = 10,
        fallback_agent: Optional[AgentType] = None,
        fallback_strategy: TimeoutStrategy = TimeoutStrategy.FALLBACK,
        task_type: Optional[TaskType] = None,
    ) -> TimeoutConfig:
        """Set timeout configuration for an agent."""
        config = TimeoutConfig(
            agent_type=agent_type,
            task_type=task_type,
            timeout_seconds=timeout_seconds,
            soft_timeout_seconds=soft_timeout_seconds,
            retry_count=retry_count,
            retry_delay_seconds=retry_delay_seconds,
            fallback_agent=fallback_agent,
            fallback_strategy=fallback_strategy,
        )
        
        key = f"{agent_type.value}:{task_type.value if task_type else 'default'}"
        self.timeout_configs[key] = config
        self.last_updated = datetime.utcnow()
        
        return config
    
    def get_timeout(self, agent_type: AgentType, task_type: Optional[TaskType] = None) -> Optional[TimeoutConfig]:
        """Get timeout configuration for an agent."""
        key = f"{agent_type.value}:{task_type.value if task_type else 'default'}"
        return self.timeout_configs.get(key)
    
    def remove_timeout(self, agent_type: AgentType, task_type: Optional[TaskType] = None) -> bool:
        """Remove timeout configuration."""
        key = f"{agent_type.value}:{task_type.value if task_type else 'default'}"
        
        if key in self.timeout_configs:
            del self.timeout_configs[key]
            self.last_updated = datetime.utcnow()
            return True
        
        return False
    
    def get_effective_timeout(self, agent_type: AgentType, task_type: Optional[TaskType] = None) -> int:
        """Get effective timeout for an agent/task."""
        config = self.get_timeout(agent_type, task_type)
        
        if config:
            return config.timeout_seconds
        
        # Return global timeout
        return self.global_timeout_seconds
    
    # ==================== Fallback Rule Management ====================
    
    def add_fallback_rule(
        self,
        primary_agent: AgentType,
        fallback_agent: AgentType,
        conditions: List[FallbackCondition] = None,
        priority: int = 0,
        max_fallbacks: int = 3,
        cooldown_seconds: Optional[int] = None,
    ) -> FallbackRule:
        """Add a fallback rule."""
        rule = FallbackRule(
            primary_agent=primary_agent,
            fallback_agent=fallback_agent,
            conditions=conditions or [FallbackCondition.TIMEOUT, FallbackCondition.ERROR],
            priority=priority,
            max_fallbacks=max_fallbacks,
            cooldown_seconds=cooldown_seconds,
        )
        
        self.fallback_rules.append(rule)
        self.fallback_rules.sort(key=lambda r: r.priority, reverse=True)
        self.last_updated = datetime.utcnow()
        
        return rule
    
    def remove_fallback_rule(self, rule_id: str) -> bool:
        """Remove a fallback rule."""
        for i, rule in enumerate(self.fallback_rules):
            if rule.rule_id == rule_id:
                self.fallback_rules.pop(i)
                self.last_updated = datetime.utcnow()
                return True
        
        return False
    
    def get_fallback_agent(
        self,
        primary_agent: AgentType,
        condition: FallbackCondition,
        current_fallbacks: int = 0,
    ) -> Optional[AgentType]:
        """Get fallback agent based on rules."""
        for rule in self.fallback_rules:
            if rule.primary_agent == primary_agent:
                if condition in rule.conditions:
                    if rule.can_trigger():
                        if current_fallbacks < rule.max_fallbacks:
                            rule.trigger()
                            self.last_updated = datetime.utcnow()
                            return rule.fallback_agent
        
        return None
    
    def get_all_fallbacks(self, primary_agent: AgentType) -> List[FallbackRule]:
        """Get all fallback rules for an agent."""
        return [r for r in self.fallback_rules if r.primary_agent == primary_agent]
    
    # ==================== Timeout Handling ====================
    
    def handle_timeout(
        self,
        agent_type: AgentType,
        task_id: str,
        task_type: TaskType,
        elapsed_seconds: float,
        state: Optional[Dict[str, Any]] = None,
    ) -> TimeoutEvent:
        """Handle a timeout event."""
        config = self.get_timeout(agent_type, task_type)
        strategy = config.fallback_strategy if config else TimeoutStrategy.FAIL
        
        event = TimeoutEvent(
            agent_type=agent_type,
            task_id=task_id,
            task_type=task_type,
            timeout_seconds=self.get_effective_timeout(agent_type, task_type),
            elapsed_seconds=elapsed_seconds,
            strategy=strategy,
            state_snapshot=state,
        )
        
        self.timeout_events.append(event)
        
        # Check if we should retry
        retry_count = self.get_retry_count(task_id)
        if config and retry_count < config.retry_count:
            event.retry_count = retry_count + 1
            event.strategy = TimeoutStrategy.RETRY
        
        # Check for fallback
        elif self.enable_automatic_fallback:
            fallback_agent = self.get_fallback_agent(agent_type, FallbackCondition.TIMEOUT)
            if fallback_agent:
                event.fallback_agent = fallback_agent
                event.strategy = TimeoutStrategy.FALLBACK
        
        self.last_updated = datetime.utcnow()
        
        return event
    
    def should_retry(self, task_id: str, agent_type: AgentType) -> Tuple[bool, int]:
        """Check if a task should be retried."""
        config = self.get_timeout(agent_type)
        if not config or config.retry_count == 0:
            return False, 0
        
        retry_count = self.get_retry_count(task_id)
        if retry_count < config.retry_count:
            return True, retry_count + 1
        
        return False, retry_count
    
    def record_retry(
        self,
        task_id: str,
        agent_type: AgentType,
        previous_error: str,
        started_at: datetime,
    ) -> RetryAttempt:
        """Record a retry attempt."""
        attempt = RetryAttempt(
            task_id=task_id,
            agent_type=agent_type,
            attempt_number=self.get_retry_count(task_id) + 1,
            previous_error=previous_error,
            started_at=started_at,
        )
        
        if task_id not in self.retry_history:
            self.retry_history[task_id] = []
        
        self.retry_history[task_id].append(attempt)
        self.last_updated = datetime.utcnow()
        
        return attempt
    
    def complete_retry(
        self,
        task_id: str,
        attempt_id: str,
        success: bool,
        execution_time_ms: float,
    ) -> bool:
        """Record retry completion."""
        attempts = self.retry_history.get(task_id, [])
        
        for attempt in attempts:
            if attempt.attempt_id == attempt_id:
                attempt.success = success
                attempt.completed_at = datetime.utcnow()
                attempt.execution_time_ms = execution_time_ms
                self.last_updated = datetime.utcnow()
                return True
        
        return False
    
    def get_retry_count(self, task_id: str) -> int:
        """Get the number of retries for a task."""
        attempts = self.retry_history.get(task_id, [])
        return len([a for a in attempts if a.success or not a.completed_at])
    
    def get_retry_history(self, task_id: str) -> List[RetryAttempt]:
        """Get retry history for a task."""
        return self.retry_history.get(task_id, [])
    
    # ==================== Fallback Execution ====================
    
    def execute_fallback(
        self,
        primary_agent: AgentType,
        task_id: str,
        condition: FallbackCondition,
        error_message: Optional[str] = None,
    ) -> Tuple[Optional[AgentType], TimeoutStrategy]:
        """Execute fallback routing."""
        # Find matching fallback rule
        fallback_agent = self.get_fallback_agent(primary_agent, condition)
        
        if fallback_agent:
            return fallback_agent, TimeoutStrategy.FALLBACK
        
        # Check if we should retry
        should_retry, retry_count = self.should_retry(task_id, primary_agent)
        if should_retry:
            return primary_agent, TimeoutStrategy.RETRY
        
        # Default to fail if no fallback available
        return None, TimeoutStrategy.FAIL
    
    def is_fallback_exhausted(
        self,
        primary_agent: AgentType,
        task_id: str,
    ) -> bool:
        """Check if all fallbacks are exhausted for a task."""
        fallback_rules = self.get_all_fallbacks(primary_agent)
        
        total_fallbacks = sum(rule.fallback_count for rule in fallback_rules)
        retry_count = self.get_retry_count(task_id)
        
        return total_fallbacks >= self.max_retries_per_task and retry_count >= self.max_retries_per_task
    
    # ==================== Statistics & Reporting ====================
    
    def get_timeout_statistics(self) -> Dict[str, Any]:
        """Get statistics about timeouts."""
        total_events = len(self.timeout_events)
        timeout_events = [e for e in self.timeout_events if e.elapsed_seconds >= e.timeout_seconds]
        fallback_events = [e for e in self.timeout_events if e.strategy == TimeoutStrategy.FALLBACK]
        retry_events = [e for e in self.timeout_events if e.strategy == TimeoutStrategy.RETRY]
        
        return {
            "total_timeout_events": total_events,
            "actual_timeouts": len(timeout_events),
            "fallback_events": len(fallback_events),
            "retry_events": len(retry_events),
            "timeout_rate": len(timeout_events) / max(total_events, 1),
            "fallback_rate": len(fallback_events) / max(total_events, 1),
            "avg_elapsed_seconds": sum(e.elapsed_seconds for e in self.timeout_events) / max(total_events, 1),
            "timeout_config_count": len(self.timeout_configs),
            "fallback_rule_count": len(self.fallback_rules),
            "pending_retries": sum(
                len(attempts) - sum(1 for a in attempts if a.completed_at)
                for attempts in self.retry_history.values()
            ),
        }
    
    def get_fallback_statistics(self) -> Dict[str, Any]:
        """Get statistics about fallbacks."""
        fallback_counts: Dict[str, int] = {}
        condition_counts: Dict[str, int] = {}
        
        for event in self.timeout_events:
            if event.fallback_agent:
                key = f"{event.agent_type.value} -> {event.fallback_agent.value}"
                fallback_counts[key] = fallback_counts.get(key, 0) + 1
        
        for rule in self.fallback_rules:
            condition_counts[rule.primary_agent.value] = rule.fallback_count
        
        return {
            "total_fallback_rules": len(self.fallback_rules),
            "active_fallback_rules": sum(1 for r in self.fallback_rules if r.is_active),
            "fallback_counts": fallback_counts,
            "fallback_by_agent": condition_counts,
            "total_fallbacks_triggered": sum(r.fallback_count for r in self.fallback_rules),
        }
    
    def get_recent_events(
        self,
        limit: int = 10,
        event_type: Optional[str] = None,
    ) -> List[TimeoutEvent]:
        """Get recent timeout events."""
        events = self.timeout_events
        
        if event_type:
            events = [e for e in events if e.strategy.value == event_type]
        
        return events[-limit:]
    
    def clear_old_events(self, max_age_hours: int = 24) -> int:
        """Clear old timeout events."""
        threshold = datetime.utcnow() - datetime.timedelta(hours=max_age_hours)
        
        original_count = len(self.timeout_events)
        self.timeout_events = [
            e for e in self.timeout_events
            if e.triggered_at >= threshold
        ]
        
        return original_count - len(self.timeout_events)
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall status of timeout manager."""
        stats = self.get_timeout_statistics()
        
        return {
            "total_configs": len(self.timeout_configs),
            "total_fallback_rules": len(self.fallback_rules),
            "timeout_events": stats["total_timeout_events"],
            "fallback_events": stats["fallback_events"],
            "timeout_rate": f"{stats['timeout_rate']:.2%}",
            "active_fallbacks": sum(1 for r in self.fallback_rules if r.is_active),
            "pending_retries": stats["pending_retries"],
            "global_timeout_seconds": self.global_timeout_seconds,
            "enable_automatic_fallback": self.enable_automatic_fallback,
            "enable_retry_logic": self.enable_retry_logic,
        }


# ==================== Agent Heartbeat & Health Monitoring ====================


class AgentHealthStatus(str, Enum):
    """Health status of an agent."""
    HEALTHY = "healthy"  # Operating normally
    DEGRADED = "degraded"  # Operating with issues
    UNHEALTHY = "unhealthy"  # Not responding properly
    OFFLINE = "offline"  # Not connected
    UNKNOWN = "unknown"  # Status unknown


class HeartbeatStatus(str, Enum):
    """Status of a heartbeat."""
    ACTIVE = "active"  # Heartbeat is active
    STALE = "stale"  # Heartbeat has expired
    STOPPED = "stopped"  # Heartbeat stopped
    MISSED = "missed"  # Heartbeat was missed


class AgentHeartbeat(BaseModel):
    """Heartbeat record for an agent."""
    heartbeat_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: AgentHealthStatus = AgentHealthStatus.UNKNOWN
    latency_ms: float = 0.0  # Response latency
    load: float = 0.0  # CPU/load percentage
    memory_mb: float = 0.0  # Memory usage
    active_tasks: int = 0  # Number of active tasks
    queue_depth: int = 0  # Number of pending tasks
    version: str = "1.0.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HeartbeatConfig(BaseModel):
    """Configuration for heartbeat monitoring."""
    config_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    interval_seconds: int = 30  # Heartbeat interval
    timeout_seconds: int = 120  # Consider dead after this
    max_missed_heartbeats: int = 3  # Max missed before marking unhealthy
    enable_monitoring: bool = True
    alert_on_degradation: bool = True
    alert_on_offline: bool = True
    health_check_url: Optional[str] = None
    custom_health_check: Optional[Dict[str, Any]] = None


class HealthCheckResult(BaseModel):
    """Result of a health check."""
    check_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    overall_status: AgentHealthStatus
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    
    def add_check(
        self,
        check_name: str,
        status: bool,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a health check result."""
        self.checks[check_name] = {
            "passed": status,
            "message": message,
            "details": details or {},
        }
        
        # Update overall status
        if not status:
            if self.overall_status == AgentHealthStatus.HEALTHY:
                self.overall_status = AgentHealthStatus.DEGRADED


class HealthMonitorConfig(BaseModel):
    """Configuration for health monitoring system."""
    monitor_id: str = Field(default_factory=lambda: str(uuid4()))
    global_interval_seconds: int = 30
    global_timeout_seconds: int = 120
    enable_auto_recovery: bool = False
    recovery_attempts: int = 3
    recovery_delay_seconds: int = 60
    alert_webhook_url: Optional[str] = None
    alert_email: Optional[str] = None
    metrics_retention_days: int = 7
    health_check_history_size: int = 100
    enable_metrics: bool = True


class AgentMetrics(BaseModel):
    """Metrics for an agent."""
    metrics_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    period_seconds: int = 60
    
    # Task metrics
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_timeout: int = 0
    tasks_retried: int = 0
    
    # Time metrics
    avg_execution_time_ms: float = 0.0
    min_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    total_execution_time_ms: float = 0.0
    
    # Queue metrics
    avg_queue_depth: float = 0.0
    max_queue_depth: int = 0
    
    # Error metrics
    error_count: int = 0
    error_types: Dict[str, int] = Field(default_factory=dict)
    
    # Success rate
    success_rate: float = 1.0
    
    def update_success_rate(self) -> None:
        """Calculate success rate."""
        total = self.tasks_completed + self.tasks_failed + self.tasks_timeout
        if total > 0:
            self.success_rate = self.tasks_completed / total


class HeartbeatRecord(BaseModel):
    """Record of a heartbeat event."""
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: HeartbeatStatus
    latency_ms: float = 0.0
    health_status: AgentHealthStatus
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentHealthMonitor(BaseModel):
    """Monitor for agent heartbeats and health."""
    monitor_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    agent_configs: Dict[str, HeartbeatConfig] = Field(default_factory=dict)
    heartbeats: Dict[str, AgentHeartbeat] = Field(default_factory=dict)  # agent_type -> latest heartbeat
    heartbeat_history: List[HeartbeatRecord] = Field(default_factory=list)
    health_checks: List[HealthCheckResult] = Field(default_factory=list)
    metrics: Dict[str, AgentMetrics] = Field(default_factory=dict)  # agent_type -> metrics
    config: HealthMonitorConfig = Field(default_factory=HealthMonitorConfig)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # ==================== Heartbeat Management ====================
    
    def register_agent(
        self,
        agent_type: AgentType,
        interval_seconds: int = 30,
        timeout_seconds: int = 120,
        max_missed_heartbeats: int = 3,
    ) -> HeartbeatConfig:
        """Register an agent for heartbeat monitoring."""
        config = HeartbeatConfig(
            agent_type=agent_type,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            max_missed_heartbeats=max_missed_heartbeats,
        )
        
        self.agent_configs[agent_type.value] = config
        self.last_updated = datetime.utcnow()
        
        return config
    
    def unregister_agent(self, agent_type: AgentType) -> bool:
        """Unregister an agent from heartbeat monitoring."""
        if agent_type.value in self.agent_configs:
            del self.agent_configs[agent_type.value]
            
            if agent_type in self.heartbeats:
                del self.heartbeats[agent_type]
            
            self.last_updated = datetime.utcnow()
            return True
        
        return False
    
    def record_heartbeat(
        self,
        agent_type: AgentType,
        status: AgentHealthStatus = AgentHealthStatus.UNKNOWN,
        latency_ms: float = 0.0,
        load: float = 0.0,
        memory_mb: float = 0.0,
        active_tasks: int = 0,
        queue_depth: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentHeartbeat:
        """Record a heartbeat from an agent."""
        heartbeat = AgentHeartbeat(
            agent_type=agent_type,
            status=status,
            latency_ms=latency_ms,
            load=load,
            memory_mb=memory_mb,
            active_tasks=active_tasks,
            queue_depth=queue_depth,
            metadata=metadata or {},
        )
        
        # Update latest heartbeat
        self.heartbeats[agent_type] = heartbeat
        
        # Determine heartbeat status
        config = self.agent_configs.get(agent_type.value)
        if config:
            heartbeat_status = HeartbeatStatus.ACTIVE
        else:
            heartbeat_status = HeartbeatStatus.STOPPED
        
        # Record in history
        record = HeartbeatRecord(
            agent_type=agent_type,
            status=heartbeat_status,
            latency_ms=latency_ms,
            health_status=status,
            message=f"Heartbeat received: {status.value}",
        )
        self.heartbeat_history.append(record)
        
        # Trim history if needed
        if len(self.heartbeat_history) > self.config.health_check_history_size:
            self.heartbeat_history = self.heartbeat_history[-self.config.health_check_history_size:]
        
        self.last_updated = datetime.utcnow()
        
        return heartbeat
    
    def check_heartbeat_status(self, agent_type: AgentType) -> Tuple[HeartbeatStatus, AgentHealthStatus]:
        """Check the status of an agent's heartbeat."""
        config = self.agent_configs.get(agent_type.value)
        if not config:
            return HeartbeatStatus.STOPPED, AgentHealthStatus.OFFLINE
        
        heartbeat = self.heartbeats.get(agent_type)
        if not heartbeat:
            return HeartbeatStatus.STOPPED, AgentHealthStatus.OFFLINE
        
        # Check if heartbeat is stale
        age_seconds = (datetime.utcnow() - heartbeat.timestamp).total_seconds()
        if age_seconds > config.timeout_seconds:
            return HeartbeatStatus.STALE, AgentHealthStatus.UNHEALTHY
        
        if age_seconds > config.interval_seconds * config.max_missed_heartbeats:
            return HeartbeatStatus.MISSED, AgentHealthStatus.UNHEALTHY
        
        return HeartbeatStatus.ACTIVE, heartbeat.status
    
    def get_heartbeat_age(self, agent_type: AgentType) -> float:
        """Get the age of an agent's last heartbeat in seconds."""
        heartbeat = self.heartbeats.get(agent_type)
        if not heartbeat:
            return float('inf')
        
        return (datetime.utcnow() - heartbeat.timestamp).total_seconds()
    
    def get_all_agent_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get the status of all monitored agents."""
        statuses = {}
        
        for agent_type in AgentType:
            if agent_type == AgentType.SUPERVISOR:
                continue
            
            heartbeat_status, health_status = self.check_heartbeat_status(agent_type)
            heartbeat = self.heartbeats.get(agent_type)
            
            statuses[agent_type.value] = {
                "heartbeat_status": heartbeat_status.value,
                "health_status": health_status.value,
                "last_heartbeat": heartbeat.timestamp.isoformat() if heartbeat else None,
                "latency_ms": heartbeat.latency_ms if heartbeat else None,
                "active_tasks": heartbeat.active_tasks if heartbeat else 0,
                "is_monitoring": agent_type.value in self.agent_configs,
            }
        
        return statuses
    
    # ==================== Health Check Management ====================
    
    def perform_health_check(
        self,
        agent_type: AgentType,
        checks: Optional[Dict[str, Callable[[], Tuple[bool, str]]]] = None,
    ) -> HealthCheckResult:
        """Perform a health check on an agent."""
        result = HealthCheckResult(
            agent_type=agent_type,
            overall_status=AgentHealthStatus.HEALTHY,
        )
        
        # Check heartbeat status
        heartbeat_status, health_status = self.check_heartbeat_status(agent_type)
        result.add_check(
            "heartbeat",
            heartbeat_status == HeartbeatStatus.ACTIVE,
            f"Heartbeat status: {heartbeat_status.value}",
        )
        
        # Check heartbeat age
        age = self.get_heartbeat_age(agent_type)
        config = self.agent_configs.get(agent_type.value)
        timeout = config.timeout_seconds if config else 120
        result.add_check(
            "heartbeat_freshness",
            age < timeout,
            f"Heartbeat age: {age:.1f}s (timeout: {timeout}s)",
            {"age_seconds": age, "timeout_seconds": timeout},
        )
        
        # Run custom checks if provided
        if checks:
            for check_name, check_func in checks.items():
                try:
                    passed, message = check_func()
                    result.add_check(check_name, passed, message)
                except Exception as e:
                    result.add_check(check_name, False, f"Error: {str(e)}")
        
        result.message = f"Health check completed: {result.overall_status.value}"
        
        # Store result
        self.health_checks.append(result)
        
        # Trim history if needed
        if len(self.health_checks) > self.config.health_check_history_size:
            self.health_checks = self.health_checks[-self.config.health_check_history_size:]
        
        self.last_updated = datetime.utcnow()
        
        return result
    
    def get_health_history(
        self,
        agent_type: Optional[AgentType] = None,
        limit: int = 10,
    ) -> List[HealthCheckResult]:
        """Get health check history."""
        results = self.health_checks
        
        if agent_type:
            results = [r for r in results if r.agent_type == agent_type]
        
        return results[-limit:]
    
    # ==================== Metrics Management ====================
    
    def record_task_completion(
        self,
        agent_type: AgentType,
        execution_time_ms: float,
        success: bool,
        error_type: Optional[str] = None,
    ) -> AgentMetrics:
        """Record task completion metrics."""
        if agent_type not in self.metrics:
            self.metrics[agent_type] = AgentMetrics(agent_type=agent_type)
        
        metrics = self.metrics[agent_type]
        
        if success:
            metrics.tasks_completed += 1
        else:
            metrics.tasks_failed += 1
            if error_type:
                metrics.error_types[error_type] = metrics.error_types.get(error_type, 0) + 1
        
        # Update time metrics
        metrics.total_execution_time_ms += execution_time_ms
        metrics.avg_execution_time_ms = metrics.total_execution_time_ms / (metrics.tasks_completed + metrics.tasks_failed)
        
        if metrics.min_execution_time_ms == 0 or execution_time_ms < metrics.min_execution_time_ms:
            metrics.min_execution_time_ms = execution_time_ms
        
        if execution_time_ms > metrics.max_execution_time_ms:
            metrics.max_execution_time_ms = execution_time_ms
        
        metrics.update_success_rate()
        
        self.last_updated = datetime.utcnow()
        
        return metrics
    
    def record_task_timeout(self, agent_type: AgentType) -> AgentMetrics:
        """Record a task timeout."""
        if agent_type not in self.metrics:
            self.metrics[agent_type] = AgentMetrics(agent_type=agent_type)
        
        metrics = self.metrics[agent_type]
        metrics.tasks_timeout += 1
        metrics.update_success_rate()
        
        self.last_updated = datetime.utcnow()
        
        return metrics
    
    def update_queue_metrics(
        self,
        agent_type: AgentType,
        queue_depth: int,
    ) -> None:
        """Update queue depth metrics."""
        if agent_type not in self.metrics:
            self.metrics[agent_type] = AgentMetrics(agent_type=agent_type)
        
        metrics = self.metrics[agent_type]
        
        if metrics.avg_queue_depth == 0:
            metrics.avg_queue_depth = queue_depth
        else:
            # Running average
            metrics.avg_queue_depth = (metrics.avg_queue_depth + queue_depth) / 2
        
        if queue_depth > metrics.max_queue_depth:
            metrics.max_queue_depth = queue_depth
        
        self.last_updated = datetime.utcnow()
    
    def get_agent_metrics(self, agent_type: AgentType) -> Optional[AgentMetrics]:
        """Get metrics for an agent."""
        return self.metrics.get(agent_type)
    
    def get_all_metrics(self) -> Dict[str, AgentMetrics]:
        """Get metrics for all agents."""
        return self.metrics
    
    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics across all agents."""
        if not self.metrics:
            return {}
        
        total_completed = sum(m.tasks_completed for m in self.metrics.values())
        total_failed = sum(m.tasks_failed for m in self.metrics.values())
        total_timeout = sum(m.tasks_timeout for m in self.metrics.values())
        total_execution_time = sum(m.total_execution_time_ms for m in self.metrics.values())
        
        return {
            "total_tasks_completed": total_completed,
            "total_tasks_failed": total_failed,
            "total_tasks_timeout": total_timeout,
            "overall_success_rate": total_completed / max(total_completed + total_failed, 1),
            "avg_execution_time_ms": total_execution_time / max(total_completed + total_failed, 1),
            "agents_monitored": len(self.metrics),
            "agent_details": {
                agent.value: {
                    "completed": m.tasks_completed,
                    "failed": m.tasks_failed,
                    "timeout": m.tasks_timeout,
                    "success_rate": m.success_rate,
                    "avg_time_ms": m.avg_execution_time_ms,
                }
                for agent, m in self.metrics.items()
            },
        }
    
    # ==================== Alerting ====================
    
    def check_for_alerts(self) -> List[Dict[str, Any]]:
        """Check for conditions that should trigger alerts."""
        alerts = []
        
        for agent_type in AgentType:
            if agent_type == AgentType.SUPERVISOR:
                continue
            
            # Check if agent is offline
            heartbeat_status, health_status = self.check_heartbeat_status(agent_type)
            
            if heartbeat_status in [HeartbeatStatus.STOPPED, HeartbeatStatus.MISSED]:
                if self.config.alert_on_offline:
                    alerts.append({
                        "type": "agent_offline",
                        "agent": agent_type.value,
                        "severity": "critical",
                        "message": f"Agent {agent_type.value} is offline",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            
            elif health_status == AgentHealthStatus.DEGRADED:
                if self.config.alert_on_degradation:
                    alerts.append({
                        "type": "agent_degraded",
                        "agent": agent_type.value,
                        "severity": "warning",
                        "message": f"Agent {agent_type.value} is degraded",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            
            # Check metrics for high failure rates
            metrics = self.metrics.get(agent_type)
            if metrics and metrics.success_rate < 0.5:
                alerts.append({
                    "type": "high_failure_rate",
                    "agent": agent_type.value,
                    "severity": "warning",
                    "message": f"Agent {agent_type.value} has high failure rate: {metrics.success_rate:.2%}",
                    "timestamp": datetime.utcnow().isoformat(),
                })
        
        return alerts
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of the monitor status."""
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0
        offline_count = 0
        
        for agent_type in AgentType:
            if agent_type == AgentType.SUPERVISOR:
                continue
            
            _, health_status = self.check_heartbeat_status(agent_type)
            
            if health_status == AgentHealthStatus.HEALTHY:
                healthy_count += 1
            elif health_status == AgentHealthStatus.DEGRADED:
                degraded_count += 1
            elif health_status == AgentHealthStatus.UNHEALTHY:
                unhealthy_count += 1
            elif health_status == AgentHealthStatus.OFFLINE:
                offline_count += 1
        
        return {
            "total_agents": healthy_count + degraded_count + unhealthy_count + offline_count,
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
            "offline": offline_count,
            "overall_status": (
                AgentHealthStatus.HEALTHY if healthy_count > 0 and unhealthy_count == 0 and offline_count == 0
                else AgentHealthStatus.DEGRADED if offline_count == 0
                else AgentHealthStatus.UNHEALTHY
            ),
            "alerts": self.check_for_alerts(),
            "last_updated": self.last_updated.isoformat(),
        }


# ==================== Context Sharing Models ====================


class ContextScope(str, Enum):
    """Scope of context for sharing."""
    GLOBAL = "global"  # Available to all agents
    PROJECT = "project"  # Project-level context
    WORKFLOW = "workflow"  # Workflow-specific context
    TASK = "task"  # Task-specific context
    AGENT = "agent"  # Agent-specific context


class ContextType(str, Enum):
    """Types of context that can be shared."""
    DECISION = "decision"  # Decision context
    REQUIREMENT = "requirement"  # Requirements context
    ARCHITECTURE = "architecture"  # Architecture context
    TECHNICAL = "technical"  # Technical constraints
    BUSINESS = "business"  # Business requirements
    USER = "user"  # User preferences
    HISTORY = "history"  # Conversation/decision history
    VALIDATION = "validation"  # Validation rules
    EXPORT = "export"  # Export configuration
    ANALYSIS = "analysis"  # Analysis results


class ContextEntry(BaseModel):
    """A single context entry for sharing."""
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    context_type: ContextType
    scope: ContextScope
    key: str  # Unique key within the scope
    value: Any
    source_agent: AgentType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: Optional[int] = None  # Time-to-live in seconds
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.ttl_seconds is None:
            return False
        
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    def access(self) -> None:
        """Record access to this entry."""
        self.access_count += 1
        self.last_accessed_at = datetime.utcnow()


class ContextBundle(BaseModel):
    """A collection of context entries for agent collaboration."""
    bundle_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    task_id: Optional[str] = None
    entries: Dict[str, ContextEntry] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    created_by: Optional[AgentType] = None
    target_agents: List[AgentType] = Field(default_factory=list)
    priority: int = 0
    is_complete: bool = False

    def add_entry(self, entry: ContextEntry) -> None:
        """Add an entry to the bundle."""
        self.entries[entry.entry_id] = entry
        self.updated_at = datetime.utcnow()
    
    def get_entries_by_type(self, context_type: ContextType) -> List[ContextEntry]:
        """Get all entries of a specific type."""
        return [e for e in self.entries.values() if e.context_type == context_type and not e.is_expired()]
    
    def get_entries_by_scope(self, scope: ContextScope) -> List[ContextEntry]:
        """Get all entries of a specific scope."""
        return [e for e in self.entries.values() if e.scope == scope and not e.is_expired()]
    
    def get_all_valid_entries(self) -> List[ContextEntry]:
        """Get all non-expired entries."""
        return [e for e in self.entries.values() if not e.is_expired()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bundle to dictionary."""
        return {
            "bundle_id": self.bundle_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "entries": {
                k: {
                    "entry_id": v.entry_id,
                    "context_type": v.context_type.value,
                    "scope": v.scope.value,
                    "key": v.key,
                    "value": v.value,
                    "source_agent": v.source_agent.value,
                    "version": v.version,
                    "metadata": v.metadata,
                }
                for k, v in self.entries.items()
            },
            "created_at": self.created_at.isoformat(),
            "version": self.version,
        }


class ContextSharingPolicy(BaseModel):
    """Policy defining how context can be shared."""
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    scope: ContextScope
    context_types: List[ContextType]  # Allowed context types
    source_agents: List[AgentType]  # Allowed source agents
    target_agents: List[AgentType]  # Allowed target agents
    requires_approval: bool = False
    approval_roles: List[str] = Field(default_factory=list)  # Roles that can approve
    can_modify: bool = True
    can_delete: bool = False
    ttl_seconds: Optional[int] = None
    encryption_required: bool = False
    audit_logging: bool = True

    def can_share(
        self,
        source_agent: AgentType,
        target_agent: AgentType,
        context_type: ContextType,
    ) -> bool:
        """Check if sharing is allowed by this policy."""
        if source_agent not in self.source_agents:
            return False
        
        if target_agent not in self.target_agents:
            return False
        
        if context_type not in self.context_types:
            return False
        
        return True


class ContextShareRequest(BaseModel):
    """Request to share context with agents."""
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    from_agent: AgentType
    to_agents: List[AgentType]
    context_type: ContextType
    scope: ContextScope = ContextScope.PROJECT
    context_key: str
    context_value: Any
    reason: str  # Reason for sharing
    metadata: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    requires_approval: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    status: str = "pending"  # pending, approved, rejected, expired
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class ContextShareRecord(BaseModel):
    """Record of a context share event."""
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    share_request_id: str
    from_agent: AgentType
    to_agent: AgentType
    context_entry_id: str
    shared_at: datetime = Field(default_factory=datetime.utcnow)
    access_granted: bool = True
    access_reason: Optional[str] = None
    used_in_task: Optional[str] = None
    audit_info: Dict[str, Any] = Field(default_factory=dict)


class ContextSharingManager(BaseModel):
    """Manager for context sharing between agents."""
    manager_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    context_store: Dict[str, ContextEntry] = Field(default_factory=dict)
    bundles: Dict[str, ContextBundle] = Field(default_factory=dict)
    policies: Dict[str, ContextSharingPolicy] = Field(default_factory=dict)
    share_requests: Dict[str, ContextShareRequest] = Field(default_factory=dict)
    share_records: List[ContextShareRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # ==================== Context Entry Management ====================
    
    def create_context_entry(
        self,
        context_type: ContextType,
        scope: ContextScope,
        key: str,
        value: Any,
        source_agent: AgentType,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextEntry:
        """Create a new context entry."""
        entry = ContextEntry(
            context_type=context_type,
            scope=scope,
            key=key,
            value=value,
            source_agent=source_agent,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )
        
        # Store entry with composite key
        store_key = f"{scope.value}:{context_type.value}:{key}"
        self.context_store[store_key] = entry
        self.updated_at = datetime.utcnow()
        
        return entry
    
    def get_context_entry(
        self,
        scope: ContextScope,
        context_type: ContextType,
        key: str,
    ) -> Optional[ContextEntry]:
        """Get a context entry by scope, type, and key."""
        store_key = f"{scope.value}:{context_type.value}:{key}"
        entry = self.context_store.get(store_key)
        
        if entry and not entry.is_expired():
            entry.access()
            return entry
        
        return None
    
    def get_context_by_scope(self, scope: ContextScope) -> List[ContextEntry]:
        """Get all context entries of a specific scope."""
        entries = []
        
        for entry in self.context_store.values():
            if entry.scope == scope and not entry.is_expired():
                entry.access()
                entries.append(entry)
        
        return entries
    
    def get_context_by_type(self, context_type: ContextType) -> List[ContextEntry]:
        """Get all context entries of a specific type."""
        entries = []
        
        for entry in self.context_store.values():
            if entry.context_type == context_type and not entry.is_expired():
                entry.access()
                entries.append(entry)
        
        return entries
    
    def update_context_entry(
        self,
        scope: ContextScope,
        context_type: ContextType,
        key: str,
        value: Any,
        source_agent: AgentType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ContextEntry]:
        """Update an existing context entry."""
        store_key = f"{scope.value}:{context_type.value}:{key}"
        
        if store_key in self.context_store:
            entry = self.context_store[store_key]
            entry.value = value
            entry.source_agent = source_agent
            entry.updated_at = datetime.utcnow()
            entry.version += 1
            
            if metadata:
                entry.metadata.update(metadata)
            
            self.updated_at = datetime.utcnow()
            return entry
        
        return None
    
    def delete_context_entry(
        self,
        scope: ContextScope,
        context_type: ContextType,
        key: str,
    ) -> bool:
        """Delete a context entry."""
        store_key = f"{scope.value}:{context_type.value}:{key}"
        
        if store_key in self.context_store:
            del self.context_store[store_key]
            self.updated_at = datetime.utcnow()
            return True
        
        return False
    
    def clear_expired_context(self) -> int:
        """Clear all expired context entries."""
        expired_keys = [
            k for k, v in self.context_store.items()
            if v.is_expired()
        ]
        
        for key in expired_keys:
            del self.context_store[key]
        
        self.updated_at = datetime.utcnow()
        return len(expired_keys)
    
    # ==================== Context Bundle Management ====================
    
    def create_bundle(
        self,
        project_id: str,
        task_id: Optional[str] = None,
        created_by: Optional[AgentType] = None,
        target_agents: Optional[List[AgentType]] = None,
    ) -> ContextBundle:
        """Create a new context bundle."""
        bundle = ContextBundle(
            project_id=project_id,
            task_id=task_id,
            created_by=created_by,
            target_agents=target_agents or [],
        )
        
        self.bundles[bundle.bundle_id] = bundle
        self.updated_at = datetime.utcnow()
        
        return bundle
    
    def add_to_bundle(
        self,
        bundle_id: str,
        context_type: ContextType,
        scope: ContextScope,
        key: str,
        value: Any,
        source_agent: AgentType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ContextEntry]:
        """Add a context entry to a bundle."""
        if bundle_id not in self.bundles:
            return None
        
        bundle = self.bundles[bundle_id]
        
        entry = self.create_context_entry(
            context_type=context_type,
            scope=scope,
            key=key,
            value=value,
            source_agent=source_agent,
            metadata=metadata,
        )
        
        bundle.add_entry(entry)
        return entry
    
    def get_bundle(self, bundle_id: str) -> Optional[ContextBundle]:
        """Get a context bundle by ID."""
        return self.bundles.get(bundle_id)
    
    def get_agent_bundle(
        self,
        agent_type: AgentType,
        project_id: str,
        task_id: Optional[str] = None,
    ) -> Optional[ContextBundle]:
        """Get the latest bundle for an agent."""
        for bundle in reversed(self.bundles.values()):
            if (
                agent_type in bundle.target_agents
                and bundle.project_id == project_id
                and (task_id is None or bundle.task_id == task_id)
            ):
                return bundle
        
        return None
    
    def finalize_bundle(self, bundle_id: str) -> bool:
        """Mark a bundle as complete."""
        if bundle_id in self.bundles:
            self.bundles[bundle_id].is_complete = True
            self.updated_at = datetime.utcnow()
            return True
        
        return False
    
    # ==================== Context Sharing Policy Management ====================
    
    def add_policy(self, policy: ContextSharingPolicy) -> None:
        """Add a context sharing policy."""
        self.policies[policy.policy_id] = policy
        self.updated_at = datetime.utcnow()
    
    def can_share_context(
        self,
        source_agent: AgentType,
        target_agent: AgentType,
        context_type: ContextType,
        scope: ContextScope,
    ) -> bool:
        """Check if context sharing is allowed."""
        for policy in self.policies.values():
            if policy.scope == scope:
                if policy.can_share(source_agent, target_agent, context_type):
                    return True
        
        # Default: allow sharing within project scope
        return scope == ContextScope.PROJECT
    
    # ==================== Context Share Requests ====================
    
    def create_share_request(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        context_type: ContextType,
        scope: ContextScope,
        context_key: str,
        context_value: Any,
        reason: str,
        priority: int = 0,
    ) -> ContextShareRequest:
        """Create a context share request."""
        request = ContextShareRequest(
            from_agent=from_agent,
            to_agents=to_agents,
            context_type=context_type,
            scope=scope,
            context_key=context_key,
            context_value=context_value,
            reason=reason,
            priority=priority,
        )
        
        # Check if approval is required
        for policy in self.policies.values():
            if policy.scope == scope and policy.requires_approval:
                if context_type in policy.context_types:
                    request.requires_approval = True
                    break
        
        self.share_requests[request.request_id] = request
        self.updated_at = datetime.utcnow()
        
        return request
    
    def approve_share_request(
        self,
        request_id: str,
        approved_by: str,
    ) -> bool:
        """Approve a context share request."""
        if request_id in self.share_requests:
            request = self.share_requests[request_id]
            request.status = "approved"
            request.approved_by = approved_by
            request.approved_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()
            return True
        
        return False
    
    def reject_share_request(self, request_id: str) -> bool:
        """Reject a context share request."""
        if request_id in self.share_requests:
            request = self.share_requests[request_id]
            request.status = "rejected"
            self.updated_at = datetime.utcnow()
            return True
        
        return False
    
    def get_share_request(self, request_id: str) -> Optional[ContextShareRequest]:
        """Get a share request by ID."""
        return self.share_requests.get(request_id)
    
    def get_pending_requests(self, agent_type: AgentType) -> List[ContextShareRequest]:
        """Get pending share requests for an agent."""
        return [
            r for r in self.share_requests.values()
            if agent_type in r.to_agents and r.status == "pending"
        ]
    
    # ==================== Context Sharing Records ====================
    
    def record_share(
        self,
        share_request_id: str,
        from_agent: AgentType,
        to_agent: AgentType,
        context_entry_id: str,
        used_in_task: Optional[str] = None,
        audit_info: Optional[Dict[str, Any]] = None,
    ) -> ContextShareRecord:
        """Record a context share event."""
        record = ContextShareRecord(
            share_request_id=share_request_id,
            from_agent=from_agent,
            to_agent=to_agent,
            context_entry_id=context_entry_id,
            used_in_task=used_in_task,
            audit_info=audit_info or {},
        )
        
        self.share_records.append(record)
        return record
    
    def get_share_history(
        self,
        context_entry_id: Optional[str] = None,
        agent_type: Optional[AgentType] = None,
    ) -> List[ContextShareRecord]:
        """Get share history filtered by criteria."""
        records = self.share_records
        
        if context_entry_id:
            records = [r for r in records if r.context_entry_id == context_entry_id]
        
        if agent_type:
            records = [r for r in records if r.from_agent == agent_type or r.to_agent == agent_type]
        
        return records
    
    # ==================== Utility Methods ====================
    
    def get_shared_context_for_agent(
        self,
        agent_type: AgentType,
        context_types: Optional[List[ContextType]] = None,
    ) -> Dict[str, Any]:
        """Get all shared context relevant to an agent."""
        shared = {}
        
        for entry in self.context_store.values():
            if entry.is_expired():
                continue
            
            if context_types and entry.context_type not in context_types:
                continue
            
            # Check if agent should have access
            if entry.scope in [ContextScope.GLOBAL, ContextScope.PROJECT]:
                entry.access()
                shared[f"{entry.context_type.value}:{entry.key}"] = entry.value
            elif entry.scope == ContextScope.AGENT:
                if hasattr(entry, 'target_agents') and agent_type in getattr(entry, 'target_agents', []):
                    entry.access()
                    shared[f"{entry.context_type.value}:{entry.key}"] = entry.value
        
        return shared
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about context sharing."""
        return {
            "total_entries": len(self.context_store),
            "valid_entries": sum(1 for e in self.context_store.values() if not e.is_expired()),
            "expired_entries": sum(1 for e in self.context_store.values() if e.is_expired()),
            "total_bundles": len(self.bundles),
            "completed_bundles": sum(1 for b in self.bundles.values() if b.is_complete),
            "pending_requests": sum(1 for r in self.share_requests.values() if r.status == "pending"),
            "total_share_records": len(self.share_records),
            "total_policies": len(self.policies),
            "access_statistics": {
                "total_accesses": sum(e.access_count for e in self.context_store.values()),
                "average_accesses": sum(e.access_count for e in self.context_store.values()) / max(len(self.context_store), 1),
            },
        }


# ==================== Message Protocol Types ====================


class MessageProtocolType(str, Enum):
    """Protocol types for agent communication."""
    REQUEST_RESPONSE = "request_response"  # Classic request/response pattern
    PUBLISH_SUBSCRIBE = "publish_subscribe"  # Pub/sub pattern for broadcasts
    PIPELINE = "pipeline"  # Sequential message processing
    BLACKBOARD = "blackboard"  # Shared message board pattern
    DIRECT = "direct"  # Direct agent-to-agent messaging


class MessagePriority(str, Enum):
    """Message priority levels."""
    CRITICAL = "critical"  # Immediate processing required
    HIGH = "high"  # Process before normal messages
    NORMAL = "normal"  # Standard priority
    LOW = "low"  # Can be deferred
    BACKGROUND = "background"  # Non-urgent processing


class MessageStatus(str, Enum):
    """Status of a message in the protocol."""
    PENDING = "pending"  # Message created but not sent
    SENT = "sent"  # Message sent to recipients
    DELIVERED = "delivered"  # Message received by recipients
    PROCESSING = "processing"  # Message being processed
    ACKNOWLEDGED = "acknowledged"  # Receipt acknowledged
    COMPLETED = "completed"  # Request fulfilled
    FAILED = "failed"  # Message processing failed
    EXPIRED = "expired"  # Message exceeded timeout


class MessageProtocolVersion(BaseModel):
    """Version information for message protocol."""
    major: int = 1
    minor: int = 0
    patch: int = 0
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def is_compatible(self, other: "MessageProtocolVersion") -> bool:
        """Check if another version is compatible."""
        return self.major == other.major


class MessageEnvelope(BaseModel):
    """Envelope containing message with protocol metadata."""
    envelope_id: str = Field(default_factory=lambda: str(uuid4()))
    protocol_type: MessageProtocolType = MessageProtocolType.DIRECT
    protocol_version: MessageProtocolVersion = Field(default_factory=MessageProtocolVersion)
    message: AgentMessage
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    correlation_id: Optional[str] = None  # For tracing related messages
    tracing_context: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


class MessageAcknowledgment(BaseModel):
    """Acknowledgment for a received message."""
    ack_id: str = Field(default_factory=lambda: str(uuid4()))
    envelope_id: str
    from_agent: AgentType
    received_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0
    status: MessageStatus = MessageStatus.DELIVERED
    error: Optional[str] = None


class RequestMessage(AgentMessage):
    """Request message with expected response type."""
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    action: str  # e.g., "validate_decision", "retrieve_context"
    expected_response_type: str = "result"  # "result", "approval", "information"
    timeout_seconds: int = 300
    requires_approval: bool = False
    approval_type: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    attachments: List[str] = Field(default_factory=list)  # References to data


class ResponseMessage(AgentMessage):
    """Response message to a request."""
    response_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str  # ID of the original request
    success: bool
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    partial_result: Optional[Dict[str, Any]] = None  # For streaming responses
    processing_info: Dict[str, Any] = Field(default_factory=dict)


class NotificationMessage(AgentMessage):
    """Notification message for events and updates."""
    notification_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str  # e.g., "decision_created", "artifact_generated"
    event_category: str = "general"  # "workflow", "data", "system", "user"
    importance: MessagePriority = MessagePriority.NORMAL
    requires_action: bool = False
    action_url: Optional[str] = None
    affected_resources: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryMessage(AgentMessage):
    """Query message for information retrieval."""
    query_id: str = Field(default_factory=lambda: str(uuid4()))
    query_type: str  # e.g., "semantic_search", "fact_lookup"
    query_text: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    pagination: Dict[str, Any] = Field(default_factory=dict)  # limit, offset
    sort_options: Dict[str, Any] = Field(default_factory=dict)
    expected_results: int = 10
    search_scope: str = "local"  # "local", "global", "project"


class QueryResultMessage(AgentMessage):
    """Result message for a query."""
    result_id: str = Field(default_factory=lambda: str(uuid4()))
    query_id: str
    total_results: int
    results: List[Dict[str, Any]] = Field(default_factory=list)
    relevance_scores: Dict[str, float] = Field(default_factory=dict)
    search_metadata: Dict[str, Any] = Field(default_factory=dict)
    next_cursor: Optional[str] = None


class MessageHandler(BaseModel):
    """Handler for a specific message type."""
    handler_id: str = Field(default_factory=lambda: str(uuid4()))
    message_type: str  # Type of message this handler processes
    handler_function: str  # Name of the handler function
    agent_types: List[AgentType]  # Agents that can use this handler
    priority: int = 0
    timeout_seconds: int = 300
    retry_on_failure: bool = True
    max_retries: int = 3
    error_handler: Optional[str] = None


class MessageProtocol(BaseModel):
    """Protocol definition for agent communication."""
    protocol_id: str = Field(default_factory=lambda: str(uuid4()))
    protocol_type: MessageProtocolType
    version: MessageProtocolVersion = Field(default_factory=MessageProtocolVersion)
    handlers: Dict[str, MessageHandler] = Field(default_factory=dict)
    default_timeout: int = 300
    max_message_size: int = 1024 * 1024  # 1MB
    compression_enabled: bool = False
    encryption_enabled: bool = False
    acknowledgment_required: bool = True
    message_logging: bool = True


class MessageRouter(BaseModel):
    """Router for directing messages to appropriate handlers."""
    router_id: str = Field(default_factory=lambda: str(uuid4()))
    routing_rules: List[Dict[str, Any]] = Field(default_factory=list)
    default_handler: Optional[str] = None
    fallback_handlers: Dict[str, str] = Field(default_factory=dict)
    routing_strategy: str = "priority"  # "priority", "round_robin", "load_based"

    def route_message(
        self,
        message: AgentMessage,
        available_handlers: List[str],
    ) -> Optional[str]:
        """Determine which handler should process the message."""
        for rule in self.routing_rules:
            if self._matches_rule(message, rule):
                handler = rule.get("handler")
                if handler in available_handlers:
                    return handler
        
        return self.default_handler if self.default_handler in available_handlers else None
    
    def _matches_rule(self, message: AgentMessage, rule: Dict[str, Any]) -> bool:
        """Check if a message matches a routing rule."""
        message_type = rule.get("message_type")
        to_agents = rule.get("to_agents")
        priority = rule.get("priority")
        
        if message_type and message.message_type != message_type:
            return False
        
        if to_agents and message.to_agents:
            if not any(a in to_agents for a in message.to_agents):
                return False
        
        if priority and hasattr(message, "priority"):
            if message.priority != priority:
                return False
        
        return True


class MessageDeliveryStatus(BaseModel):
    """Status of message delivery."""
    delivery_id: str = Field(default_factory=lambda: str(uuid4()))
    envelope_id: str
    recipient: AgentType
    status: MessageStatus
    attempts: int = 1
    last_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    error: Optional[str] = None


class MessageProtocolManager(BaseModel):
    """Manager for message protocols between agents."""
    manager_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    protocols: Dict[str, MessageProtocol] = Field(default_factory=dict)
    routers: Dict[str, MessageRouter] = Field(default_factory=dict)
    envelope_store: Dict[str, MessageEnvelope] = Field(default_factory=dict)
    delivery_status: Dict[str, List[MessageDeliveryStatus]] = Field(default_factory=dict)
    acknowledgments: Dict[str, MessageAcknowledgment] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def create_envelope(
        self,
        message: AgentMessage,
        protocol_type: MessageProtocolType = MessageProtocolType.DIRECT,
        priority: MessagePriority = MessagePriority.NORMAL,
        timeout_seconds: Optional[int] = None,
    ) -> MessageEnvelope:
        """Create an envelope for a message."""
        envelope = MessageEnvelope(
            protocol_type=protocol_type,
            message=message,
            priority=priority,
            correlation_id=self._generate_correlation_id(),
        )
        
        if timeout_seconds:
            envelope.expires_at = datetime.utcnow() + datetime.timedelta(seconds=timeout_seconds)
        
        self.envelope_store[envelope.envelope_id] = envelope
        return envelope
    
    def _generate_correlation_id(self) -> str:
        """Generate a correlation ID for message tracing."""
        return str(uuid4())
    
    def send_request(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        action: str,
        content: Dict[str, Any],
        expected_response_type: str = "result",
        timeout_seconds: int = 300,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> RequestMessage:
        """Send a request message to agents."""
        request = RequestMessage(
            from_agent=from_agent,
            to_agents=to_agents,
            message_type="request",
            content=content,
            action=action,
            expected_response_type=expected_response_type,
            timeout_seconds=timeout_seconds,
            priority=priority,
        )
        
        envelope = self.create_envelope(request, MessageProtocolType.REQUEST_RESPONSE, priority, timeout_seconds)
        return request
    
    def send_response(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        request_id: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ResponseMessage:
        """Send a response to a request."""
        response = ResponseMessage(
            from_agent=from_agent,
            to_agents=to_agents,
            message_type="response",
            content={"success": success},
            request_id=request_id,
            success=success,
            result=result,
            error_code=error_code,
            error_message=error_message,
        )
        return response
    
    def send_notification(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        event_type: str,
        event_category: str = "general",
        importance: MessagePriority = MessagePriority.NORMAL,
        requires_action: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationMessage:
        """Send a notification to agents."""
        notification = NotificationMessage(
            from_agent=from_agent,
            to_agents=to_agents,
            message_type="notification",
            content={},
            event_type=event_type,
            event_category=event_category,
            importance=importance,
            requires_action=requires_action,
            metadata=metadata or {},
        )
        
        envelope = self.create_envelope(notification, MessageProtocolType.PUBLISH_SUBSCRIBE, importance)
        return notification
    
    def send_query(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        query_type: str,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        expected_results: int = 10,
        search_scope: str = "local",
    ) -> QueryMessage:
        """Send a query to agents."""
        query = QueryMessage(
            from_agent=from_agent,
            to_agents=to_agents,
            message_type="query",
            content={},
            query_type=query_type,
            query_text=query_text,
            filters=filters or {},
            expected_results=expected_results,
            search_scope=search_scope,
        )
        
        envelope = self.create_envelope(query, MessageProtocolType.PUBLISH_SUBSCRIBE)
        return query
    
    def acknowledge_message(
        self,
        envelope_id: str,
        from_agent: AgentType,
        processing_time_ms: float = 0.0,
        status: MessageStatus = MessageStatus.DELIVERED,
        error: Optional[str] = None,
    ) -> MessageAcknowledgment:
        """Acknowledge receipt of a message."""
        ack = MessageAcknowledgment(
            envelope_id=envelope_id,
            from_agent=from_agent,
            processing_time_ms=processing_time_ms,
            status=status,
            error=error,
        )
        
        self.acknowledgments[ack.ack_id] = ack
        
        if envelope_id in self.envelope_store:
            envelope = self.envelope_store[envelope_id]
            envelope.status = MessageStatus.ACKNOWLEDGED
        
        return ack
    
    def record_delivery_status(
        self,
        envelope_id: str,
        recipient: AgentType,
        status: MessageStatus,
        error: Optional[str] = None,
    ) -> MessageDeliveryStatus:
        """Record the delivery status for a message."""
        delivery = MessageDeliveryStatus(
            envelope_id=envelope_id,
            recipient=recipient,
            status=status,
            last_attempt_at=datetime.utcnow(),
            error=error,
        )
        
        if envelope_id not in self.delivery_status:
            self.delivery_status[envelope_id] = []
        self.delivery_status[envelope_id].append(delivery)
        
        # Update envelope status
        if envelope_id in self.envelope_store:
            envelope = self.envelope_store[envelope_id]
            envelope.status = status
        
        return delivery
    
    def check_envelope_status(self, envelope_id: str) -> Optional[MessageEnvelope]:
        """Check the status of an envelope."""
        return self.envelope_store.get(envelope_id)
    
    def check_expiring_envelopes(self, threshold_seconds: int = 60) -> List[MessageEnvelope]:
        """Check for envelopes that will expire soon."""
        threshold = datetime.utcnow() + datetime.timedelta(seconds=threshold_seconds)
        expiring = []
        
        for envelope in self.envelope_store.values():
            if envelope.expires_at and envelope.expires_at <= threshold:
                if envelope.status not in [MessageStatus.COMPLETED, MessageStatus.FAILED, MessageStatus.EXPIRED]:
                    expiring.append(envelope)
        
        return expiring
    
    def expire_envelopes(self) -> int:
        """Mark expired envelopes as expired."""
        expired_count = 0
        now = datetime.utcnow()
        
        for envelope in self.envelope_store.values():
            if envelope.expires_at and envelope.expires_at <= now:
                if envelope.status not in [MessageStatus.COMPLETED, MessageStatus.FAILED]:
                    envelope.status = MessageStatus.EXPIRED
                    expired_count += 1
        
        return expired_count
    
    def get_pending_requests(self, agent_type: AgentType) -> List[RequestMessage]:
        """Get pending requests for an agent."""
        pending = []
        for envelope in self.envelope_store.values():
            if isinstance(envelope.message, RequestMessage):
                if agent_type in envelope.message.to_agents:
                    if envelope.status in [MessageStatus.SENT, MessageStatus.DELIVERED]:
                        pending.append(envelope.message)
        return pending
    
    def get_pending_responses(self, request_id: str) -> List[ResponseMessage]:
        """Get pending responses for a request."""
        pending = []
        for envelope in self.envelope_store.values():
            if isinstance(envelope.message, ResponseMessage):
                if envelope.message.request_id == request_id:
                    pending.append(envelope.message)
        return pending
    
    def clear_completed_envelopes(self, max_age_hours: int = 24) -> int:
        """Clear completed/expired envelopes older than specified age."""
        threshold = datetime.utcnow() - datetime.timedelta(hours=max_age_hours)
        cleared = 0
        
        to_remove = []
        for envelope_id, envelope in self.envelope_store.items():
            if envelope.status in [MessageStatus.COMPLETED, MessageStatus.FAILED, MessageStatus.EXPIRED]:
                if envelope.timestamp <= threshold:
                    to_remove.append(envelope_id)
        
        for envelope_id in to_remove:
            del self.envelope_store[envelope_id]
            if envelope_id in self.delivery_status:
                del self.delivery_status[envelope_id]
            cleared += 1
        
        return cleared


# ==================== Shared State Models ====================


class SharedStateScope(str, Enum):
    """Scope for shared state visibility."""
    GLOBAL = "global"  # Visible to all agents
    PROJECT = "project"  # Visible within a project
    WORKFLOW = "workflow"  # Visible within a workflow
    AGENT = "agent"  # Visible only to specific agent


class SharedStateUpdate(BaseModel):
    """Record of a shared state update."""
    update_id: str = Field(default_factory=lambda: str(uuid4()))
    key: str
    value: Any
    source_agent: AgentType
    scope: SharedStateScope = SharedStateScope.GLOBAL
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SharedStateEntry(BaseModel):
    """Entry in the shared state store."""
    key: str
    value: Any
    scope: SharedStateScope
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    source_agent: Optional[AgentType] = None
    subscribers: List[AgentType] = Field(default_factory=list)
    history: List[SharedStateUpdate] = Field(default_factory=list)

    def update(
        self,
        value: Any,
        source_agent: AgentType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SharedStateUpdate:
        """Update the entry value."""
        update = SharedStateUpdate(
            key=self.key,
            value=value,
            source_agent=source_agent,
            scope=self.scope,
            version=self.version + 1,
            metadata=metadata or {},
        )
        self.value = value
        self.updated_at = datetime.utcnow()
        self.version = update.version
        self.source_agent = source_agent
        self.history.append(update)
        return update


class SharedStateStore(BaseModel):
    """Shared state store for agent communication."""
    store_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    entries: Dict[str, SharedStateEntry] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    global_version: int = 1
    
    def set(
        self,
        key: str,
        value: Any,
        source_agent: AgentType,
        scope: SharedStateScope = SharedStateScope.GLOBAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SharedStateUpdate:
        """Set a value in the shared state."""
        if key in self.entries:
            entry = self.entries[key]
            return entry.update(value, source_agent, metadata)
        else:
            entry = SharedStateEntry(
                key=key,
                value=value,
                scope=scope,
                source_agent=source_agent,
            )
            self.entries[key] = entry
            self.updated_at = datetime.utcnow()
            self.global_version += 1
            return SharedStateUpdate(
                key=key,
                value=value,
                source_agent=source_agent,
                scope=scope,
                version=1,
                metadata=metadata or {},
            )
    
    def get(self, key: str, scope: Optional[SharedStateScope] = None) -> Optional[Any]:
        """Get a value from the shared state."""
        entry = self.entries.get(key)
        if entry is None:
            return None
        if scope is not None and entry.scope != scope:
            return None
        return entry.value
    
    def get_entry(self, key: str) -> Optional[SharedStateEntry]:
        """Get the full entry for a key."""
        return self.entries.get(key)
    
    def delete(self, key: str) -> bool:
        """Delete a key from the shared state."""
        if key in self.entries:
            del self.entries[key]
            self.updated_at = datetime.utcnow()
            self.global_version += 1
            return True
        return False
    
    def get_by_scope(self, scope: SharedStateScope) -> Dict[str, Any]:
        """Get all entries with a specific scope."""
        return {
            key: entry.value
            for key, entry in self.entries.items()
            if entry.scope == scope
        }
    
    def get_updates_since(self, version: int) -> List[SharedStateUpdate]:
        """Get all updates since a specific version."""
        updates = []
        for entry in self.entries.values():
            for update in entry.history:
                if update.version > version:
                    updates.append(update)
        return sorted(updates, key=lambda u: u.version)
    
    def subscribe(
        self,
        key: str,
        agent: AgentType,
    ) -> bool:
        """Subscribe an agent to changes on a key."""
        entry = self.entries.get(key)
        if entry and agent not in entry.subscribers:
            entry.subscribers.append(agent)
            return True
        return False
    
    def unsubscribe(self, key: str, agent: AgentType) -> bool:
        """Unsubscribe an agent from changes on a key."""
        entry = self.entries.get(key)
        if entry and agent in entry.subscribers:
            entry.subscribers.remove(agent)
            return True
        return False
    
    def get_subscribers(self, key: str) -> List[AgentType]:
        """Get all subscribers for a key."""
        entry = self.entries.get(key)
        return entry.subscribers if entry else []
    
    def get_all(self) -> Dict[str, Any]:
        """Get all shared state values."""
        return {key: entry.value for key, entry in self.entries.items()}
    
    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()
        self.updated_at = datetime.utcnow()
        self.global_version += 1


class AgentMessage(BaseModel):
    """Message passed between agents."""
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    from_agent: AgentType
    to_agents: List[AgentType]
    message_type: str  # e.g., "request", "response", "notification", "query"
    content: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reply_to: Optional[str] = None  # Message ID to reply to
    priority: int = 0
    requires_ack: bool = False


class MessageQueue(BaseModel):
    """Queue for messages between agents."""
    queue_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    messages: List[AgentMessage] = Field(default_factory=list)
    pending_responses: Dict[str, AgentMessage] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def send_message(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        message_type: str,
        content: Dict[str, Any],
        reply_to: Optional[str] = None,
        priority: int = 0,
        requires_ack: bool = False,
    ) -> AgentMessage:
        """Send a message to agents."""
        message = AgentMessage(
            from_agent=from_agent,
            to_agents=to_agents,
            message_type=message_type,
            content=content,
            reply_to=reply_to,
            priority=priority,
            requires_ack=requires_ack,
        )
        self.messages.append(message)
        return message
    
    def get_messages_for_agent(self, agent: AgentType) -> List[AgentMessage]:
        """Get all messages for a specific agent."""
        return [m for m in self.messages if agent in m.to_agents]
    
    def get_unread_for_agent(self, agent: AgentType) -> List[AgentMessage]:
        """Get unread messages for an agent."""
        return [m for m in self.messages if agent in m.to_agents and not m.content.get("_read", False)]
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        for message in self.messages:
            if message.message_id == message_id:
                message.content["_read"] = True
                return True
        return False
    
    def reply_to_message(
        self,
        original_message_id: str,
        from_agent: AgentType,
        content: Dict[str, Any],
    ) -> Optional[AgentMessage]:
        """Reply to a specific message."""
        original = self.pending_responses.get(original_message_id)
        if not original:
            # Find in messages
            for msg in self.messages:
                if msg.message_id == original_message_id:
                    original = msg
                    break
        
        if original:
            return self.send_message(
                from_agent=from_agent,
                to_agents=[original.from_agent],
                message_type="response",
                content=content,
                reply_to=original_message_id,
            )
        return None
    
    def get_messages_by_type(self, message_type: str) -> List[AgentMessage]:
        """Get all messages of a specific type."""
        return [m for m in self.messages if m.message_type == message_type]
    
    def get_pending_responses(self, message_id: str) -> List[AgentMessage]:
        """Get pending responses to a message."""
        return [m for m in self.messages if m.reply_to == message_id]
    
    def clear_processed(self, agent: AgentType) -> int:
        """Clear processed messages for an agent."""
        count = 0
        to_remove = []
        for message in self.messages:
            if agent in message.to_agents and message.content.get("_read", False):
                to_remove.append(message)
        for msg in to_remove:
            if msg in self.messages:
                self.messages.remove(msg)
                count += 1
        return count


# ==================== Supervisor Agent ====================

class SupervisorAgent:
    """
    Supervisor Agent that orchestrates all other agents.
    
    Responsibilities:
    1. Coordinate workflow between agents
    2. Route tasks to appropriate agents
    3. Handle interrupts and errors
    4. Monitor agent completion
    5. Aggregate results from agents
    """
    
    def __init__(
        self,
        config: Optional[SupervisorConfig] = None,
        interrupt_manager: Optional[InterruptManager] = None,
    ):
        """
        Initialize the supervisor agent.
        
        Args:
            config: Supervisor configuration
            interrupt_manager: Optional interrupt manager for HITL
        """
        self.config = config or SupervisorConfig()
        self.interrupt_manager = interrupt_manager or InterruptManager()
        self.status = SupervisorStatus.IDLE
        self.graph: Optional[StateGraph] = None
        self.agent_results: Dict[str, AgentResult] = {}
        self.supervisor_decisions: List[SupervisorDecision] = []
        self._callbacks: Dict[str, Callable] = {}
        self._pending_delegations: Dict[str, TaskDelegation] = {}
        self._delegation_history: List[TaskDelegation] = []
        
        # Shared state for agent communication
        self._shared_state_store: Optional[SharedStateStore] = None
        self._message_queue: Optional[MessageQueue] = None
        self._state_subscribers: Dict[str, Set[Callable]] = {}
        self._lock = threading.Lock()
        
        # Message protocol manager
        self._protocol_manager: Optional[MessageProtocolManager] = None
        
        # Context sharing manager
        self._context_sharing_manager: Optional[ContextSharingManager] = None
        
        # Health monitor
        self._health_monitor: Optional[AgentHealthMonitor] = None
        
        # Timeout manager
        self._timeout_manager: Optional[TimeoutManager] = None
    
    # ==================== Shared State Methods ====================
    
    def initialize_shared_state(self, project_id: str) -> SharedStateStore:
        """
        Initialize the shared state store for a project.
        
        Args:
            project_id: Project identifier
        
        Returns:
            SharedStateStore instance
        """
        with self._lock:
            self._shared_state_store = SharedStateStore(project_id=project_id)
            self._message_queue = MessageQueue(project_id=project_id)
            self._state_subscribers = {
                "global": set(),
                "project": set(),
                "workflow": set(),
            }
            return self._shared_state_store
    
    def get_shared_state_store(self) -> Optional[SharedStateStore]:
        """Get the current shared state store."""
        return self._shared_state_store
    
    def set_shared_state(
        self,
        key: str,
        value: Any,
        agent_type: AgentType,
        scope: SharedStateScope = SharedStateScope.GLOBAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SharedStateUpdate]:
        """
        Set a value in the shared state.
        
        Args:
            key: State key
            value: Value to store
            agent_type: Agent setting the value
            scope: Visibility scope
            metadata: Optional metadata
        
        Returns:
            SharedStateUpdate if successful, None otherwise
        """
        if not self._shared_state_store:
            return None
        
        update = self._shared_state_store.set(
            key=key,
            value=value,
            source_agent=agent_type,
            scope=scope,
            metadata=metadata,
        )
        
        # Notify subscribers
        self._notify_state_subscribers(key, update)
        
        return update
    
    def get_shared_state(
        self,
        key: str,
        scope: Optional[SharedStateScope] = None,
    ) -> Optional[Any]:
        """
        Get a value from the shared state.
        
        Args:
            key: State key
            scope: Optional scope filter
        
        Returns:
            Value if found, None otherwise
        """
        if not self._shared_state_store:
            return None
        
        return self._shared_state_store.get(key, scope)
    
    def get_all_shared_state(self) -> Dict[str, Any]:
        """Get all shared state values."""
        if not self._shared_state_store:
            return {}
        
        return self._shared_state_store.get_all()
    
    def delete_shared_state(self, key: str) -> bool:
        """
        Delete a key from shared state.
        
        Args:
            key: State key to delete
        
        Returns:
            True if deleted, False otherwise
        """
        if not self._shared_state_store:
            return False
        
        return self._shared_state_store.delete(key)
    
    def subscribe_to_state(
        self,
        key: str,
        callback: Callable[[SharedStateUpdate], None],
    ) -> bool:
        """
        Subscribe to changes on a state key.
        
        Args:
            key: State key to subscribe to
            callback: Callback function
        
        Returns:
            True if subscribed, False otherwise
        """
        if key not in self._state_subscribers:
            self._state_subscribers[key] = set()
        
        self._state_subscribers[key].add(callback)
        return True
    
    def unsubscribe_from_state(
        self,
        key: str,
        callback: Callable[[SharedStateUpdate], None],
    ) -> bool:
        """
        Unsubscribe from state changes.
        
        Args:
            key: State key
            callback: Callback function
        
        Returns:
            True if unsubscribed, False otherwise
        """
        if key in self._state_subscribers:
            self._state_subscribers[key].discard(callback)
            return True
        return False
    
    def _notify_state_subscribers(self, key: str, update: SharedStateUpdate) -> None:
        """Notify all subscribers of a state change."""
        # Notify specific key subscribers
        if key in self._state_subscribers:
            for callback in list(self._state_subscribers[key]):
                try:
                    callback(update)
                except Exception:
                    pass  # Don't let subscriber errors break the flow
        
        # Notify scope subscribers
        if update.scope in self._state_subscribers:
            for callback in list(self._state_subscribers[update.scope]):
                try:
                    callback(update)
                except Exception:
                    pass
    
    def get_state_history(self, key: str) -> List[SharedStateUpdate]:
        """Get the history of changes for a key."""
        if not self._shared_state_store:
            return []
        
        entry = self._shared_state_store.get_entry(key)
        return entry.history if entry else []
    
    def get_state_version(self, key: str) -> Optional[int]:
        """Get the current version of a key."""
        if not self._shared_state_store:
            return None
        
        entry = self._shared_state_store.get_entry(key)
        return entry.version if entry else None
    
    # ==================== Message Passing Methods ====================
    
    def get_message_queue(self) -> Optional[MessageQueue]:
        """Get the current message queue."""
        return self._message_queue
    
    def send_message(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        message_type: str,
        content: Dict[str, Any],
        priority: int = 0,
        requires_ack: bool = False,
    ) -> Optional[AgentMessage]:
        """
        Send a message to agents.
        
        Args:
            from_agent: Sending agent
            to_agents: Target agents
            message_type: Type of message
            content: Message content
            priority: Message priority
            requires_ack: Whether acknowledgment is required
        
        Returns:
            AgentMessage if sent, None otherwise
        """
        if not self._message_queue:
            return None
        
        return self._message_queue.send_message(
            from_agent=from_agent,
            to_agents=to_agents,
            message_type=message_type,
            content=content,
            priority=priority,
            requires_ack=requires_ack,
        )
    
    def broadcast_message(
        self,
        from_agent: AgentType,
        message_type: str,
        content: Dict[str, Any],
        priority: int = 0,
    ) -> Optional[AgentMessage]:
        """
        Broadcast a message to all agents.
        
        Args:
            from_agent: Sending agent
            message_type: Type of message
            content: Message content
            priority: Message priority
        
        Returns:
            AgentMessage if sent, None otherwise
        """
        all_agents = [
            AgentType.INTERROGATION,
            AgentType.SPECIFICATION,
            AgentType.VALIDATION,
            AgentType.CONTEXT_MEMORY,
            AgentType.DELIVERY,
        ]
        return self.send_message(
            from_agent=from_agent,
            to_agents=[a for a in all_agents if a != from_agent],
            message_type=message_type,
            content=content,
            priority=priority,
        )
    
    def get_messages(self, agent: AgentType) -> List[AgentMessage]:
        """Get all messages for an agent."""
        if not self._message_queue:
            return []
        
        return self._message_queue.get_messages_for_agent(agent)
    
    def get_unread_messages(self, agent: AgentType) -> List[AgentMessage]:
        """Get unread messages for an agent."""
        if not self._message_queue:
            return []
        
        return self._message_queue.get_unread_for_agent(agent)
    
    def mark_message_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        if not self._message_queue:
            return False
        
        return self._message_queue.mark_as_read(message_id)
    
    def reply_to_message(
        self,
        original_message_id: str,
        from_agent: AgentType,
        content: Dict[str, Any],
    ) -> Optional[AgentMessage]:
        """Reply to a specific message."""
        if not self._message_queue:
            return None
        
        return self._message_queue.reply_to_message(
            original_message_id=original_message_id,
            from_agent=from_agent,
            content=content,
        )
    
    def request_context_from_agent(
        self,
        requesting_agent: AgentType,
        target_agent: AgentType,
        context_type: str,
        query: str,
    ) -> Optional[AgentMessage]:
        """
        Request context from another agent.
        
        Args:
            requesting_agent: Agent requesting context
            target_agent: Agent to request context from
            context_type: Type of context requested
            query: Query description
        
        Returns:
            Sent message if successful, None otherwise
        """
        return self.send_message(
            from_agent=requesting_agent,
            to_agents=[target_agent],
            message_type="context_request",
            content={
                "context_type": context_type,
                "query": query,
            },
            priority=5,
            requires_ack=True,
        )
    
    def share_context_with_agents(
        self,
        sharing_agent: AgentType,
        context_data: Dict[str, Any],
        target_agents: Optional[List[AgentType]] = None,
    ) -> Optional[AgentMessage]:
        """
        Share context data with other agents.
        
        Args:
            sharing_agent: Agent sharing context
            context_data: Context data to share
            target_agents: Optional specific agents to share with
        
        Returns:
            Sent message if successful, None otherwise
        """
        return self.send_message(
            from_agent=sharing_agent,
            to_agents=target_agents or [
                AgentType.INTERROGATION,
                AgentType.SPECIFICATION,
                AgentType.VALIDATION,
                AgentType.CONTEXT_MEMORY,
                AgentType.DELIVERY,
            ],
            message_type="context_share",
            content=context_data,
            priority=3,
            requires_ack=False,
        )
    
    def notify_agent_completion(
        self,
        completed_agent: AgentType,
        result_summary: Dict[str, Any],
    ) -> Optional[AgentMessage]:
        """
        Notify other agents that an agent has completed.
        
        Args:
            completed_agent: Agent that completed
            result_summary: Summary of results
        
        Returns:
            Sent message if successful, None otherwise
        """
        return self.broadcast_message(
            from_agent=completed_agent,
            message_type="agent_completion",
            content=result_summary,
            priority=2,
        )
    
    def request_validation(
        self,
        requesting_agent: AgentType,
        validation_type: str,
        data_to_validate: Dict[str, Any],
    ) -> Optional[AgentMessage]:
        """
        Request validation from ValidationAgent.
        
        Args:
            requesting_agent: Agent requesting validation
            validation_type: Type of validation
            data_to_validate: Data to validate
        
        Returns:
            Sent message if successful, None otherwise
        """
        return self.send_message(
            from_agent=requesting_agent,
            to_agents=[AgentType.VALIDATION],
            message_type="validation_request",
            content={
                "validation_type": validation_type,
                "data": data_to_validate,
            },
            priority=7,
            requires_ack=True,
        )
    
    def propagate_agent_results(
        self,
        source_agent: AgentType,
        results: Dict[str, Any],
    ) -> None:
        """
        Propagate agent results to shared state and notify.
        
        Args:
            source_agent: Agent that produced results
            results: Results to propagate
        """
        # Store in shared state
        self.set_shared_state(
            key=f"agent_results:{source_agent.value}",
            value=results,
            agent_type=source_agent,
            scope=SharedStateScope.PROJECT,
            metadata={"timestamp": datetime.utcnow().isoformat()},
        )
        
        # Broadcast completion
        self.notify_agent_completion(
            completed_agent=source_agent,
            result_summary={
                "agent": source_agent.value,
                "result_keys": list(results.keys()),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    
    # ==================== State Propagation Methods ====================
    
    def sync_state_to_agent(
        self,
        agent_type: AgentType,
        state_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Sync relevant shared state to an agent.
        
        Args:
            agent_type: Agent to sync state to
            state_keys: Specific keys to sync (None for all relevant)
        
        Returns:
            Dictionary of state relevant to the agent
        """
        if not self._shared_state_store:
            return {}
        
        relevant_state: Dict[str, Any] = {}
        
        for key, entry in self._shared_state_store.entries.items():
            # Check if agent should receive this key
            if entry.scope == SharedStateScope.AGENT:
                # Only send if this agent is the subscriber
                if agent_type not in entry.subscribers:
                    continue
            
            # Include the key
            if state_keys is None or key in state_keys:
                relevant_state[key] = {
                    "value": entry.value,
                    "version": entry.version,
                    "updated_at": entry.updated_at.isoformat(),
                    "source": entry.source_agent.value if entry.source_agent else None,
                }
        
        return relevant_state
    
    def get_agent_contribution(self, agent_type: AgentType) -> Optional[Dict[str, Any]]:
        """Get an agent's contribution from shared state."""
        return self.get_shared_state(f"agent_results:{agent_type.value}")
    
    def get_all_contributions(self) -> Dict[str, Any]:
        """Get all agent contributions from shared state."""
        contributions = {}
        for agent_type in AgentType:
            if agent_type != AgentType.SUPERVISOR:
                contrib = self.get_agent_contribution(agent_type)
                if contrib:
                    contributions[agent_type.value] = contrib
        return contributions
    
    def clear_shared_state(self) -> None:
        """Clear all shared state."""
        if self._shared_state_store:
            self._shared_state_store.clear()
        if self._message_queue:
            self._message_queue = MessageQueue(project_id=self._shared_state_store.project_id if self._shared_state_store else "")
    
    # ==================== Message Protocol Methods ====================
    
    def initialize_message_protocol(self, project_id: str) -> MessageProtocolManager:
        """
        Initialize the message protocol manager for a project.
        
        Args:
            project_id: Project identifier
        
        Returns:
            MessageProtocolManager instance
        """
        with self._lock:
            self._protocol_manager = MessageProtocolManager(project_id=project_id)
            return self._protocol_manager
    
    def get_protocol_manager(self) -> Optional[MessageProtocolManager]:
        """Get the current protocol manager."""
        return self._protocol_manager
    
    def send_request_message(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        action: str,
        content: Dict[str, Any],
        expected_response_type: str = "result",
        timeout_seconds: int = 300,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> Optional[RequestMessage]:
        """
        Send a request message to agents with expected response.
        
        Args:
            from_agent: Sending agent
            to_agents: Target agents
            action: Action being requested
            content: Request content
            expected_response_type: Type of response expected
            timeout_seconds: Response timeout
            priority: Message priority
        
        Returns:
            RequestMessage if sent, None otherwise
        """
        if not self._protocol_manager:
            return None
        
        return self._protocol_manager.send_request(
            from_agent=from_agent,
            to_agents=to_agents,
            action=action,
            content=content,
            expected_response_type=expected_response_type,
            timeout_seconds=timeout_seconds,
            priority=priority,
        )
    
    def send_response_message(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        request_id: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ResponseMessage]:
        """
        Send a response to a request.
        
        Args:
            from_agent: Sending agent
            to_agents: Target agents
            request_id: Original request ID
            success: Whether the request was successful
            result: Response result data
            error_code: Error code if failed
            error_message: Error message if failed
        
        Returns:
            ResponseMessage if sent, None otherwise
        """
        if not self._protocol_manager:
            return None
        
        return self._protocol_manager.send_response(
            from_agent=from_agent,
            to_agents=to_agents,
            request_id=request_id,
            success=success,
            result=result,
            error_code=error_code,
            error_message=error_message,
        )
    
    def send_notification_message(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        event_type: str,
        event_category: str = "general",
        importance: MessagePriority = MessagePriority.NORMAL,
        requires_action: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[NotificationMessage]:
        """
        Send a notification to agents about an event.
        
        Args:
            from_agent: Sending agent
            to_agents: Target agents
            event_type: Type of event
            event_category: Category of event
            importance: Message priority
            requires_action: Whether action is required
            metadata: Additional metadata
        
        Returns:
            NotificationMessage if sent, None otherwise
        """
        if not self._protocol_manager:
            return None
        
        return self._protocol_manager.send_notification(
            from_agent=from_agent,
            to_agents=to_agents,
            event_type=event_type,
            event_category=event_category,
            importance=importance,
            requires_action=requires_action,
            metadata=metadata,
        )
    
    def send_query_message(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        query_type: str,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        expected_results: int = 10,
        search_scope: str = "local",
    ) -> Optional[QueryMessage]:
        """
        Send a query to agents for information retrieval.
        
        Args:
            from_agent: Sending agent
            to_agents: Target agents
            query_type: Type of query
            query_text: Query text
            filters: Query filters
            expected_results: Expected number of results
            search_scope: Scope of search
        
        Returns:
            QueryMessage if sent, None otherwise
        """
        if not self._protocol_manager:
            return None
        
        return self._protocol_manager.send_query(
            from_agent=from_agent,
            to_agents=to_agents,
            query_type=query_type,
            query_text=query_text,
            filters=filters,
            expected_results=expected_results,
            search_scope=search_scope,
        )
    
    def acknowledge_message(
        self,
        envelope_id: str,
        from_agent: AgentType,
        processing_time_ms: float = 0.0,
        status: MessageStatus = MessageStatus.DELIVERED,
        error: Optional[str] = None,
    ) -> Optional[MessageAcknowledgment]:
        """
        Acknowledge receipt of a message.
        
        Args:
            envelope_id: Envelope ID to acknowledge
            from_agent: Agent acknowledging
            processing_time_ms: Processing time
            status: Delivery status
            error: Error if any
        
        Returns:
            Acknowledgment if recorded, None otherwise
        """
        if not self._protocol_manager:
            return None
        
        return self._protocol_manager.acknowledge_message(
            envelope_id=envelope_id,
            from_agent=from_agent,
            processing_time_ms=processing_time_ms,
            status=status,
            error=error,
        )
    
    def get_pending_requests(self, agent_type: AgentType) -> List[RequestMessage]:
        """Get pending requests for an agent."""
        if not self._protocol_manager:
            return []
        
        return self._protocol_manager.get_pending_requests(agent_type)
    
    def get_pending_responses(self, request_id: str) -> List[ResponseMessage]:
        """Get pending responses for a request."""
        if not self._protocol_manager:
            return []
        
        return self._protocol_manager.get_pending_responses(request_id)
    
    def check_envelope_status(self, envelope_id: str) -> Optional[MessageEnvelope]:
        """Check the status of an envelope."""
        if not self._protocol_manager:
            return None
        
        return self._protocol_manager.check_envelope_status(envelope_id)
    
    def handle_expiring_envelopes(self, threshold_seconds: int = 60) -> List[MessageEnvelope]:
        """Handle envelopes that are about to expire."""
        if not self._protocol_manager:
            return []
        
        expiring = self._protocol_manager.check_expiring_envelopes(threshold_seconds)
        
        # Notify relevant agents about expiring messages
        for envelope in expiring:
            if isinstance(envelope.message, RequestMessage):
                self.broadcast_message(
                    from_agent=AgentType.SUPERVISOR,
                    message_type="envelope_expiring",
                    content={
                        "envelope_id": envelope.envelope_id,
                        "message_type": envelope.message.message_type,
                        "expires_at": envelope.expires_at.isoformat() if envelope.expires_at else None,
                    },
                    priority=MessagePriority.HIGH.value,
                )
        
        return expiring
    
    def cleanup_protocol_manager(self, max_age_hours: int = 24) -> int:
        """Clean up old completed envelopes."""
        if not self._protocol_manager:
            return 0
        
        return self._protocol_manager.clear_completed_envelopes(max_age_hours)
    
    # ==================== Context Sharing Methods ====================
    
    def initialize_context_sharing(self, project_id: str) -> ContextSharingManager:
        """
        Initialize the context sharing manager for a project.
        
        Args:
            project_id: Project identifier
        
        Returns:
            ContextSharingManager instance
        """
        with self._lock:
            self._context_sharing_manager = ContextSharingManager(project_id=project_id)
            return self._context_sharing_manager
    
    def get_context_sharing_manager(self) -> Optional[ContextSharingManager]:
        """Get the current context sharing manager."""
        return self._context_sharing_manager
    
    def create_context_entry(
        self,
        context_type: ContextType,
        scope: ContextScope,
        key: str,
        value: Any,
        source_agent: AgentType,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ContextEntry]:
        """Create a new context entry."""
        if not self._context_sharing_manager:
            return None
        
        return self._context_sharing_manager.create_context_entry(
            context_type=context_type,
            scope=scope,
            key=key,
            value=value,
            source_agent=source_agent,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )
    
    def get_context_entry(
        self,
        scope: ContextScope,
        context_type: ContextType,
        key: str,
    ) -> Optional[ContextEntry]:
        """Get a context entry by scope, type, and key."""
        if not self._context_sharing_manager:
            return None
        
        return self._context_sharing_manager.get_context_entry(scope, context_type, key)
    
    def get_shared_context_for_agent(
        self,
        agent_type: AgentType,
        context_types: Optional[List[ContextType]] = None,
    ) -> Dict[str, Any]:
        """Get all shared context relevant to an agent."""
        if not self._context_sharing_manager:
            return {}
        
        return self._context_sharing_manager.get_shared_context_for_agent(
            agent_type=agent_type,
            context_types=context_types,
        )
    
    def create_context_bundle(
        self,
        project_id: str,
        task_id: Optional[str] = None,
        created_by: Optional[AgentType] = None,
        target_agents: Optional[List[AgentType]] = None,
    ) -> Optional[ContextBundle]:
        """Create a new context bundle."""
        if not self._context_sharing_manager:
            return None
        
        return self._context_sharing_manager.create_bundle(
            project_id=project_id,
            task_id=task_id,
            created_by=created_by,
            target_agents=target_agents,
        )
    
    def add_to_context_bundle(
        self,
        bundle_id: str,
        context_type: ContextType,
        scope: ContextScope,
        key: str,
        value: Any,
        source_agent: AgentType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ContextEntry]:
        """Add a context entry to a bundle."""
        if not self._context_sharing_manager:
            return None
        
        return self._context_sharing_manager.add_to_bundle(
            bundle_id=bundle_id,
            context_type=context_type,
            scope=scope,
            key=key,
            value=value,
            source_agent=source_agent,
            metadata=metadata,
        )
    
    def share_context_with_agent(
        self,
        from_agent: AgentType,
        to_agent: AgentType,
        context_type: ContextType,
        scope: ContextScope,
        key: str,
        value: Any,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[ContextEntry], bool]:
        """
        Share context with another agent.
        
        Args:
            from_agent: Agent sharing context
            to_agent: Agent to share with
            context_type: Type of context
            scope: Scope of context
            key: Context key
            value: Context value
            reason: Reason for sharing
            metadata: Additional metadata
        
        Returns:
            Tuple of (ContextEntry, whether sharing was successful)
        """
        if not self._context_sharing_manager:
            return None, False
        
        # Check if sharing is allowed
        if not self._context_sharing_manager.can_share_context(
            from_agent, to_agent, context_type, scope
        ):
            return None, False
        
        # Create the context entry
        entry = self._context_sharing_manager.create_context_entry(
            context_type=context_type,
            scope=scope,
            key=key,
            value=value,
            source_agent=from_agent,
            metadata=metadata,
        )
        
        # Record the share
        self._context_sharing_manager.record_share(
            share_request_id="",
            from_agent=from_agent,
            to_agent=to_agent,
            context_entry_id=entry.entry_id,
            audit_info={"reason": reason},
        )
        
        return entry, True
    
    def request_shared_context(
        self,
        from_agent: AgentType,
        to_agents: List[AgentType],
        context_type: ContextType,
        scope: ContextScope,
        context_key: str,
        reason: str,
    ) -> Optional[ContextShareRequest]:
        """Request context from other agents."""
        if not self._context_sharing_manager:
            return None
        
        return self._context_sharing_manager.create_share_request(
            from_agent=from_agent,
            to_agents=to_agents,
            context_type=context_type,
            scope=scope,
            context_key=context_key,
            context_value=None,  # Will be filled by the sharing agent
            reason=reason,
        )
    
    def add_sharing_policy(self, policy: ContextSharingPolicy) -> None:
        """Add a context sharing policy."""
        if self._context_sharing_manager:
            self._context_sharing_manager.add_policy(policy)
    
    def get_context_statistics(self) -> Optional[Dict[str, Any]]:
        """Get statistics about context sharing."""
        if not self._context_sharing_manager:
            return None
        
        return self._context_sharing_manager.get_statistics()
    
    def clear_expired_context(self) -> int:
        """Clear all expired context entries."""
        if not self._context_sharing_manager:
            return 0
        
        return self._context_sharing_manager.clear_expired_context()
    
    # ==================== Collaborative Context Methods ====================
    
    def share_decision_context(
        self,
        agent_type: AgentType,
        decision_id: str,
        decision_data: Dict[str, Any],
    ) -> Optional[ContextEntry]:
        """Share decision context with other agents."""
        return self.create_context_entry(
            context_type=ContextType.DECISION,
            scope=ContextScope.PROJECT,
            key=f"decision:{decision_id}",
            value=decision_data,
            source_agent=agent_type,
            metadata={"decision_id": decision_id},
        )
    
    def share_requirement_context(
        self,
        agent_type: AgentType,
        requirement_id: str,
        requirement_data: Dict[str, Any],
    ) -> Optional[ContextEntry]:
        """Share requirement context with other agents."""
        return self.create_context_entry(
            context_type=ContextType.REQUIREMENT,
            scope=ContextScope.PROJECT,
            key=f"requirement:{requirement_id}",
            value=requirement_data,
            source_agent=agent_type,
            metadata={"requirement_id": requirement_id},
        )
    
    def share_architecture_context(
        self,
        agent_type: AgentType,
        architecture_data: Dict[str, Any],
    ) -> Optional[ContextEntry]:
        """Share architecture context with other agents."""
        return self.create_context_entry(
            context_type=ContextType.ARCHITECTURE,
            scope=ContextScope.PROJECT,
            key="architecture:main",
            value=architecture_data,
            source_agent=agent_type,
            metadata={"shared_at": datetime.utcnow().isoformat()},
        )
    
    def get_decision_context(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get decision context by ID."""
        entry = self.get_context_entry(
            scope=ContextScope.PROJECT,
            context_type=ContextType.DECISION,
            key=f"decision:{decision_id}",
        )
        
        return entry.value if entry else None
    
    def get_requirement_context(self, requirement_id: str) -> Optional[Dict[str, Any]]:
        """Get requirement context by ID."""
        entry = self.get_context_entry(
            scope=ContextScope.PROJECT,
            context_type=ContextType.REQUIREMENT,
            key=f"requirement:{requirement_id}",
        )
        
        return entry.value if entry else None
    
    def get_architecture_context(self) -> Optional[Dict[str, Any]]:
        """Get shared architecture context."""
        entry = self.get_context_entry(
            scope=ContextScope.PROJECT,
            context_type=ContextType.ARCHITECTURE,
            key="architecture:main",
        )
        
        return entry.value if entry else None
    
    # ==================== Heartbeat & Health Monitoring Methods ====================
    
    def initialize_health_monitor(
        self,
        project_id: str,
        interval_seconds: int = 30,
        timeout_seconds: int = 120,
        enable_auto_recovery: bool = False,
    ) -> AgentHealthMonitor:
        """
        Initialize the health monitor for agents.
        
        Args:
            project_id: Project identifier
            interval_seconds: Heartbeat interval
            timeout_seconds: Timeout before marking unhealthy
            enable_auto_recovery: Enable automatic recovery
        
        Returns:
            AgentHealthMonitor instance
        """
        with self._lock:
            config = HealthMonitorConfig(
                global_interval_seconds=interval_seconds,
                global_timeout_seconds=timeout_seconds,
                enable_auto_recovery=enable_auto_recovery,
            )
            self._health_monitor = AgentHealthMonitor(
                project_id=project_id,
                config=config,
            )
            return self._health_monitor
    
    def get_health_monitor(self) -> Optional[AgentHealthMonitor]:
        """Get the current health monitor."""
        return self._health_monitor
    
    def register_agent_for_monitoring(
        self,
        agent_type: AgentType,
        interval_seconds: int = 30,
        timeout_seconds: int = 120,
        max_missed_heartbeats: int = 3,
    ) -> Optional[HeartbeatConfig]:
        """Register an agent for heartbeat monitoring."""
        if not self._health_monitor:
            return None
        
        return self._health_monitor.register_agent(
            agent_type=agent_type,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            max_missed_heartbeats=max_missed_heartbeats,
        )
    
    def record_heartbeat(
        self,
        agent_type: AgentType,
        status: AgentHealthStatus = AgentHealthStatus.UNKNOWN,
        latency_ms: float = 0.0,
        load: float = 0.0,
        memory_mb: float = 0.0,
        active_tasks: int = 0,
        queue_depth: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentHeartbeat]:
        """Record a heartbeat from an agent."""
        if not self._health_monitor:
            return None
        
        return self._health_monitor.record_heartbeat(
            agent_type=agent_type,
            status=status,
            latency_ms=latency_ms,
            load=load,
            memory_mb=memory_mb,
            active_tasks=active_tasks,
            queue_depth=queue_depth,
            metadata=metadata,
        )
    
    def check_agent_health(self, agent_type: AgentType) -> Tuple[HeartbeatStatus, AgentHealthStatus]:
        """Check the health status of an agent."""
        if not self._health_monitor:
            return HeartbeatStatus.STOPPED, AgentHealthStatus.UNKNOWN
        
        return self._health_monitor.check_heartbeat_status(agent_type)
    
    def get_all_agent_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get the status of all monitored agents."""
        if not self._health_monitor:
            return {}
        
        return self._health_monitor.get_all_agent_statuses()
    
    def perform_health_check(
        self,
        agent_type: AgentType,
        checks: Optional[Dict[str, Callable[[], Tuple[bool, str]]]] = None,
    ) -> Optional[HealthCheckResult]:
        """Perform a health check on an agent."""
        if not self._health_monitor:
            return None
        
        return self._health_monitor.perform_health_check(agent_type, checks)
    
    def get_health_history(
        self,
        agent_type: Optional[AgentType] = None,
        limit: int = 10,
    ) -> List[HealthCheckResult]:
        """Get health check history."""
        if not self._health_monitor:
            return []
        
        return self._health_monitor.get_health_history(agent_type, limit)
    
    def record_task_completion(
        self,
        agent_type: AgentType,
        execution_time_ms: float,
        success: bool,
        error_type: Optional[str] = None,
    ) -> Optional[AgentMetrics]:
        """Record task completion metrics."""
        if not self._health_monitor:
            return None
        
        return self._health_monitor.record_task_completion(
            agent_type=agent_type,
            execution_time_ms=execution_time_ms,
            success=success,
            error_type=error_type,
        )
    
    def record_task_timeout(self, agent_type: AgentType) -> Optional[AgentMetrics]:
        """Record a task timeout."""
        if not self._health_monitor:
            return None
        
        return self._health_monitor.record_task_timeout(agent_type)
    
    def get_agent_metrics(self, agent_type: AgentType) -> Optional[AgentMetrics]:
        """Get metrics for an agent."""
        if not self._health_monitor:
            return None
        
        return self._health_monitor.get_agent_metrics(agent_type)
    
    def get_all_metrics(self) -> Dict[str, AgentMetrics]:
        """Get metrics for all agents."""
        if not self._health_monitor:
            return {}
        
        return self._health_monitor.get_all_metrics()
    
    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics across all agents."""
        if not self._health_monitor:
            return {}
        
        return self._health_monitor.get_aggregate_metrics()
    
    def check_health_alerts(self) -> List[Dict[str, Any]]:
        """Check for health alerts."""
        if not self._health_monitor:
            return []
        
        return self._health_monitor.check_for_alerts()
    
    def get_health_status_summary(self) -> Dict[str, Any]:
        """Get a summary of the health monitor status."""
        if not self._health_monitor:
            return {}
        
        return self._health_monitor.get_status_summary()
    
    def send_heartbeat(self, agent_type: AgentType) -> Optional[AgentHeartbeat]:
        """
        Send a heartbeat for this agent.
        
        Args:
            agent_type: Type of the agent sending heartbeat
        
        Returns:
            AgentHeartbeat if recorded, None otherwise
        """
        return self.record_heartbeat(
            agent_type=agent_type,
            status=AgentHealthStatus.HEALTHY,
        )
    
    def report_unhealthy(
        self,
        agent_type: AgentType,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentHeartbeat]:
        """
        Report that an agent is unhealthy.
        
        Args:
            agent_type: Type of the agent
            message: Description of the issue
            details: Additional details
        
        Returns:
            AgentHeartbeat if recorded, None otherwise
        """
        return self.record_heartbeat(
            agent_type=agent_type,
            status=AgentHealthStatus.UNHEALTHY,
            metadata={"message": message, "details": details or {}},
        )
    
    # ==================== Timeout & Fallback Methods ====================
    
    def initialize_timeout_manager(
        self,
        project_id: str,
        global_timeout_seconds: int = 600,
        max_retries_per_task: int = 3,
        enable_automatic_fallback: bool = True,
        enable_retry_logic: bool = True,
    ) -> TimeoutManager:
        """
        Initialize the timeout manager for agent task handling.
        
        Args:
            project_id: Project identifier
            global_timeout_seconds: Global timeout for all tasks
            max_retries_per_task: Maximum retries per task
            enable_automatic_fallback: Enable automatic fallback
            enable_retry_logic: Enable retry logic
        
        Returns:
            TimeoutManager instance
        """
        with self._lock:
            self._timeout_manager = TimeoutManager(
                project_id=project_id,
                global_timeout_seconds=global_timeout_seconds,
                max_retries_per_task=max_retries_per_task,
                enable_automatic_fallback=enable_automatic_fallback,
                enable_retry_logic=enable_retry_logic,
            )
            return self._timeout_manager
    
    def get_timeout_manager(self) -> Optional[TimeoutManager]:
        """Get the current timeout manager."""
        return self._timeout_manager
    
    def set_agent_timeout(
        self,
        agent_type: AgentType,
        timeout_seconds: int = 300,
        soft_timeout_seconds: Optional[int] = None,
        retry_count: int = 0,
        retry_delay_seconds: int = 10,
        fallback_agent: Optional[AgentType] = None,
        fallback_strategy: TimeoutStrategy = TimeoutStrategy.FALLBACK,
        task_type: Optional[TaskType] = None,
    ) -> Optional[TimeoutConfig]:
        """Set timeout configuration for an agent."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.set_timeout(
            agent_type=agent_type,
            timeout_seconds=timeout_seconds,
            soft_timeout_seconds=soft_timeout_seconds,
            retry_count=retry_count,
            retry_delay_seconds=retry_delay_seconds,
            fallback_agent=fallback_agent,
            fallback_strategy=fallback_strategy,
            task_type=task_type,
        )
    
    def get_agent_timeout(self, agent_type: AgentType, task_type: Optional[TaskType] = None) -> int:
        """Get effective timeout for an agent."""
        if not self._timeout_manager:
            return 300  # Default 5 minutes
        
        return self._timeout_manager.get_effective_timeout(agent_type, task_type)
    
    def add_fallback_rule(
        self,
        primary_agent: AgentType,
        fallback_agent: AgentType,
        conditions: List[FallbackCondition] = None,
        priority: int = 0,
        max_fallbacks: int = 3,
        cooldown_seconds: Optional[int] = None,
    ) -> Optional[FallbackRule]:
        """Add a fallback rule for agent routing."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.add_fallback_rule(
            primary_agent=primary_agent,
            fallback_agent=fallback_agent,
            conditions=conditions,
            priority=priority,
            max_fallbacks=max_fallbacks,
            cooldown_seconds=cooldown_seconds,
        )
    
    def handle_agent_timeout(
        self,
        agent_type: AgentType,
        task_id: str,
        task_type: TaskType,
        elapsed_seconds: float,
        state: Optional[Dict[str, Any]] = None,
    ) -> Optional[TimeoutEvent]:
        """Handle a timeout event for an agent task."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.handle_timeout(
            agent_type=agent_type,
            task_id=task_id,
            task_type=task_type,
            elapsed_seconds=elapsed_seconds,
            state=state,
        )
    
    def get_fallback_agent(
        self,
        primary_agent: AgentType,
        condition: FallbackCondition,
        current_fallbacks: int = 0,
    ) -> Optional[AgentType]:
        """Get fallback agent based on rules."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.get_fallback_agent(
            primary_agent=primary_agent,
            condition=condition,
            current_fallbacks=current_fallbacks,
        )
    
    def execute_fallback(
        self,
        primary_agent: AgentType,
        task_id: str,
        condition: FallbackCondition,
        error_message: Optional[str] = None,
    ) -> Tuple[Optional[AgentType], TimeoutStrategy]:
        """Execute fallback routing for a failed task."""
        if not self._timeout_manager:
            return None, TimeoutStrategy.FAIL
        
        return self._timeout_manager.execute_fallback(
            primary_agent=primary_agent,
            task_id=task_id,
            condition=condition,
            error_message=error_message,
        )
    
    def record_retry(
        self,
        task_id: str,
        agent_type: AgentType,
        previous_error: str,
    ) -> Optional[RetryAttempt]:
        """Record a retry attempt for a task."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.record_retry(
            task_id=task_id,
            agent_type=agent_type,
            previous_error=previous_error,
            started_at=datetime.utcnow(),
        )
    
    def complete_retry(
        self,
        task_id: str,
        attempt_id: str,
        success: bool,
        execution_time_ms: float,
    ) -> bool:
        """Record completion of a retry attempt."""
        if not self._timeout_manager:
            return False
        
        return self._timeout_manager.complete_retry(
            task_id=task_id,
            attempt_id=attempt_id,
            success=success,
            execution_time_ms=execution_time_ms,
        )
    
    def should_retry_task(self, task_id: str, agent_type: AgentType) -> Tuple[bool, int]:
        """Check if a task should be retried."""
        if not self._timeout_manager:
            return False, 0
        
        return self._timeout_manager.should_retry(task_id, agent_type)
    
    def is_fallback_exhausted(self, primary_agent: AgentType, task_id: str) -> bool:
        """Check if all fallbacks are exhausted."""
        if not self._timeout_manager:
            return True
        
        return self._timeout_manager.is_fallback_exhausted(primary_agent, task_id)
    
    def get_timeout_statistics(self) -> Optional[Dict[str, Any]]:
        """Get timeout statistics."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.get_timeout_statistics()
    
    def get_fallback_statistics(self) -> Optional[Dict[str, Any]]:
        """Get fallback statistics."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.get_fallback_statistics()
    
    def get_timeout_status(self) -> Optional[Dict[str, Any]]:
        """Get overall timeout manager status."""
        if not self._timeout_manager:
            return None
        
        return self._timeout_manager.get_status()
    
    def clear_old_timeout_events(self, max_age_hours: int = 24) -> int:
        """Clear old timeout events."""
        if not self._timeout_manager:
            return 0
        
        return self._timeout_manager.clear_old_events(max_age_hours)
    
    def get_timeout_event_history(self, task_id: str) -> List[TimeoutEvent]:
        """Get timeout events for a task."""
        if not self._timeout_manager:
            return []
        
        return [e for e in self._timeout_manager.timeout_events if e.task_id == task_id]
    
    # ==================== Agent Selection Methods ====================
    
    def select_agent(
        self,
        task_type: TaskType,
        available_agents: List[AgentType],
        state: Optional[SupervisorAgentState] = None,
    ) -> AgentType:
        """
        Select the best agent for a given task type.
        
        Args:
            task_type: Type of task to perform
            available_agents: List of available agent types
            state: Current state for context-aware selection
        
        Returns:
            Selected agent type
        """
        # Get preferred agent for task type
        preferred = TASK_TYPE_TO_AGENT.get(task_type)
        
        if preferred and preferred in available_agents:
            return preferred
        
        # Find capable agents
        capable = [a for a in available_agents if self._can_agent_handle(a, task_type)]
        
        if not capable:
            # Fallback to preferred or first available
            return preferred or available_agents[0] if available_agents else AgentType.SUPERVISOR
        
        # Score and rank capable agents
        scored = [(agent, self._score_agent(agent, task_type, state)) for agent in capable]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored[0][0] if scored else preferred or AgentType.SUPERVISOR
    
    def _can_agent_handle(self, agent: AgentType, task_type: TaskType) -> bool:
        """
        Check if an agent can handle a specific task type.
        
        Args:
            agent: Agent type to check
            task_type: Task type to check
        
        Returns:
            True if agent can handle the task
        """
        # Direct mapping
        if TASK_TYPE_TO_AGENT.get(task_type) == agent:
            return True
        
        # Check agent capabilities
        capabilities = AGENT_CAPABILITIES.get(agent, [])
        task_type_str = task_type.value.replace("_", " ")
        
        for capability in capabilities:
            if task_type_str in capability or capability in task_type_str:
                return True
        
        return False
    
    def _score_agent(
        self,
        agent: AgentType,
        task_type: TaskType,
        state: Optional[SupervisorAgentState] = None,
    ) -> float:
        """
        Score an agent for a specific task.
        
        Args:
            agent: Agent type to score
            task_type: Task type to score for
            state: Current state for context
        
        Returns:
            Score (higher is better)
        """
        score = 0.0
        
        # Weight-based scoring
        weights = AGENT_SELECTION_WEIGHTS.get(agent, {})
        task_type_str = task_type.value
        
        # Direct weight match
        if task_type_str in weights:
            score += weights[task_type_str]
        
        # History-based scoring
        if state:
            completed_agents = state.get("completed_agents", [])
            
            # Prefer agents that haven't been used recently (load balancing)
            agent_count = completed_agents.count(agent)
            score += 1.0 / (1.0 + agent_count * 0.1)
            
            # Check recent performance
            recent_failures = state.get("recent_failures", {})
            if agent in recent_failures:
                score -= recent_failures[agent] * 0.2
        
        # Task type priority bonus
        priority = TASK_TYPE_PRIORITY.get(task_type, 0)
        if TASK_TYPE_TO_AGENT.get(task_type) == agent:
            score += priority * 0.1
        
        return score
    
    def select_agents_for_parallel_execution(
        self,
        task_types: List[TaskType],
        available_agents: List[AgentType],
        state: Optional[SupervisorAgentState] = None,
    ) -> Dict[TaskType, AgentType]:
        """
        Select agents for parallel execution of multiple tasks.
        
        Args:
            task_types: List of task types to execute
            available_agents: List of available agent types
            state: Current state for context
        
        Returns:
            Mapping of task type to selected agent
        """
        selections: Dict[TaskType, AgentType] = {}
        used_agents: List[AgentType] = []
        
        for task_type in task_types:
            # Filter out already-used agents if we want load balancing
            candidates = [a for a in available_agents if a not in used_agents]
            
            if not candidates:
                candidates = available_agents
            
            agent = self.select_agent(task_type, candidates, state)
            selections[task_type] = agent
            used_agents.append(agent)
        
        return selections
    
    def get_agent_status(
        self,
        agent: AgentType,
        state: SupervisorAgentState,
    ) -> Dict[str, Any]:
        """
        Get the status of an agent.
        
        Args:
            agent: Agent type to check
            state: Current state
        
        Returns:
            Agent status dictionary
        """
        current_agent = state.get("current_agent")
        completed_agents = state.get("completed_agents", [])
        
        is_active = current_agent == agent
        is_completed = agent in completed_agents
        
        return {
            "agent": agent.value,
            "is_active": is_active,
            "is_completed": is_completed,
            "can_handle": self._get_capabilities(agent),
        }
    
    def _get_capabilities(self, agent: AgentType) -> List[str]:
        """Get list of capabilities for an agent."""
        return AGENT_CAPABILITIES.get(agent, [])
    
    def create_enhanced_state_graph(
        self,
        config: Optional[SupervisorConfig] = None,
    ) -> StateGraph:
        """
        Create an enhanced StateGraph with agent selection logic.
        
        Args:
            config: Optional supervisor configuration
        
        Returns:
            Compiled StateGraph with agent selection
        """
        builder = StateGraph(SupervisorAgentState)
        
        # Entry point
        builder.add_node("supervisor_entry", self._supervisor_entry)
        
        # Agent selection node
        builder.add_node("select_agent", self._select_agent)
        
        # Agent routing nodes
        builder.add_node("route_to_interrogation", self._route_to_interrogation)
        builder.add_node("route_to_specification", self._route_to_specification)
        builder.add_node("route_to_validation", self._route_to_validation)
        builder.add_node("route_to_context_memory", self._route_to_context_memory)
        builder.add_node("route_to_delivery", self._route_to_delivery)
        
        # Decision and completion nodes
        builder.add_node("make_routing_decision", self._make_routing_decision)
        builder.add_node("check_completion", self._check_completion)
        builder.add_node("handle_agent_result", self._handle_agent_result)
        builder.add_node("handle_interrupt", self._handle_interrupt)
        builder.add_node("finalize", self._finalize)
        builder.add_node("handle_error", self._handle_error)
        
        # Entry edges
        builder.add_edge("__root__", "supervisor_entry")
        builder.add_edge("supervisor_entry", "select_agent")
        
        # Agent selection with intelligent routing
        builder.add_conditional_edges(
            "select_agent",
            self._get_selected_agent_target,
            {
                "interrogation": "route_to_interrogation",
                "specification": "route_to_specification",
                "validation": "route_to_validation",
                "context_memory": "route_to_context_memory",
                "delivery": "route_to_delivery",
                "completion": "check_completion",
                "error": "handle_error",
            }
        )
        
        # Continue to routing decision after selection
        builder.add_edge("select_agent", "make_routing_decision")
        
        # Routing edges
        builder.add_conditional_edges(
            "make_routing_decision",
            self._get_routing_target,
            {
                "interrogation": "route_to_interrogation",
                "specification": "route_to_specification",
                "validation": "route_to_validation",
                "context_memory": "route_to_context_memory",
                "delivery": "route_to_delivery",
                "completion": "check_completion",
                "finalize": "finalize",
                "error": "handle_error",
            }
        )
        
        # Agent execution edges
        builder.add_edge("route_to_interrogation", "handle_agent_result")
        builder.add_edge("route_to_specification", "handle_agent_result")
        builder.add_edge("route_to_validation", "handle_agent_result")
        builder.add_edge("route_to_context_memory", "handle_agent_result")
        builder.add_edge("route_to_delivery", "handle_agent_result")
        
        # Result handling
        builder.add_conditional_edges(
            "handle_agent_result",
            self._should_continue,
            {
                "continue": "select_agent",
                "interrupt": "handle_interrupt",
                "complete": "check_completion",
                "error": "handle_error",
            }
        )
        
        # Completion check
        builder.add_conditional_edges(
            "check_completion",
            self._is_workflow_complete,
            {
                "complete": "finalize",
                "continue": "select_agent",
                "error": "handle_error",
            }
        )
        
        # Interrupt handling
        builder.add_edge("handle_interrupt", "select_agent")
        
        # Final edges
        builder.add_edge("finalize", "__end__")
        builder.add_edge("handle_error", "__end__")
        
        return builder.compile()
    
    def _select_agent(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Select the best agent for the current task."""
        # Infer task type from state
        task_type = self._infer_task_type(state)
        
        if task_type is None:
            # No task, check completion
            state["selected_agent"] = None
            return state
        
        # Get available agents
        available_agents = state.get("available_agents", [
            AgentType.INTERROGATION,
            AgentType.SPECIFICATION,
            AgentType.VALIDATION,
            AgentType.CONTEXT_MEMORY,
            AgentType.DELIVERY,
        ])
        
        # Select agent
        selected = self.select_agent(task_type, available_agents, state)
        state["selected_agent"] = selected.value
        state["selected_task_type"] = task_type.value
        
        # Log selection
        state = add_message(
            state,
            "assistant",
            f"Selected {selected.value} for task: {task_type.value}"
        )
        
        return state
    
    def _get_selected_agent_target(self, state: SupervisorAgentState) -> str:
        """Get routing target based on selected agent."""
        selected = state.get("selected_agent")
        
        if selected is None:
            return "completion"
        
        mapping = {
            AgentType.INTERROGATION.value: "interrogation",
            AgentType.SPECIFICATION.value: "specification",
            AgentType.VALIDATION.value: "validation",
            AgentType.CONTEXT_MEMORY.value: "context_memory",
            AgentType.DELIVERY.value: "delivery",
        }
        
        return mapping.get(selected, "completion")
    
    def _create_state_graph(self) -> StateGraph:
        """Create the LangGraph state machine for the supervisor."""
        builder = StateGraph(SupervisorAgentState)
        
        # Entry point
        builder.add_node("supervisor_entry", self._supervisor_entry)
        
        # Agent routing nodes
        builder.add_node("route_to_interrogation", self._route_to_interrogation)
        builder.add_node("route_to_specification", self._route_to_specification)
        builder.add_node("route_to_validation", self._route_to_validation)
        builder.add_node("route_to_context_memory", self._route_to_context_memory)
        builder.add_node("route_to_delivery", self._route_to_delivery)
        
        # Decision and completion nodes
        builder.add_node("make_routing_decision", self._make_routing_decision)
        builder.add_node("check_completion", self._check_completion)
        builder.add_node("handle_agent_result", self._handle_agent_result)
        builder.add_node("handle_interrupt", self._handle_interrupt)
        builder.add_node("finalize", self._finalize)
        builder.add_node("handle_error", self._handle_error)
        
        # Entry edges
        builder.add_edge("__root__", "supervisor_entry")
        
        # Supervisor flow
        builder.add_edge("supervisor_entry", "make_routing_decision")
        
        # Routing edges
        builder.add_conditional_edges(
            "make_routing_decision",
            self._get_routing_target,
            {
                "interrogation": "route_to_interrogation",
                "specification": "route_to_specification",
                "validation": "route_to_validation",
                "context_memory": "route_to_context_memory",
                "delivery": "route_to_delivery",
                "completion": "check_completion",
                "finalize": "finalize",
                "error": "handle_error",
            }
        )
        
        # Agent execution edges (simulated - in real impl would call actual agents)
        builder.add_edge("route_to_interrogation", "handle_agent_result")
        builder.add_edge("route_to_specification", "handle_agent_result")
        builder.add_edge("route_to_validation", "handle_agent_result")
        builder.add_edge("route_to_context_memory", "handle_agent_result")
        builder.add_edge("route_to_delivery", "handle_agent_result")
        
        # Result handling
        builder.add_conditional_edges(
            "handle_agent_result",
            self._should_continue,
            {
                "continue": "make_routing_decision",
                "interrupt": "handle_interrupt",
                "complete": "check_completion",
                "error": "handle_error",
            }
        )
        
        # Completion check
        builder.add_conditional_edges(
            "check_completion",
            self._is_workflow_complete,
            {
                "complete": "finalize",
                "continue": "make_routing_decision",
                "error": "handle_error",
            }
        )
        
        # Interrupt handling
        builder.add_edge("handle_interrupt", "make_routing_decision")
        
        # Final edges
        builder.add_edge("finalize", "__end__")
        builder.add_edge("handle_error", "__end__")
        
        return builder.compile()
    
    def _supervisor_entry(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Entry point for the supervisor."""
        self.status = SupervisorStatus.ORCHESTRATING
        
        # Add system message
        state = add_message(
            state,
            "system",
            "Supervisor: Starting orchestration of spec generation workflow."
        )
        
        # Initialize agent queue if not set
        if not state.get("agent_queue"):
            state["agent_queue"] = [
                AgentType.INTERROGATION,
                AgentType.SPECIFICATION,
                AgentType.VALIDATION,
                AgentType.CONTEXT_MEMORY,
                AgentType.DELIVERY,
            ]
        
        return state
    
    def _make_routing_decision(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Make a decision about which agent to route to next."""
        decision = self._evaluate_routing(state)
        self.supervisor_decisions.append(decision)
        
        # Add decision to state
        state["last_supervisor_decision"] = decision.model_dump()
        
        state = add_message(
            state,
            "assistant",
            f"Supervisor decision: {decision.action.value} - {decision.reasoning}"
        )
        
        return state
    
    def _evaluate_routing(self, state: SupervisorAgentState) -> SupervisorDecision:
        """Evaluate routing based on current state and strategy."""
        agent_queue = state.get("agent_queue", [])
        completed_agents = state.get("completed_agents", [])
        current_agent = state.get("current_agent")
        
        # Check if we have a pending interrupt
        if state.get("should_interrupt") and state.get("pending_interrupts"):
            return SupervisorDecision(
                action=SupervisorAction.HANDLE_INTERRUPT,
                reasoning="Pending human interrupt requires attention",
                alternative_actions=[SupervisorAction.CHECK_COMPLETION],
            )
        
        # Check completion first
        if self._check_workflow_complete(state):
            return SupervisorDecision(
                action=SupervisorAction.CHECK_COMPLETION,
                reasoning="Workflow completion conditions met",
                confidence=1.0,
            )
        
        # Route based on strategy
        if self.config.default_routing_strategy == RoutingStrategy.SEQUENTIAL:
            return self._sequential_routing(agent_queue, completed_agents, current_agent)
        elif self.config.default_routing_strategy == RoutingStrategy.PRIORITY:
            return self._priority_routing(state)
        elif self.config.default_routing_strategy == RoutingStrategy.TASK_TYPE:
            return self._task_type_routing(state)
        else:
            return self._dependency_routing(state)
    
    def _sequential_routing(
        self,
        agent_queue: List[AgentType],
        completed_agents: List[AgentType],
        current_agent: Optional[AgentType],
    ) -> SupervisorDecision:
        """Route agents sequentially."""
        # Find next incomplete agent
        for agent in agent_queue:
            if agent not in completed_agents:
                action = self._agent_to_action(agent)
                return SupervisorDecision(
                    action=action,
                    target_agent=agent,
                    reasoning=f"Next agent in sequence: {agent.value}",
                )
        
        # All agents completed
        return SupervisorDecision(
            action=SupervisorAction.CHECK_COMPLETION,
            reasoning="All agents have completed their tasks",
        )
    
    def _priority_routing(self, state: SupervisorAgentState) -> SupervisorDecision:
        """Route based on priority and urgency."""
        pending_questions = state.get("pending_questions", [])
        validation_queue = state.get("validation_queue", [])
        artifacts = state.get("artifacts", {})
        
        # Priority order: interrogation -> validation -> specification -> delivery
        if pending_questions:
            return SupervisorDecision(
                action=SupervisorAction.START_INTERROGATION,
                target_agent=AgentType.INTERROGATION,
                reasoning="Pending questions require answers",
            )
        
        if validation_queue:
            return SupervisorDecision(
                action=SupervisorAction.START_VALIDATION,
                target_agent=AgentType.VALIDATION,
                reasoning="Artifacts require validation",
            )
        
        if artifacts:
            return SupervisorDecision(
                action=SupervisorAction.START_SPECIFICATION,
                target_agent=AgentType.SPECIFICATION,
                reasoning="Decisions ready for specification generation",
            )
        
        return SupervisorDecision(
            action=SupervisorAction.CHECK_COMPLETION,
            reasoning="No pending high-priority tasks",
        )
    
    def _dependency_routing(self, state: SupervisorAgentState) -> SupervisorDecision:
        """Route based on task dependencies."""
        # Check dependencies
        decisions = state.get("decisions", {})
        artifacts = state.get("artifacts", {})
        
        # Need decisions before specification
        if not decisions:
            return SupervisorDecision(
                action=SupervisorAction.START_INTERROGATION,
                target_agent=AgentType.INTERROGATION,
                reasoning="No decisions yet - start interrogation",
            )
        
        # Need specification before validation
        if decisions and not artifacts:
            return SupervisorDecision(
                action=SupervisorAction.START_SPECIFICATION,
                target_agent=AgentType.SPECIFICATION,
                reasoning="Decisions ready - generate specifications",
            )
        
        # Need validation before delivery
        if self.config.require_validation:
            validation_results = state.get("validation_results", {})
            if not validation_results:
                return SupervisorDecision(
                    action=SupervisorAction.START_VALIDATION,
                    target_agent=AgentType.VALIDATION,
                    reasoning="Specifications ready - validate before delivery",
                )
        
        # Ready for delivery
        if self.config.require_delivery:
            return SupervisorDecision(
                action=SupervisorAction.START_DELIVERY,
                target_agent=AgentType.DELIVERY,
                reasoning="All prerequisites met - deliver artifacts",
            )
        
        return SupervisorDecision(
            action=SupervisorAction.CHECK_COMPLETION,
            reasoning="All dependencies resolved",
        )
    
    def _task_type_routing(self, state: SupervisorAgentState) -> SupervisorDecision:
        """
        Route tasks based on task type.
        
        This method:
        1. Checks for pending task queue
        2. Infers task type from state if not explicit
        3. Validates dependencies
        4. Routes to appropriate agent
        """
        # Check for explicit task queue
        task_queue = state.get("task_queue", [])
        
        if task_queue:
            # Process tasks in queue
            return self._process_task_queue(state, task_queue)
        
        # Infer task type from current state
        task_type = self._infer_task_type(state)
        
        if task_type is None:
            # Default to decision gathering if no clear task
            return SupervisorDecision(
                action=SupervisorAction.START_INTERROGATION,
                target_agent=AgentType.INTERROGATION,
                reasoning="No pending tasks - defaulting to decision gathering",
            )
        
        # Get target agent for task type
        target_agent = TASK_TYPE_TO_AGENT.get(task_type)
        
        if target_agent is None:
            return SupervisorDecision(
                action=SupervisorAction.CHECK_COMPLETION,
                reasoning=f"Unknown task type: {task_type.value}",
            )
        
        # Check dependencies
        dependencies = TASK_DEPENDENCIES.get(task_type, [])
        unmet_deps = self._check_task_dependencies(dependencies, state)
        
        if unmet_deps:
            # Route to highest priority unmet dependency
            next_task = self._get_highest_priority_task(unmet_deps, state)
            return self._route_to_dependency(next_task, state)
        
        # Create routing decision
        action = self._agent_to_action(target_agent)
        
        return SupervisorDecision(
            action=action,
            target_agent=target_agent,
            reasoning=f"Task type '{task_type.value}' routes to {target_agent.value}",
            confidence=0.9,
            alternative_actions=[
                self._agent_to_action(agent)
                for agent in AGENT_TO_TASK_TYPES.get(target_agent, [])
                if agent != task_type
            ],
        )
    
    def _process_task_queue(self, state: SupervisorAgentState, task_queue: List[Dict[str, Any]]) -> SupervisorDecision:
        """Process tasks from the task queue."""
        completed_tasks = state.get("completed_tasks", [])
        
        for task in task_queue:
            task_id = task.get("id")
            task_type_str = task.get("task_type")
            
            if task_id in completed_tasks:
                continue
            
            try:
                task_type = TaskType(task_type_str)
            except ValueError:
                continue
            
            # Check dependencies
            dependencies = TASK_DEPENDENCIES.get(task_type, [])
            unmet_deps = self._check_task_dependencies(dependencies, state)
            
            if unmet_deps:
                # Defer this task until dependencies are met
                continue
            
            target_agent = TASK_TYPE_TO_AGENT.get(task_type)
            
            if target_agent:
                action = self._agent_to_action(target_agent)
                return SupervisorDecision(
                    action=action,
                    target_agent=target_agent,
                    reasoning=f"Processing queued task: {task_type.value}",
                    confidence=0.95,
                )
        
        # All queued tasks either completed or waiting on dependencies
        return SupervisorDecision(
            action=SupervisorAction.CHECK_COMPLETION,
            reasoning="All queued tasks processed",
        )
    
    def _infer_task_type(self, state: SupervisorAgentState) -> Optional[TaskType]:
        """
        Infer the task type from the current state.
        
        Priority order for inference:
        1. Conflicts detected -> CONFLICT_RESOLUTION
        2. Pending questions -> DECISION_GATHERING
        3. No artifacts but decisions exist -> SPECIFICATION_GENERATION
        4. Artifacts exist but not validated -> ARTIFACT_VALIDATION
        5. Brownfield project -> CODEBASE_ANALYSIS or IMPACT_ANALYSIS
        6. Export requested -> ARTIFACT_EXPORT
        7. Context query -> CONTEXT_RETRIEVAL
        """
        # Check for contradictions/conflicts
        pending_conflicts = state.get("pending_conflicts", [])
        if pending_conflicts:
            return TaskType.CONFLICT_RESOLUTION
        
        # Check for pending questions
        pending_questions = state.get("pending_questions", [])
        if pending_questions:
            return TaskType.DECISION_GATHERING
        
        # Check decisions and artifacts
        decisions = state.get("decisions", {})
        artifacts = state.get("artifacts", {})
        
        if not decisions:
            # No decisions yet - need to gather them
            return TaskType.DECISION_GATHERING
        
        if decisions and not artifacts:
            # Have decisions, need to generate specs
            return TaskType.SPECIFICATION_GENERATION
        
        if artifacts:
            validation_results = state.get("validation_results", {})
            if not validation_results:
                # Have artifacts, need to validate
                return TaskType.ARTIFACT_VALIDATION
            
            # Check if export is requested
            export_requested = state.get("export_requested", False)
            if export_requested:
                return TaskType.ARTIFACT_EXPORT
        
        # Check for brownfield analysis
        project_type = state.get("project_type")
        if project_type == "brownfield":
            # Check if analysis is needed
            analysis_complete = state.get("codebase_analysis_complete", False)
            if not analysis_complete:
                return TaskType.CODEBASE_ANALYSIS
            
            # Check for impact analysis
            impact_requested = state.get("impact_analysis_requested", False)
            if impact_requested:
                return TaskType.IMPACT_ANALYSIS
        
        # Check for context retrieval
        context_query = state.get("context_query")
        if context_query:
            return TaskType.CONTEXT_RETRIEVAL
        
        # Default to decision gathering
        return TaskType.DECISION_GATHERING
    
    def _check_task_dependencies(
        self,
        dependencies: List[TaskType],
        state: SupervisorAgentState,
    ) -> List[TaskType]:
        """Check which dependencies are not yet met."""
        unmet = []
        completed_tasks = state.get("completed_tasks", [])
        decisions = state.get("decisions", {})
        artifacts = state.get("artifacts", {})
        
        for dep in dependencies:
            if dep == TaskType.DECISION_GATHERING and not decisions:
                unmet.append(dep)
            elif dep == TaskType.SPECIFICATION_GENERATION and not artifacts:
                unmet.append(dep)
            elif dep == TaskType.CODEBASE_ANALYSIS:
                analysis_complete = state.get("codebase_analysis_complete", False)
                if not analysis_complete:
                    unmet.append(dep)
        
        return unmet
    
    def _get_highest_priority_task(
        self,
        tasks: List[TaskType],
        state: SupervisorAgentState,
    ) -> TaskType:
        """Get the highest priority task from a list."""
        if not tasks:
            return TaskType.DECISION_GATHERING
        
        # Sort by priority (higher first)
        sorted_tasks = sorted(tasks, key=lambda t: TASK_TYPE_PRIORITY.get(t, 0), reverse=True)
        return sorted_tasks[0]
    
    def _route_to_dependency(
        self,
        task_type: TaskType,
        state: SupervisorAgentState,
    ) -> SupervisorDecision:
        """Route to handle a dependency task."""
        target_agent = TASK_TYPE_TO_AGENT.get(task_type)
        
        if target_agent:
            action = self._agent_to_action(target_agent)
            return SupervisorDecision(
                action=action,
                target_agent=target_agent,
                reasoning=f"Dependency required: {task_type.value} -> {target_agent.value}",
                confidence=0.85,
            )
        
        return SupervisorDecision(
            action=SupervisorAction.CHECK_COMPLETION,
            reasoning=f"Cannot route dependency: {task_type.value}",
        )
    
    def _agent_to_action(self, agent: AgentType) -> SupervisorAction:
        """Convert agent type to supervisor action."""
        mapping = {
            AgentType.INTERROGATION: SupervisorAction.START_INTERROGATION,
            AgentType.SPECIFICATION: SupervisorAction.START_SPECIFICATION,
            AgentType.VALIDATION: SupervisorAction.START_VALIDATION,
            AgentType.CONTEXT_MEMORY: SupervisorAction.START_CONTEXT_MEMORY,
            AgentType.DELIVERY: SupervisorAction.START_DELIVERY,
            AgentType.SUPERVISOR: SupervisorAction.ROUTE_TO_AGENT,
        }
        return mapping.get(agent, SupervisorAction.ROUTE_TO_AGENT)
    
    def _get_routing_target(self, state: SupervisorAgentState) -> str:
        """Get routing target from state."""
        decision = state.get("last_supervisor_decision", {})
        action = decision.get("action", "completion")
        
        mapping = {
            SupervisorAction.START_INTERROGATION.value: "interrogation",
            SupervisorAction.START_SPECIFICATION.value: "specification",
            SupervisorAction.START_VALIDATION.value: "validation",
            SupervisorAction.START_CONTEXT_MEMORY.value: "context_memory",
            SupervisorAction.START_DELIVERY.value: "delivery",
            SupervisorAction.CHECK_COMPLETION.value: "completion",
            SupervisorAction.HANDLE_INTERRUPT.value: "interrupt",
            SupervisorAction.FINALIZE.value: "finalize",
            SupervisorAction.ERROR.value: "error",
        }
        
        return mapping.get(action, "completion")
    
    def _route_to_interrogation(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Route to interrogation agent."""
        state["current_agent"] = AgentType.INTERROGATION
        state = add_message(state, "assistant", "Routing to Interrogation Agent...")
        return state
    
    def _route_to_specification(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Route to specification agent."""
        state["current_agent"] = AgentType.SPECIFICATION
        state = add_message(state, "assistant", "Routing to Specification Agent...")
        return state
    
    def _route_to_validation(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Route to validation agent."""
        state["current_agent"] = AgentType.VALIDATION
        state = add_message(state, "assistant", "Routing to Validation Agent...")
        return state
    
    def _route_to_context_memory(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Route to context memory agent."""
        state["current_agent"] = AgentType.CONTEXT_MEMORY
        state = add_message(state, "assistant", "Routing to Context Memory Agent...")
        return state
    
    def _route_to_delivery(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Route to delivery agent."""
        state["current_agent"] = AgentType.DELIVERY
        state = add_message(state, "assistant", "Routing to Delivery Agent...")
        return state
    
    def _handle_agent_result(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Handle result from an agent."""
        current_agent = state.get("current_agent")
        
        if current_agent:
            # Mark agent as completed
            completed = state.get("completed_agents", [])
            if current_agent not in completed:
                completed.append(current_agent)
                state["completed_agents"] = completed
            
            state = add_message(
                state,
                "assistant",
                f"{current_agent.value} agent completed."
            )
        
        state["current_agent"] = None
        return state
    
    def _should_continue(self, state: SupervisorAgentState) -> str:
        """Determine if workflow should continue."""
        if state.get("should_interrupt"):
            return "interrupt"
        
        decision = state.get("last_supervisor_decision", {})
        action = decision.get("action", "")
        
        if action in [SupervisorAction.CHECK_COMPLETION.value, SupervisorAction.FINALIZE.value]:
            return "complete"
        
        return "continue"
    
    def _check_workflow_complete(self, state: SupervisorAgentState) -> bool:
        """Check if workflow is complete."""
        required_agents = [AgentType.INTERROGATION, AgentType.SPECIFICATION]
        
        if self.config.require_validation:
            required_agents.append(AgentType.VALIDATION)
        
        if self.config.require_delivery:
            required_agents.append(AgentType.DELIVERY)
        
        completed = state.get("completed_agents", [])
        
        return all(agent in completed for agent in required_agents)
    
    def _is_workflow_complete(self, state: SupervisorAgentState) -> Dict[str, Any]:
        """Check if workflow is complete - returns routing decision."""
        if self._check_workflow_complete(state):
            return {"route": "complete"}
        
        return {"route": "continue"}
    
    def _handle_interrupt(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Handle a human interrupt."""
        pending_interrupts = state.get("pending_interrupts", [])
        
        if pending_interrupts:
            interrupt = pending_interrupts[0]
            state = add_message(
                state,
                "user",
                f"Interrupt: {interrupt.get('message', 'Human intervention required')}"
            )
        
        state["should_interrupt"] = False
        return state
    
    def _finalize(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Finalize the workflow."""
        self.status = SupervisorStatus.COMPLETED
        
        state = add_message(
            state,
            "system",
            "Supervisor: Workflow completed successfully."
        )
        
        # Aggregate results
        state["final_report"] = {
            "completed_agents": state.get("completed_agents", []),
            "total_agents": len(state.get("agent_queue", [])),
            "decisions_count": len(state.get("decisions", {})),
            "artifacts_count": len(state.get("artifacts", {})),
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        return state
    
    def _handle_error(self, state: SupervisorAgentState) -> SupervisorAgentState:
        """Handle an error."""
        self.status = SupervisorStatus.ERROR
        
        state = add_message(
            state,
            "system",
            "Supervisor: Workflow terminated with error."
        )
        
        errors = state.get("errors", [])
        if errors:
            last_error = errors[-1]
            state = add_message(
                state,
                "assistant",
                f"Error: {last_error.get('message', 'Unknown error')}"
            )
        
        return state
    
    # ==================== Public API ====================
    
    def create_workflow(
        self,
        project_id: str,
        thread_id: Optional[str] = None,
    ) -> StateGraph:
        """
        Create a supervisor workflow graph.
        
        Args:
            project_id: Project identifier
            thread_id: Optional thread ID
        
        Returns:
            Compiled StateGraph
        """
        self.graph = self._create_state_graph()
        return self.graph
    
    async def run(
        self,
        project_id: str,
        thread_id: Optional[str] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> SupervisorAgentState:
        """
        Run the supervisor workflow.
        
        Args:
            project_id: Project identifier
            thread_id: Optional thread ID
            initial_state: Optional initial state
        
        Returns:
            Final state
        """
        if not self.graph:
            self.create_workflow(project_id, thread_id)
        
        state = create_supervisor_state(project_id, thread_id)
        
        if initial_state:
            state.update(initial_state)
        
        result = await self.graph.ainvoke(state)
        return result
    
    def delegate_to_agent(
        self,
        agent_type: AgentType,
        task_data: Dict[str, Any],
    ) -> AgentTask:
        """
        Create a task for delegation to an agent.
        
        Args:
            agent_type: Type of agent to delegate to
            task_data: Task data
        
        Returns:
            AgentTask
        """
        return AgentTask(
            agent_type=agent_type,
            project_id=task_data.get("project_id", ""),
            input_data=task_data,
        )
    
    def register_callback(
        self,
        event: str,
        callback: Callable,
    ) -> None:
        """Register a callback for supervisor events."""
        self._callbacks[event] = callback
    
    def _trigger_callback(self, event: str, data: Any) -> None:
        """Trigger a registered callback."""
        callback = self._callbacks.get(event)
        if callback:
            callback(data)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current supervisor status."""
        return {
            "status": self.status.value,
            "config": self.config.model_dump(),
            "decisions_count": len(self.supervisor_decisions),
            "results_count": len(self.agent_results),
        }
    
    def reset(self) -> None:
        """Reset the supervisor to initial state."""
        self.status = SupervisorStatus.IDLE
        self.agent_results.clear()
        self.supervisor_decisions.clear()
        self._callbacks.clear()
        self._pending_delegations.clear()
        # Keep delegation history but mark as archived
        for delegation in self._delegation_history:
            delegation.status = TaskDelegationStatus.CANCELLED

    
    def create_delegation(
        self,
        task_id: str,
        agent_type: AgentType,
        task_type: TaskType,
        input_data: Dict[str, Any],
    ) -> TaskDelegation:
        """
        Create a task delegation record.
        
        Args:
            task_id: Unique task identifier
            agent_type: Type of agent to delegate to
            task_type: Type of task
            input_data: Task input data
        
        Returns:
            TaskDelegation record
        """
        return TaskDelegation(
            task_id=task_id,
            agent_type=agent_type,
            task_type=task_type,
            input_data=input_data,
            max_retries=self.config.max_retries,
        )
    
    def delegate_to_interrogation(
        self,
        project_id: str,
        questions: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskDelegation:
        """
        Delegate decision gathering to InterrogationAgent.
        
        Args:
            project_id: Project identifier
            questions: List of questions to ask
            context: Optional context data
        
        Returns:
            TaskDelegation record
        """
        task_id = f"interrogation_{uuid4()}"
        input_data = {
            "project_id": project_id,
            "questions": questions,
            "context": context or {},
        }
        
        return self.create_delegation(
            task_id=task_id,
            agent_type=AgentType.INTERROGATION,
            task_type=TaskType.DECISION_GATHERING,
            input_data=input_data,
        )
    
    def delegate_to_specification(
        self,
        project_id: str,
        decisions: Dict[str, Any],
        artifact_types: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskDelegation:
        """
        Delegate specification generation to SpecificationAgent.
        
        Args:
            project_id: Project identifier
            decisions: Collected decisions
            artifact_types: Types of artifacts to generate
            context: Optional context data
        
        Returns:
            TaskDelegation record
        """
        task_id = f"specification_{uuid4()}"
        input_data = {
            "project_id": project_id,
            "decisions": decisions,
            "artifact_types": artifact_types,
            "context": context or {},
        }
        
        return self.create_delegation(
            task_id=task_id,
            agent_type=AgentType.SPECIFICATION,
            task_type=TaskType.SPECIFICATION_GENERATION,
            input_data=input_data,
        )
    
    def delegate_to_validation(
        self,
        project_id: str,
        artifacts: Dict[str, Any],
        decisions: Dict[str, Any],
        validation_type: str = "full",
    ) -> TaskDelegation:
        """
        Delegate artifact validation to ValidationAgent.
        
        Args:
            project_id: Project identifier
            artifacts: Artifacts to validate
            decisions: Decisions that artifacts are based on
            validation_type: Type of validation (full, partial, contradiction_check)
        
        Returns:
            TaskDelegation record
        """
        task_id = f"validation_{uuid4()}"
        input_data = {
            "project_id": project_id,
            "artifacts": artifacts,
            "decisions": decisions,
            "validation_type": validation_type,
        }
        
        task_type = TaskType.CONFLICT_RESOLUTION if validation_type == "contradiction_check" else TaskType.ARTIFACT_VALIDATION
        
        return self.create_delegation(
            task_id=task_id,
            agent_type=AgentType.VALIDATION,
            task_type=task_type,
            input_data=input_data,
        )
    
    def delegate_to_context_memory(
        self,
        project_id: str,
        operation: str,
        query: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> TaskDelegation:
        """
        Delegate context operations to ContextMemoryAgent.
        
        Args:
            project_id: Project identifier
            operation: Operation type (retrieve, store, search, analyze)
            query: Query for retrieval/search
            data: Data for storage
        
        Returns:
            TaskDelegation record
        """
        task_id = f"context_memory_{uuid4()}"
        input_data = {
            "project_id": project_id,
            "operation": operation,
            "query": query,
            "data": data,
        }
        
        # Determine task type based on operation
        if operation == "analyze":
            task_type = TaskType.CODEBASE_ANALYSIS
        elif operation == "impact":
            task_type = TaskType.IMPACT_ANALYSIS
        else:
            task_type = TaskType.CONTEXT_RETRIEVAL
        
        return self.create_delegation(
            task_id=task_id,
            agent_type=AgentType.CONTEXT_MEMORY,
            task_type=task_type,
            input_data=input_data,
        )
    
    def delegate_to_delivery(
        self,
        project_id: str,
        artifacts: Dict[str, Any],
        export_formats: List[str],
        delivery_options: Optional[Dict[str, Any]] = None,
    ) -> TaskDelegation:
        """
        Delegate artifact export to DeliveryAgent.
        
        Args:
            project_id: Project identifier
            artifacts: Artifacts to export
            export_formats: Target export formats
            delivery_options: Delivery options (email, webhook, download, etc.)
        
        Returns:
            TaskDelegation record
        """
        task_id = f"delivery_{uuid4()}"
        input_data = {
            "project_id": project_id,
            "artifacts": artifacts,
            "export_formats": export_formats,
            "delivery_options": delivery_options or {},
        }
        
        return self.create_delegation(
            task_id=task_id,
            agent_type=AgentType.DELIVERY,
            task_type=TaskType.ARTIFACT_EXPORT,
            input_data=input_data,
        )
    
    async def execute_delegation(
        self,
        delegation: TaskDelegation,
        agent_instances: Dict[AgentType, Any],
    ) -> TaskDelegation:
        """
        Execute a task delegation.
        
        Args:
            delegation: TaskDelegation to execute
            agent_instances: Dictionary of agent instances
        
        Returns:
            Updated TaskDelegation with results
        """
        agent = agent_instances.get(delegation.agent_type)
        
        if agent is None:
            delegation.status = TaskDelegationStatus.FAILED
            delegation.error = f"Agent not found: {delegation.agent_type}"
            return delegation
        
        delegation.status = TaskDelegationStatus.IN_PROGRESS
        delegation.started_at = datetime.utcnow()
        
        try:
            # Execute the agent with input data
            if hasattr(agent, 'run'):
                result = await agent.run(
                    project_id=delegation.input_data.get("project_id"),
                    thread_id=delegation.task_id,
                    initial_state=delegation.input_data,
                )
                delegation.output_data = result
            else:
                # Simple synchronous execution for agents without run method
                result = agent.execute(delegation.input_data)
                delegation.output_data = result
            
            delegation.status = TaskDelegationStatus.COMPLETED
            delegation.completed_at = datetime.utcnow()
            
        except Exception as e:
            delegation.error = str(e)
            delegation.retries += 1
            
            if delegation.retries < delegation.max_retries:
                delegation.status = TaskDelegationStatus.PENDING
            else:
                delegation.status = TaskDelegationStatus.FAILED
            
            delegation.completed_at = datetime.utcnow()
        
        return delegation
    
    def batch_delegate(
        self,
        delegations: List[TaskDelegation],
        parallel: bool = False,
    ) -> List[TaskDelegation]:
        """
        Prepare batch delegations.
        
        Args:
            delegations: List of task delegations
            parallel: Whether to execute in parallel
        
        Returns:
            List of TaskDelegation records
        """
        # Store delegations
        for delegation in delegations:
            self._pending_delegations[delegation.delegation_id] = delegation
        
        return delegations
    
    def cancel_delegation(self, delegation_id: str) -> bool:
        """
        Cancel a pending delegation.
        
        Args:
            delegation_id: ID of delegation to cancel
        
        Returns:
            True if cancelled, False if not found
        """
        delegation = self._pending_delegations.get(delegation_id)
        
        if delegation and delegation.status == TaskDelegationStatus.PENDING:
            delegation.status = TaskDelegationStatus.CANCELLED
            return True
        
        return False
    
    def get_delegation_status(self, delegation_id: str) -> Optional[TaskDelegation]:
        """
        Get status of a delegation.
        
        Args:
            delegation_id: ID of delegation
        
        Returns:
            TaskDelegation if found, None otherwise
        """
        return self._pending_delegations.get(delegation_id)
    
    # ==================== Result Aggregation Methods ====================
    
    def create_aggregation(
        self,
        project_id: str,
        expected_agents: Optional[List[AgentType]] = None,
    ) -> ResultAggregation:
        """
        Create a new result aggregation.
        
        Args:
            project_id: Project identifier
            expected_agents: List of agents expected to contribute results
        
        Returns:
            ResultAggregation instance
        """
        aggregation = ResultAggregation(
            project_id=project_id,
            started_at=datetime.utcnow(),
        )
        
        return aggregation
    
    def aggregate_agent_result(
        self,
        aggregation: ResultAggregation,
        result: AgentResult,
    ) -> ResultAggregation:
        """
        Add an agent result to aggregation and check for completion.
        
        Args:
            aggregation: ResultAggregation to update
            result: AgentResult to add
        
        Returns:
            Updated ResultAggregation
        """
        aggregation.add_result(result)
        
        if not result.success:
            aggregation.errors.append(f"Agent {result.agent_type.value} failed: {result.error}")
        
        return aggregation
    
    def aggregate_delegation_result(
        self,
        aggregation: ResultAggregation,
        delegation: TaskDelegation,
    ) -> ResultAggregation:
        """
        Add a delegation result to aggregation and check for completion.
        
        Args:
            aggregation: ResultAggregation to update
            delegation: TaskDelegation to add
        
        Returns:
            Updated ResultAggregation
        """
        aggregation.add_delegation_result(delegation)
        
        if delegation.status == TaskDelegationStatus.FAILED:
            aggregation.errors.append(f"Delegation {delegation.delegation_id} failed: {delegation.error}")
        
        return aggregation
    
    def aggregate_parallel_results(
        self,
        results: List[AgentResult],
    ) -> Dict[str, Any]:
        """
        Aggregate results from parallel agent execution.
        
        Args:
            results: List of AgentResult from parallel execution
        
        Returns:
            Aggregated output dictionary
        """
        aggregated = {
            "success_count": 0,
            "failure_count": 0,
            "artifacts": {},
            "decisions": {},
            "validation_results": {},
            "context_data": {},
            "exports": {},
            "errors": [],
            "execution_summary": [],
        }
        
        for result in results:
            if result.success:
                aggregated["success_count"] += 1
                aggregated["execution_summary"].append({
                    "agent": result.agent_type.value,
                    "status": "success",
                    "task_id": result.task_id,
                })
                
                # Merge outputs based on agent type
                if result.agent_type == AgentType.SPECIFICATION:
                    aggregated["artifacts"].update(result.output)
                elif result.agent_type == AgentType.INTERROGATION:
                    aggregated["decisions"].update(result.output)
                elif result.agent_type == AgentType.VALIDATION:
                    aggregated["validation_results"].update(result.output)
                elif result.agent_type == AgentType.CONTEXT_MEMORY:
                    aggregated["context_data"].update(result.output)
                elif result.agent_type == AgentType.DELIVERY:
                    aggregated["exports"].update(result.output)
            else:
                aggregated["failure_count"] += 1
                aggregated["errors"].append({
                    "agent": result.agent_type.value,
                    "error": result.error,
                    "task_id": result.task_id,
                })
                aggregated["execution_summary"].append({
                    "agent": result.agent_type.value,
                    "status": "failed",
                    "task_id": result.task_id,
                    "error": result.error,
                })
        
        return aggregated
    
    def merge_specification_artifacts(
        self,
        artifacts: Dict[str, Any],
        merge_strategy: str = "sequential",
    ) -> Dict[str, Any]:
        """
        Merge specification artifacts from multiple generation steps.
        
        Args:
            artifacts: Dictionary of artifact_type -> artifact_content
            merge_strategy: Strategy for merging (sequential, override, merge)
        
        Returns:
            Merged artifact dictionary
        """
        merged = {
            "prd": None,
            "api_contracts": None,
            "db_schema": None,
            "tickets": None,
            "architecture": None,
            "tests": None,
            "deployment": None,
            "merged_at": datetime.utcnow().isoformat(),
            "merge_strategy": merge_strategy,
        }
        
        for artifact_type, content in artifacts.items():
            if artifact_type in merged and merged[artifact_type] is None:
                merged[artifact_type] = content
            elif merge_strategy == "override":
                merged[artifact_type] = content
            elif merge_strategy == "merge":
                if isinstance(merged[artifact_type], str):
                    merged[artifact_type] = f"{merged[artifact_type]}\n\n{content}"
        
        return merged
    
    def aggregate_decisions(
        self,
        decision_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Aggregate decisions from interrogation agent.
        
        Args:
            decision_results: List of decision dictionaries
        
        Returns:
            Aggregated decisions dictionary
        """
        aggregated = {
            "decisions": {},
            "categories": {},
            "dependencies": [],
            "total_count": len(decision_results),
            "aggregated_at": datetime.utcnow().isoformat(),
        }
        
        for decision in decision_results:
            decision_id = decision.get("id", str(uuid4()))
            aggregated["decisions"][decision_id] = decision
            
            # Categorize decisions
            category = decision.get("category", "uncategorized")
            if category not in aggregated["categories"]:
                aggregated["categories"][category] = []
            aggregated["categories"][category].append(decision_id)
            
            # Track dependencies
            deps = decision.get("dependencies", [])
            aggregated["dependencies"].extend(deps)
        
        return aggregated
    
    def aggregate_validation_results(
        self,
        validation_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Aggregate validation results from validation agent.
        
        Args:
            validation_results: List of validation result dictionaries
        
        Returns:
            Aggregated validation report
        """
        aggregated = {
            "validations": [],
            "conflicts": [],
            "warnings": [],
            "suggestions": [],
            "overall_status": "passed",
            "aggregated_at": datetime.utcnow().isoformat(),
        }
        
        for validation in validation_results:
            aggregated["validations"].append(validation)
            
            status = validation.get("status", "unknown")
            if status == "failed":
                aggregated["overall_status"] = "failed"
                aggregated["conflicts"].append(validation)
            elif status == "warning":
                if aggregated["overall_status"] != "failed":
                    aggregated["overall_status"] = "warning"
                aggregated["warnings"].append(validation)
            
            # Collect suggestions
            for suggestion in validation.get("suggestions", []):
                aggregated["suggestions"].append(suggestion)
        
        return aggregated
    
    def create_final_report(
        self,
        aggregation: ResultAggregation,
        project_id: str,
    ) -> Dict[str, Any]:
        """
        Create a final report from aggregated results.
        
        Args:
            aggregation: ResultAggregation with all results
            project_id: Project identifier
        
        Returns:
            Final report dictionary
        """
        aggregation.status = AggregationStatus.COMPLETED
        aggregation.completed_at = datetime.utcnow()
        
        report = {
            "project_id": project_id,
            "status": "success" if aggregation.get_failure_count() == 0 else "partial",
            "summary": {
                "total_results": len(aggregation.agent_results) + len(aggregation.delegation_results),
                "successful": aggregation.get_success_count(),
                "failed": aggregation.get_failure_count(),
            },
            "artifacts": aggregation.aggregated_output.get("artifacts", {}),
            "decisions": aggregation.aggregated_output.get("decisions", {}),
            "validation_results": aggregation.aggregated_output.get("validation_results", {}),
            "context_data": aggregation.aggregated_output.get("context_data", {}),
            "exports": aggregation.aggregated_output.get("exports", {}),
            "errors": aggregation.errors,
            "completed_at": aggregation.completed_at.isoformat(),
        }
        
        return report
    
    # ==================== Parallel Execution Methods ====================
    
    def identify_parallel_tasks(
        self,
        task_types: List[TaskType],
        state: SupervisorAgentState,
    ) -> List[List[TaskType]]:
        """
        Identify which tasks can be executed in parallel.
        
        Args:
            task_types: List of task types to analyze
            state: Current state for dependency checking
        
        Returns:
            List of task groups that can run in parallel
        """
        # Group tasks by their dependencies
        independent_groups: List[List[TaskType]] = []
        pending_tasks = set(task_types)
        
        while pending_tasks:
            # Find tasks with no unmet dependencies in pending
            ready_tasks = []
            
            for task_type in pending_tasks:
                dependencies = TASK_DEPENDENCIES.get(task_type, [])
                unmet = self._check_task_dependencies(dependencies, state)
                
                if not unmet:
                    ready_tasks.append(task_type)
            
            if ready_tasks:
                independent_groups.append(ready_tasks)
                pending_tasks -= set(ready_tasks)
            else:
                # Break circular dependency by taking one task
                ready_tasks.append(next(iter(pending_tasks)))
                independent_groups.append(ready_tasks)
                pending_tasks -= set(ready_tasks)
        
        return independent_groups
    
    def create_parallel_execution(
        self,
        project_id: str,
        task_types: List[TaskType],
        agent_selections: Dict[TaskType, AgentType],
        timeout_seconds: int = 300,
    ) -> ParallelExecution:
        """
        Create a parallel execution context.
        
        Args:
            project_id: Project identifier
            task_types: Task types to execute
            agent_selections: Mapping of task type to agent
            timeout_seconds: Timeout for execution
        
        Returns:
            ParallelExecution instance
        """
        return ParallelExecution(
            project_id=project_id,
            task_types=task_types,
            agent_selections=agent_selections,
            timeout_seconds=timeout_seconds,
        )
    
    async def execute_parallel(
        self,
        execution: ParallelExecution,
        agent_instances: Dict[AgentType, Any],
    ) -> ParallelExecution:
        """
        Execute multiple agents in parallel.
        
        Args:
            execution: ParallelExecution to run
            agent_instances: Dictionary of agent instances
        
        Returns:
            Updated ParallelExecution with results
        """
        import asyncio
        
        execution.status = ParallelExecutionStatus.IN_PROGRESS
        execution.started_at = datetime.utcnow()
        
        # Create tasks for each agent
        async def execute_task(
            task_type: TaskType,
            agent_type: AgentType,
        ) -> tuple[TaskType, bool, Dict[str, Any]]:
            """Execute a single task."""
            agent = agent_instances.get(agent_type)
            
            if agent is None:
                return (task_type, False, {"error": f"Agent not found: {agent_type}"})
            
            try:
                if hasattr(agent, 'run'):
                    result = await agent.run(
                        project_id=execution.project_id,
                        thread_id=f"parallel_{execution.execution_id}",
                    )
                else:
                    result = agent.execute({})
                
                return (task_type, True, result)
            except Exception as e:
                return (task_type, False, {"error": str(e)})
        
        # Execute all tasks in parallel
        tasks = [
            execute_task(tt, execution.agent_selections[tt])
            for tt in execution.task_types
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                # Handle exception
                for tt in execution.task_types:
                    if tt not in execution.results and tt not in execution.errors:
                        execution.add_error(tt, str(result))
                        break
            else:
                task_type, success, data = result
                
                if success:
                    execution.add_result(
                        task_type,
                        AgentResult(
                            agent_type=execution.agent_selections[task_type],
                            task_id=f"parallel_{execution.execution_id}_{task_type.value}",
                            success=True,
                            output=data,
                        ),
                    )
                else:
                    execution.add_error(task_type, data.get("error", "Unknown error"))
        
        execution.completed_at = datetime.utcnow()
        
        if execution.is_successful():
            execution.status = ParallelExecutionStatus.COMPLETED
        elif execution.get_failure_count() > 0:
            execution.status = ParallelExecutionStatus.PARTIAL
        else:
            execution.status = ParallelExecutionStatus.FAILED
        
        return execution
    
    def execute_sequential(
        self,
        execution: ParallelExecution,
        agent_instances: Dict[AgentType, Any],
    ) -> ParallelExecution:
        """
        Execute multiple agents sequentially (fallback).
        
        Args:
            execution: ParallelExecution to run
            agent_instances: Dictionary of agent instances
        
        Returns:
            Updated ParallelExecution with results
        """
        execution.status = ParallelExecutionStatus.IN_PROGRESS
        execution.started_at = datetime.utcnow()
        
        for task_type in execution.task_types:
            agent_type = execution.agent_selections[task_type]
            agent = agent_instances.get(agent_type)
            
            try:
                if hasattr(agent, 'run'):
                    result = agent.run(
                        project_id=execution.project_id,
                        thread_id=f"sequential_{execution.execution_id}",
                    )
                else:
                    result = agent.execute({})
                
                execution.add_result(
                    task_type,
                    AgentResult(
                        agent_type=agent_type,
                        task_id=f"sequential_{execution.execution_id}_{task_type.value}",
                        success=True,
                        output=result if isinstance(result, dict) else {},
                    ),
                )
            except Exception as e:
                execution.add_error(task_type, str(e))
        
        execution.completed_at = datetime.utcnow()
        
        if execution.is_successful():
            execution.status = ParallelExecutionStatus.COMPLETED
        elif execution.get_failure_count() > 0:
            execution.status = ParallelExecutionStatus.PARTIAL
        else:
            execution.status = ParallelExecutionStatus.FAILED
        
        return execution
    
    def merge_parallel_results(
        self,
        execution: ParallelExecution,
    ) -> Dict[str, Any]:
        """
        Merge results from parallel execution.
        
        Args:
            execution: Completed ParallelExecution
        
        Returns:
            Merged results dictionary
        """
        merged = {
            "success_count": execution.get_success_count(),
            "failure_count": execution.get_failure_count(),
            "artifacts": {},
            "decisions": {},
            "validation_results": {},
            "context_data": {},
            "exports": {},
            "errors": execution.errors,
            "execution_summary": [],
        }
        
        for task_type, result in execution.results.items():
            agent_type = execution.agent_selections[task_type]
            
            merged["execution_summary"].append({
                "task_type": task_type.value,
                "agent": agent_type.value,
                "status": "success",
            })
            
            # Merge outputs based on agent type
            if agent_type == AgentType.SPECIFICATION:
                merged["artifacts"].update(result.output)
            elif agent_type == AgentType.INTERROGATION:
                merged["decisions"].update(result.output)
            elif agent_type == AgentType.VALIDATION:
                merged["validation_results"].update(result.output)
            elif agent_type == AgentType.CONTEXT_MEMORY:
                merged["context_data"].update(result.output)
            elif agent_type == AgentType.DELIVERY:
                merged["exports"].update(result.output)
        
        for task_type, error in execution.errors.items():
            agent_type = execution.agent_selections[task_type]
            merged["execution_summary"].append({
                "task_type": task_type.value,
                "agent": agent_type.value,
                "status": "failed",
                "error": error,
            })
        
        return merged


# ==================== Factory Functions ====================

def create_supervisor_agent(
    config: Optional[SupervisorConfig] = None,
    interrupt_manager: Optional[InterruptManager] = None,
) -> SupervisorAgent:
    """
    Create a supervisor agent instance.
    
    Args:
        config: Optional supervisor configuration
        interrupt_manager: Optional interrupt manager
    
    Returns:
        SupervisorAgent instance
    """
    return SupervisorAgent(
        config=config,
        interrupt_manager=interrupt_manager,
    )


def create_supervisor_config(
    routing_strategy: RoutingStrategy = RoutingStrategy.SEQUENTIAL,
    max_retries: int = 3,
    require_validation: bool = True,
    require_delivery: bool = True,
) -> SupervisorConfig:
    """
    Create a supervisor configuration.
    
    Args:
        routing_strategy: Default routing strategy
        max_retries: Maximum retry attempts
        require_validation: Whether validation is required
        require_delivery: Whether delivery is required
    
    Returns:
        SupervisorConfig instance
    """
    return SupervisorConfig(
        default_routing_strategy=routing_strategy,
        max_retries=max_retries,
        require_validation=require_validation,
        require_delivery=require_delivery,
    )
