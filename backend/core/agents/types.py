"""
LangGraph SDK type definitions for the Agentic Spec Builder.

This module provides comprehensive type definitions for all agent states,
messages, nodes, and edges used in the LangGraph-based spec generation system.
"""

from typing import (
    Any, Dict, List, Optional, Union, Callable, TypeVar, Generic,
    TypedDict, NotRequired, Literal, Annotated
)
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
import json


# ==================== Base Types ====================

T = TypeVar("T")


class BaseModelWithConfig(BaseModel):
    """Base model with common configuration."""
    
    class Config:
        populate_by_name = True
        extra = "forbid"


# ==================== Message Types ====================

class MessageRole(str, Enum):
    """Role types for messages."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    FUNCTION = "function"


class Message(BaseModelWithConfig):
    """Base message structure."""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List["ToolCall"]] = None
    tool_call_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModelWithConfig):
    """A turn in the conversation between user and agent."""
    turn_id: str = Field(default_factory=lambda: str(uuid4()))
    user_message: Message
    assistant_message: Message
    tool_calls: List["ToolCall"] = Field(default_factory=list)
    tool_results: List["ToolResult"] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None


# ==================== Tool Types ====================

class ToolType(str, Enum):
    """Types of tools available to agents."""
    DATABASE_QUERY = "database_query"
    VECTOR_SEARCH = "vector_search"
    LLM_GENERATE = "llm_generate"
    CODE_ANALYSIS = "code_analysis"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    GIT_OPERATIONS = "git_operations"
    WEB_SEARCH = "web_search"
    API_CALL = "api_call"


class ToolParameter(BaseModelWithConfig):
    """Schema for a tool parameter."""
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None
    enum_values: Optional[List[Any]] = None


class ToolCall(BaseModelWithConfig):
    """A call to a tool."""
    id: str = Field(default_factory=lambda: f"call_{uuid4().hex[:8]}")
    type: str = "tool_call"
    function: Dict[str, Any]  # {"name": "...", "arguments": "..."}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModelWithConfig):
    """Result from a tool execution."""
    tool_call_id: str
    tool_name: str
    content: Any
    success: bool = True
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None


class ToolDefinition(BaseModelWithConfig):
    """Definition of a tool available to agents."""
    name: str
    description: str
    type: ToolType
    parameters: List[ToolParameter] = Field(default_factory=list)
    requires_confirmation: bool = False
    safe_to_retry: bool = True


# ==================== Agent State Types ====================

class DecisionStatus(str, Enum):
    """Status of a decision."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    DEFERRED = "deferred"
    LOCKED = "locked"


class QuestionPriority(str, Enum):
    """Priority levels for questions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionCategory(str, Enum):
    """Categories for architectural decisions."""
    ARCHITECTURE = "architecture"
    TECHNOLOGY = "technology"
    API_DESIGN = "api_design"
    DATA_MODEL = "data_model"
    SECURITY = "security"
    PERFORMANCE = "performance"
    USER_EXPERIENCE = "user_experience"
    DEPLOYMENT = "deployment"
    COST = "cost"
    COMPLIANCE = "compliance"


class Decision(BaseModelWithConfig):
    """A decision made during the specification process."""
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    question_text: str
    answer_text: Optional[str] = None
    category: DecisionCategory
    status: DecisionStatus = DecisionStatus.PENDING
    priority: QuestionPriority = QuestionPriority.MEDIUM
    dependencies: List[str] = Field(default_factory=list)  # decision_ids
    dependent_decisions: List[str] = Field(default_factory=list)  # decision_ids
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None


class ArtifactType(str, Enum):
    """Types of artifacts that can be generated."""
    PRD = "prd"
    API_SPEC = "api_spec"
    DATABASE_SCHEMA = "database_schema"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    USER_STORIES = "user_stories"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    TECHNICAL_SPEC = "technical_spec"
    DEPLOYMENT_GUIDE = "deployment_guide"
    TEST_PLAN = "test_plan"
    TICKETS = "tickets"


class ArtifactFormat(str, Enum):
    """Output formats for artifacts."""
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    OPENAPI = "openapi"
    MERMAID = "mermaid"
    PLANTUML = "plantuml"
    GHERKIN = "gherkin"


class ArtifactStatus(str, Enum):
    """Status of artifact generation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class Artifact(BaseModelWithConfig):
    """An artifact generated from decisions."""
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    type: ArtifactType
    format: ArtifactFormat
    title: str
    content: str
    status: ArtifactStatus = ArtifactStatus.PENDING
    based_on_decisions: List[str] = Field(default_factory=list)  # decision_ids
    missing_dependencies: List[str] = Field(default_factory=list)  # decision_ids
    version: int = 1
    previous_versions: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# ==================== Interrogation State ====================

class InterrogationState(BaseModelWithConfig):
    """
    State for the Interrogation Agent.
    
    Manages the conversation flow for gathering user decisions.
    """
    project_id: str
    branch_id: Optional[str] = None
    conversation_history: List[Message] = Field(default_factory=list)
    pending_questions: List["Question"] = Field(default_factory=list)
    answered_questions: List[str] = Field(default_factory=list)  # decision_ids
    deferred_questions: List[str] = Field(default_factory=list)  # decision_ids
    current_question_id: Optional[str] = None
    context_retrieved: bool = False
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Question(BaseModelWithConfig):
    """A question to be answered by the user."""
    question_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    category: DecisionCategory
    priority: QuestionPriority = QuestionPriority.MEDIUM
    context: str = ""  # RAG-retrieved context
    suggested_answer: Optional[str] = None
    answer_options: List[str] = Field(default_factory=list)
    related_decisions: List[str] = Field(default_factory=list)
    is_multi_select: bool = False
    requires_justification: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== Specification State ====================

class SpecificationState(BaseModelWithConfig):
    """
    State for the Specification Agent.
    
    Manages artifact generation from decisions.
    """
    project_id: str
    branch_id: Optional[str] = None
    decisions: Dict[str, Decision] = Field(default_factory=dict)
    artifacts: List[Artifact] = Field(default_factory=list)
    current_artifact_type: Optional[ArtifactType] = None
    validation_queue: List[str] = Field(default_factory=list)  # artifact_ids
    completed_validations: List[str] = Field(default_factory=list)
    failed_validations: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Validation State ====================

class ValidationStatus(str, Enum):
    """Status of validation checks."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class Contradiction(BaseModelWithConfig):
    """A contradiction detected between decisions."""
    contradiction_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_1_id: str
    decision_2_id: str
    decision_1_text: str
    decision_2_text: str
    similarity_score: float
    description: str
    suggested_resolution: Optional[str] = None
    resolved: bool = False
    resolution: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ValidationState(BaseModelWithConfig):
    """
    State for the Validation Agent.
    
    Manages decision and artifact validation.
    """
    project_id: str
    decisions: Dict[str, Decision] = Field(default_factory=dict)
    artifacts: List[Artifact] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    dependency_checks: Dict[str, bool] = Field(default_factory=dict)
    validation_results: Dict[str, ValidationStatus] = Field(default_factory=dict)
    breaking_changes: List[Dict[str, Any]] = Field(default_factory=list)
    requires_human_review: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Context Memory State ====================

class ContextMemoryState(BaseModelWithConfig):
    """
    State for the Context Memory Agent.
    
    Manages RAG-based context retrieval and decision embedding storage.
    """
    project_id: str
    query: str
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    similarity_scores: Dict[str, float] = Field(default_factory=dict)
    context_window_used: bool = False
    tokens_used: int = 0
    embedding_model: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Delivery State ====================

class DeliveryState(BaseModelWithConfig):
    """
    State for the Delivery Agent.
    
    Manages artifact export and delivery.
    """
    project_id: str
    artifacts: List[Artifact] = Field(default_factory=list)
    selected_format: ArtifactFormat = ArtifactFormat.MARKDOWN
    selected_artifacts: List[str] = Field(default_factory=list)  # artifact_ids
    export_path: Optional[str] = None
    export_status: ArtifactStatus = ArtifactStatus.PENDING
    delivered_formats: List[ArtifactFormat] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Checkpoint Types ====================

class CheckpointMetadata(BaseModelWithConfig):
    """Metadata for a graph checkpoint."""
    thread_id: str
    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    agent_name: str
    version: int = 1
    parent_checkpoint_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Human-in-the-Loop Types ====================

class InterruptType(str, Enum):
    """Types of human interrupts."""
    APPROVAL = "approval"
    CORRECTION = "correction"
    SELECTION = "selection"
    CONFIRMATION = "confirmation"
    REJECTION = "rejection"


class HumanInterrupt(BaseModelWithConfig):
    """A human interrupt request."""
    interrupt_id: str = Field(default_factory=lambda: str(uuid4()))
    type: InterruptType
    node_name: str
    message: str
    options: List[str] = Field(default_factory=list)
    allow_ignore: bool = True
    allow_response: bool = True
    timeout_seconds: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    responded_at: Optional[datetime] = None
    response: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Unified Agent State ====================

class AgentType(str, Enum):
    """Types of agents in the system."""
    SUPERVISOR = "supervisor"
    INTERROGATION = "interrogation"
    SPECIFICATION = "specification"
    VALIDATION = "validation"
    CONTEXT_MEMORY = "context_memory"
    DELIVERY = "delivery"


class AgentTask(BaseModelWithConfig):
    """A task to be executed by an agent."""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    project_id: str
    branch_id: Optional[str] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    priority: QuestionPriority = QuestionPriority.MEDIUM
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ==================== Graph Edge Types ====================

class EdgeType(str, Enum):
    """Types of edges in the graph."""
    NORMAL = "normal"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"


class GraphNode(BaseModelWithConfig):
    """A node in the agent graph."""
    name: str
    node_type: str  # "llm", "tool", "function"
    agent_type: AgentType
    description: str = ""
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    tools: List[ToolDefinition] = Field(default_factory=list)
    retry_config: Optional[Dict[str, Any]] = None


class GraphEdge(BaseModelWithConfig):
    """An edge connecting nodes in the graph."""
    source: str
    target: str
    edge_type: EdgeType = EdgeType.NORMAL
    condition: Optional[str] = None  # For conditional edges
    priority: int = 0


# ==================== LangGraph Type Aliases ====================

# Type aliases for LangGraph compatibility
AgentStateDict = TypedDict(
    "AgentStateDict",
    {
        "messages": List[Message],
        "context": Dict[str, Any],
        "metadata": Dict[str, Any],
    },
)

InterrogationStateDict = TypedDict(
    "InterrogationStateDict",
    {
        "project_id": str,
        "branch_id": Optional[str],
        "conversation_history": List[Message],
        "pending_questions": List[Question],
        "answered_questions": List[str],
        "deferred_questions": List[str],
        "current_question_id": Optional[str],
        "context_retrieved": bool,
        "user_preferences": Dict[str, Any],
        "metadata": Dict[str, Any],
    },
)

SpecificationStateDict = TypedDict(
    "SpecificationStateDict",
    {
        "project_id": str,
        "branch_id": Optional[str],
        "decisions": Dict[str, Decision],
        "artifacts": List[Artifact],
        "current_artifact_type": Optional[str],
        "validation_queue": List[str],
        "completed_validations": List[str],
        "failed_validations": List[str],
        "metadata": Dict[str, Any],
    },
)

ValidationStateDict = TypedDict(
    "ValidationStateDict",
    {
        "project_id": str,
        "decisions": Dict[str, Decision],
        "artifacts": List[Artifact],
        "contradictions": List[Contradiction],
        "dependency_checks": Dict[str, bool],
        "validation_results": Dict[str, str],
        "breaking_changes": List[Dict[str, Any]],
        "requires_human_review": bool,
        "metadata": Dict[str, Any],
    },
)


# ==================== Configuration Types ====================

class RetryConfig(BaseModelWithConfig):
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 10000
    exponential_base: float = 2.0
    retryable_errors: List[str] = Field(default_factory=list)


class NodeConfig(BaseModelWithConfig):
    """Configuration for a graph node."""
    name: str
    retry_config: Optional[RetryConfig] = None
    timeout_seconds: Optional[int] = None
    human_interruptible: bool = False
    interrupt_types: List[InterruptType] = Field(default_factory=list)


class GraphConfig(BaseModelWithConfig):
    """Configuration for a graph."""
    name: str
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    entry_point: Optional[str] = None
    checkpointer: Optional[str] = None
    interrupt_before: List[str] = Field(default_factory=list)
    interrupt_after: List[str] = Field(default_factory=list)
