"""
Agent module for LangGraph-based spec generation.

This module provides the foundation for all agent implementations
including state definitions, type checking, and agent configurations.
"""

from .types import (
    # Base Types
    BaseModelWithConfig,
    Message,
    MessageRole,
    ConversationTurn,
    ToolType,
    ToolParameter,
    ToolCall,
    ToolResult,
    ToolDefinition,
    DecisionStatus,
    QuestionPriority,
    DecisionCategory,
    Decision,
    ArtifactType,
    ArtifactFormat,
    ArtifactStatus,
    Artifact,
    InterrogationState,
    Question,
    SpecificationState,
    ValidationState,
    ValidationStatus,
    Contradiction,
    ContextMemoryState,
    DeliveryState,
    CheckpointMetadata,
    InterruptType,
    HumanInterrupt,
    AgentType,
    AgentTask,
    GraphNode,
    GraphEdge,
    EdgeType,
    RetryConfig,
    NodeConfig,
    GraphConfig,
    AgentStateDict,
    InterrogationStateDict,
    SpecificationStateDict,
    ValidationStateDict,
)

from .state import (
    # Core Agent State
    AgentState,
    InterrogationAgentState,
    SpecificationAgentState,
    ValidationAgentState,
    ContextMemoryAgentState,
    DeliveryAgentState,
    SupervisorAgentState,
    
    # State Validation
    StateValidator,
    StateTransition,
    StateHistory,
    
    # State Factory
    create_initial_state,
    create_interrogation_state,
    create_specification_state,
    create_validation_state,
    create_context_memory_state,
    create_delivery_state,
    create_supervisor_state,
    
    # State Update Utilities
    update_state,
    add_message,
    add_error,
)

from .human_in_the_loop import (
    # Interrupt Types
    InterruptType,
    InterruptStatus,
    InterruptPriority,
    
    # Contradiction Types
    ContradictionResolutionOption,
    ContradictionSeverity,
    ContradictionDetails,
    
    # Decision Lock Types
    DecisionLockAction,
    DecisionLockSeverity,
    DecisionLockDetails,
    
    # Artifact Approval Types
    ArtifactApprovalAction,
    ArtifactApprovalSeverity,
    ArtifactApprovalDetails,
    
    # Interrupt Configuration
    HumanInterruptConfig,
    ContradictionInterruptConfig,
    DecisionLockInterruptConfig,
    ArtifactApprovalInterruptConfig,
    
    # Interrupt Response
    InterruptResponse,
    CustomInterruptResponse,
    ContradictionResolutionResponse,
    DecisionLockResponse,
    ArtifactApprovalResponse,
    
    # Interrupt Manager
    InterruptManager,
    
    # Interrupt Persistence
    InterruptPersistence,
    PersistentInterruptManager,
    
    # Interrupt Response Handler
    InterruptResponseHandler,
    
    # Timeout Handler Types
    TimeoutPolicy,
    TimeoutSeverity,
    TimeoutConfig,
    TimeoutEvent,
    
    # Timeout Handlers
    HumanResponseTimeoutHandler,
    TimeoutHandler,
    
    # LangGraph Helpers
    create_interrupt,
    create_command,
    resume_with_value,
    resume_with_approval,
    resume_with_rejection,
    
    # Mixin
    HumanInTheLoopMixin,
    
    # Factory Functions
    create_human_in_the_loop_manager,
    create_timeout_handler,
    
    # Decorators
    with_human_in_the_loop,
    interrupt_handler,
    conditional_interrupt,
    
    # Checkpoint Management
    InterruptCheckpointManager,
    checkpoint_before_interrupt,
    resume_from_checkpoint,
)

from .interrupt_websocket import (
    # WebSocket States
    WebSocketState,
    
    # Notification Types
    InterruptNotification,
    InterruptUpdate,
    
    # WebSocket Managers
    WebSocketInterruptManager,
    InterruptWebSocketHandler,
    
    # Factory Functions
    create_websocket_interrupt_manager,
    create_websocket_interrupt_handler,
)

from .supervisor import (
    # Supervisor Enums
    SupervisorAction,
    SupervisorStatus,
    RoutingStrategy,
    TaskType,
    TaskDelegationStatus,
    AggregationStatus,
    ParallelExecutionStatus,
    SharedStateScope,
    
    # Message Protocol Enums
    MessageProtocolType,
    MessagePriority,
    MessageStatus,
    
    # Context Sharing Enums
    ContextScope,
    ContextType,
    
    # Heartbeat & Health Monitoring Enums
    AgentHealthStatus,
    HeartbeatStatus,
    
    # Timeout & Fallback Enums
    TimeoutStrategy,
    FallbackCondition,
    
    # Supervisor Configuration
    SupervisorConfig,
    
    # Supervisor Results
    AgentResult,
    TaskDelegation,
    ResultAggregation,
    AggregatedArtifact,
    ParallelExecution,
    SupervisorDecision,
    
    # Shared State Models
    SharedStateUpdate,
    SharedStateEntry,
    SharedStateStore,
    AgentMessage,
    MessageQueue,
    
    # Message Protocol Models
    MessageProtocolVersion,
    MessageEnvelope,
    MessageAcknowledgment,
    RequestMessage,
    ResponseMessage,
    NotificationMessage,
    QueryMessage,
    QueryResultMessage,
    MessageHandler,
    MessageProtocol,
    MessageRouter,
    MessageDeliveryStatus,
    MessageProtocolManager,
    
    # Context Sharing Models
    ContextEntry,
    ContextBundle,
    ContextSharingPolicy,
    ContextShareRequest,
    ContextShareRecord,
    ContextSharingManager,
    
    # Heartbeat & Health Monitoring Models
    AgentHeartbeat,
    HeartbeatConfig,
    HealthCheckResult,
    HealthMonitorConfig,
    AgentMetrics,
    HeartbeatRecord,
    AgentHealthMonitor,
    
    # Timeout & Fallback Models
    TimeoutConfig,
    FallbackRule,
    TimeoutEvent,
    RetryAttempt,
    TimeoutManager,
    
    # Supervisor Agent
    SupervisorAgent,
    
    # Factory Functions
    create_supervisor_agent,
    create_supervisor_config,
)

from .frontend_interrupt_handler import (
    # UI States
    InterruptUIState,
    
    # Response Actions
    ResponseAction,
    
    # Frontend Models
    FrontendInterrupt,
    FrontendInterruptResponse,
    
    # Frontend Handler
    FrontendInterruptHandler,
    
    # Response Builder
    InterruptResponseBuilder,
    
    # Factory Functions
    create_frontend_interrupt_handler,
    create_response_builder,
)

__all__ = [
    # Types
    "BaseModelWithConfig",
    "Message",
    "MessageRole",
    "ConversationTurn",
    "ToolType",
    "ToolParameter",
    "ToolCall",
    "ToolResult",
    "ToolDefinition",
    "DecisionStatus",
    "QuestionPriority",
    "DecisionCategory",
    "Decision",
    "ArtifactType",
    "ArtifactFormat",
    "ArtifactStatus",
    "Artifact",
    "InterrogationState",
    "Question",
    "SpecificationState",
    "ValidationState",
    "ValidationStatus",
    "Contradiction",
    "ContextMemoryState",
    "DeliveryState",
    "CheckpointMetadata",
    "InterruptType",
    "HumanInterrupt",
    "AgentType",
    "AgentTask",
    "GraphNode",
    "GraphEdge",
    "EdgeType",
    "RetryConfig",
    "NodeConfig",
    "GraphConfig",
    "AgentStateDict",
    "InterrogationStateDict",
    "SpecificationStateDict",
    "ValidationStateDict",
    
    # State
    "AgentState",
    "InterrogationAgentState",
    "SpecificationAgentState",
    "ValidationAgentState",
    "ContextMemoryAgentState",
    "DeliveryAgentState",
    "SupervisorAgentState",
    "StateValidator",
    "StateTransition",
    "StateHistory",
    "create_initial_state",
    "create_interrogation_state",
    "create_specification_state",
    "create_validation_state",
    "create_context_memory_state",
    "create_delivery_state",
    "create_supervisor_state",
    "update_state",
    "add_message",
    "add_error",
    
    # Human-in-the-Loop
    "InterruptType",
    "InterruptStatus",
    "InterruptPriority",
    "ContradictionResolutionOption",
    "ContradictionSeverity",
    "ContradictionDetails",
    "DecisionLockAction",
    "DecisionLockSeverity",
    "DecisionLockDetails",
    "ArtifactApprovalAction",
    "ArtifactApprovalSeverity",
    "ArtifactApprovalDetails",
    "HumanInterruptConfig",
    "ContradictionInterruptConfig",
    "DecisionLockInterruptConfig",
    "ArtifactApprovalInterruptConfig",
    "InterruptResponse",
    "CustomInterruptResponse",
    "ContradictionResolutionResponse",
    "DecisionLockResponse",
    "ArtifactApprovalResponse",
    "InterruptManager",
    "InterruptPersistence",
    "PersistentInterruptManager",
    "InterruptResponseHandler",
    "TimeoutPolicy",
    "TimeoutSeverity",
    "TimeoutConfig",
    "TimeoutEvent",
    "HumanResponseTimeoutHandler",
    "TimeoutHandler",
    "create_interrupt",
    "create_command",
    "resume_with_value",
    "resume_with_approval",
    "resume_with_rejection",
    "HumanInTheLoopMixin",
    "create_human_in_the_loop_manager",
    "create_timeout_handler",
    "with_human_in_the_loop",
    "interrupt_handler",
    "conditional_interrupt",
    "InterruptCheckpointManager",
    "checkpoint_before_interrupt",
    "resume_from_checkpoint",
    
    # WebSocket Integration
    "WebSocketState",
    "InterruptNotification",
    "InterruptUpdate",
    "WebSocketInterruptManager",
    "InterruptWebSocketHandler",
    "create_websocket_interrupt_manager",
    "create_websocket_interrupt_handler",
    
    # Frontend Interrupt Handling
    "InterruptUIState",
    "ResponseAction",
    "FrontendInterrupt",
    "FrontendInterruptResponse",
    "FrontendInterruptHandler",
    "InterruptResponseBuilder",
    "create_frontend_interrupt_handler",
    "create_response_builder",
    
    # Supervisor Agent
    "SupervisorAction",
    "SupervisorStatus",
    "RoutingStrategy",
    "TaskType",
    "TaskDelegationStatus",
    "AggregationStatus",
    "ParallelExecutionStatus",
    "SharedStateScope",
    "MessageProtocolType",
    "MessagePriority",
    "MessageStatus",
    "ContextScope",
    "ContextType",
    "AgentHealthStatus",
    "HeartbeatStatus",
    "TimeoutStrategy",
    "FallbackCondition",
    "SupervisorConfig",
    "AgentResult",
    "TaskDelegation",
    "ResultAggregation",
    "AggregatedArtifact",
    "ParallelExecution",
    "SupervisorDecision",
    "SharedStateUpdate",
    "SharedStateEntry",
    "SharedStateStore",
    "AgentMessage",
    "MessageQueue",
    "MessageProtocolVersion",
    "MessageEnvelope",
    "MessageAcknowledgment",
    "RequestMessage",
    "ResponseMessage",
    "NotificationMessage",
    "QueryMessage",
    "QueryResultMessage",
    "MessageHandler",
    "MessageProtocol",
    "MessageRouter",
    "MessageDeliveryStatus",
    "MessageProtocolManager",
    "ContextEntry",
    "ContextBundle",
    "ContextSharingPolicy",
    "ContextShareRequest",
    "ContextShareRecord",
    "ContextSharingManager",
    "AgentHeartbeat",
    "HeartbeatConfig",
    "HealthCheckResult",
    "HealthMonitorConfig",
    "AgentMetrics",
    "HeartbeatRecord",
    "AgentHealthMonitor",
    "TimeoutConfig",
    "FallbackRule",
    "TimeoutEvent",
    "RetryAttempt",
    "TimeoutManager",
    "SupervisorAgent",
    "create_supervisor_agent",
    "create_supervisor_config",
]

# Tools
export_from_submodule("tools")
