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

from .streaming import (
    # Event Types
    EventType,
    StreamEventCategory,
    FrontendEventType,
    
    # Event Classes
    StreamEvent,
    TokenEvent,
    CheckpointEvent,
    ProgressEvent,
    
    # Progress Tracking
    ProgressConfig,
    ProgressPhase,
    ProgressMilestone,
    ProgressTracker,
    CheckpointProgressHandler,
    
    # Streaming Configuration
    StreamingConfig,
    FrontendStreamConfig,
    
    # Token Buffer
    TokenBuffer,
    
    # Base Handler
    StreamHandler,
    
    # Specialized Handlers
    LLMOutputHandler,
    ToolOutputHandler,
    AgentOutputHandler,
    CheckpointHandler,
    CompositeHandler,
    
    # Streaming Managers
    StreamingManager,
    TokenStreamingManager,
    WebSocketStreamManager,
    FrontendWebSocketBridge,
    
    # Factory Functions
    create_streaming_manager,
    create_websocket_manager,
    create_frontend_websocket_bridge,
    create_llm_handler,
    create_tool_handler,
    create_agent_handler,
    create_checkpoint_handler,
    create_checkpoint_progress_handler,
    create_progress_tracker,
    create_default_phases,
    create_composite_handler,
    create_token_streaming_manager,
    create_token_buffer,
    
    # Filter Helpers
    filter_llm_events,
    filter_tool_events,
    filter_agent_events,
)

from .visualization import (
    VisualizationFormat,
    GraphVisualizationArtifact,
    GraphStructureNode,
    GraphStructureEdge,
    GraphStructure,
    GraphStructureDiff,
    CheckpointStateSummary,
    CheckpointHistoryVisualization,
    ExecutionTraceStep,
    ExecutionTraceView,
    LangSmithDebugView,
    LangGraphVisualizer,
    create_langgraph_visualizer,
)

from .tools import (
    # Database tools
    DatabaseToolNode,
    GetUserTool,
    GetProjectTool,
    GetDecisionsTool,
    CreateDecisionTool,
    GetArtifactsTool,
    CreateArtifactTool,
    GetBranchesTool,
    AddCommentTool,
    UpdateProjectTool,
    
    # Vector store tools
    VectorStoreToolNode,
    SearchDecisionsTool,
    IndexDecisionTool,
    SearchArtifactsTool,
    IndexArtifactTool,
    GetRAGContextTool,
    FindSimilarDecisionsTool,
    DeleteFromIndexTool,
    create_vector_tools,
    
    # File operation tools
    FileOperationToolNode,
    ReadFileTool,
    WriteFileTool,
    ListDirectoryTool,
    GlobSearchTool,
    GetFileInfoTool,
    DeleteFileTool,
    CopyFileTool,
    MoveFileTool,
    CreateDirectoryTool,
    create_file_tools,
    
    # Git operation tools
    GitToolNode,
    CloneRepoTool,
    InitRepoTool,
    ListBranchesTool,
    CheckoutBranchTool,
    GetCommitLogTool,
    GetDiffTool,
    CommitChangesTool,
    PushChangesTool,
    PullChangesTool,
    GitStatusTool,
    create_git_tools,
    
    # Code analysis tools
    CodeAnalysisToolNode,
    DetectLanguageTool,
    ParseASTTool,
    ExtractFunctionsTool,
    ExtractClassesTool,
    ExtractImportsTool,
    GetCodeMetricsTool,
    ScanDirectoryTool,
    create_code_analysis_tools,
    
    # Error handling
    ToolError,
    ToolErrorSeverity,
    ToolErrorCategory,
    ToolErrorCode,
    ToolExecutionResult,
    ErrorRecoveryStrategy,
    ErrorRecoveryRule,
    ToolErrorHandler,
    ToolExecutor,
    create_error_handler,
    create_tool_executor,
    with_error_handling,
    
    # Tool registry
    ToolRegistry,
    ToolStatus,
    ToolCategory,
    ToolMetadata,
    ToolSchema,
    RegisteredTool,
    ToolFilter,
    get_registry,
    register_tool,
    register_decorator,
    list_tools,
    list_tool_instances,
    get_tool,
    get_tool_by_name,
    search_tools,
    
    # Validation
    ToolValidator,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    ValidationCategory,
    SchemaDefinition,
    create_validator,
    validate_tool_input,
    validate_tool_output,
    generate_schema_from_model,
    
    # Documentation
    ToolDocumentationGenerator,
    ToolDoc,
    ParameterDoc,
    ExampleDoc,
    DocFormat,
    create_documentation_generator,
    create_auto_documenter,
    
    # Versioning
    ToolVersionManager,
    CompatibilityChecker,
    VersionInfo,
    BreakingChange,
    CompatibilityReport,
    ToolVersion,
    VersionChangeType,
    CompatibilityLevel,
    BreakingChangeType,
    DeprecationStatus,
    create_version_manager,
    create_compatibility_checker,
    parse_version,
    compare_versions,
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
    
    # Streaming
    "EventType",
    "StreamEventCategory",
    "FrontendEventType",
    "StreamEvent",
    "TokenEvent",
    "CheckpointEvent",
    "ProgressEvent",
    "ProgressConfig",
    "ProgressPhase",
    "ProgressMilestone",
    "ProgressTracker",
    "CheckpointProgressHandler",
    "StreamingConfig",
    "FrontendStreamConfig",
    "TokenBuffer",
    "StreamHandler",
    "LLMOutputHandler",
    "ToolOutputHandler",
    "AgentOutputHandler",
    "CheckpointHandler",
    "CompositeHandler",
    "StreamingManager",
    "TokenStreamingManager",
    "WebSocketStreamManager",
    "FrontendWebSocketBridge",
    "create_streaming_manager",
    "create_websocket_manager",
    "create_frontend_websocket_bridge",
    "create_llm_handler",
    "create_tool_handler",
    "create_agent_handler",
    "create_checkpoint_handler",
    "create_checkpoint_progress_handler",
    "create_progress_tracker",
    "create_default_phases",
    "create_composite_handler",
    "create_token_streaming_manager",
    "create_token_buffer",
    "filter_llm_events",
    "filter_tool_events",
    "filter_agent_events",
    
    # Visualization
    "VisualizationFormat",
    "GraphVisualizationArtifact",
    "GraphStructureNode",
    "GraphStructureEdge",
    "GraphStructure",
    "GraphStructureDiff",
    "CheckpointStateSummary",
    "CheckpointHistoryVisualization",
    "ExecutionTraceStep",
    "ExecutionTraceView",
    "LangSmithDebugView",
    "LangGraphVisualizer",
    "create_langgraph_visualizer",
    
    # Tools
    # Database tools
    "DatabaseToolNode",
    "GetUserTool",
    "GetProjectTool",
    "GetDecisionsTool",
    "CreateDecisionTool",
    "GetArtifactsTool",
    "CreateArtifactTool",
    "GetBranchesTool",
    "AddCommentTool",
    "UpdateProjectTool",
    # Vector store tools
    "VectorStoreToolNode",
    "SearchDecisionsTool",
    "IndexDecisionTool",
    "SearchArtifactsTool",
    "IndexArtifactTool",
    "GetRAGContextTool",
    "FindSimilarDecisionsTool",
    "DeleteFromIndexTool",
    "create_vector_tools",
    # File operation tools
    "FileOperationToolNode",
    "ReadFileTool",
    "WriteFileTool",
    "ListDirectoryTool",
    "GlobSearchTool",
    "GetFileInfoTool",
    "DeleteFileTool",
    "CopyFileTool",
    "MoveFileTool",
    "CreateDirectoryTool",
    "create_file_tools",
    # Git operation tools
    "GitToolNode",
    "CloneRepoTool",
    "InitRepoTool",
    "ListBranchesTool",
    "CheckoutBranchTool",
    "GetCommitLogTool",
    "GetDiffTool",
    "CommitChangesTool",
    "PushChangesTool",
    "PullChangesTool",
    "GitStatusTool",
    "create_git_tools",
    # Code analysis tools
    "CodeAnalysisToolNode",
    "DetectLanguageTool",
    "ParseASTTool",
    "ExtractFunctionsTool",
    "ExtractClassesTool",
    "ExtractImportsTool",
    "GetCodeMetricsTool",
    "ScanDirectoryTool",
    "create_code_analysis_tools",
    # Error handling
    "ToolError",
    "ToolErrorSeverity",
    "ToolErrorCategory",
    "ToolErrorCode",
    "ToolExecutionResult",
    "ErrorRecoveryStrategy",
    "ErrorRecoveryRule",
    "ToolErrorHandler",
    "ToolExecutor",
    "create_error_handler",
    "create_tool_executor",
    "with_error_handling",
    # Tool registry
    "ToolRegistry",
    "ToolStatus",
    "ToolCategory",
    "ToolMetadata",
    "ToolSchema",
    "RegisteredTool",
    "ToolFilter",
    "get_registry",
    "register_tool",
    "register_decorator",
    "list_tools",
    "list_tool_instances",
    "get_tool",
    "get_tool_by_name",
    "search_tools",
    # Validation
    "ToolValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationCategory",
    "SchemaDefinition",
    "create_validator",
    "validate_tool_input",
    "validate_tool_output",
    "generate_schema_from_model",
    # Documentation
    "ToolDocumentationGenerator",
    "ToolDoc",
    "ParameterDoc",
    "ExampleDoc",
    "DocFormat",
    "create_documentation_generator",
    "create_auto_documenter",
    # Versioning
    "ToolVersionManager",
    "CompatibilityChecker",
    "VersionInfo",
    "BreakingChange",
    "CompatibilityReport",
    "ToolVersion",
    "VersionChangeType",
    "CompatibilityLevel",
    "BreakingChangeType",
    "DeprecationStatus",
    "create_version_manager",
    "create_compatibility_checker",
    "parse_version",
    "compare_versions",
]

