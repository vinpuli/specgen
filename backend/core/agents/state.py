"""
Agent State Management for LangGraph.

This module defines the core state structures for all agents,
including TypedDict definitions, state validation, and state transitions.
"""

from typing import (
    Any, Dict, List, Optional, Union, TypedDict, NotRequired,
    Annotated, Literal, Callable
)
from datetime import datetime
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator

from .types import (
    Message,
    ToolCall,
    ToolResult,
    Decision,
    Question,
    Artifact,
    Contradiction,
    InterruptType,
    HumanInterrupt,
    AgentType,
)


# ==================== Core Agent State ====================

class AgentState(TypedDict):
    """
    Core state shared across all agents.
    
    This is the base state structure that all agent-specific
    states extend from.
    """
    # Core identifiers
    project_id: str
    thread_id: str
    run_id: str
    
    # Conversation
    messages: List[Message]
    message_history: List[Dict[str, Any]]
    
    # Context and memory
    context: Dict[str, Any]
    retrieved_context: List[Dict[str, Any]]
    
    # Execution metadata
    metadata: Dict[str, Any]
    errors: List[Dict[str, Any]]
    
    # Checkpointing
    checkpoint_id: Optional[str]
    version: int


class InterrogationAgentState(AgentState):
    """
    State for the Interrogation Agent.
    
    Manages the question-answer flow for gathering user decisions.
    """
    # Questions
    pending_questions: List[Question]
    answered_question_ids: List[str]
    deferred_question_ids: List[str]
    current_question_id: Optional[str]
    
    # Question generation
    generated_questions: List[Question]
    question_queue: List[str]  # question_ids
    
    # Context
    rag_context: List[Dict[str, Any]]
    decision_context: Dict[str, Decision]
    
    # Validation
    answer_validated: bool
    validation_errors: List[str]
    
    # AI assistance
    ai_suggested_answer: Optional[str]
    ai_decision_made: bool


class SpecificationAgentState(AgentState):
    """
    State for the Specification Agent.
    
    Manages artifact generation from decisions.
    """
    # Decisions
    decisions: Dict[str, Decision]
    locked_decisions: List[str]
    
    # Artifacts
    artifacts: Dict[str, Artifact]
    current_artifact_id: Optional[str]
    artifact_queue: List[str]  # artifact_ids
    
    # Generation
    generated_content: Dict[str, Any]
    generation_progress: float
    
    # Dependencies
    missing_dependencies: List[str]
    resolved_dependencies: List[str]
    
    # Validation
    validation_queue: List[str]  # artifact_ids to validate
    validated_artifacts: List[str]


class ValidationAgentState(AgentState):
    """
    State for the Validation Agent.
    
    Manages decision and artifact validation.
    """
    # Decisions
    decisions: Dict[str, Decision]
    
    # Contradictions
    contradictions: Dict[str, Contradiction]
    pending_contradictions: List[str]
    resolved_contradictions: List[str]
    
    # Dependency checks
    dependency_checks: Dict[str, bool]
    incomplete_dependencies: List[str]
    
    # Artifact validation
    artifact_validations: Dict[str, Dict[str, Any]]
    validation_errors: List[str]
    validation_warnings: List[str]
    
    # Breaking changes
    breaking_changes: List[Dict[str, Any]]
    breaking_change_detected: bool
    
    # Human review
    requires_human_review: bool
    human_review_type: Optional[str]


class ContextMemoryAgentState(AgentState):
    """
    State for the Context Memory Agent.
    
    Manages RAG context retrieval and decision storage.
    """
    # Retrieval
    query: str
    retrieved_documents: List[Dict[str, Any]]
    similarity_scores: Dict[str, float]
    
    # Embeddings
    embedding_used: Optional[str]
    embedding_dimensions: int
    
    # Storage
    decision_to_store: Optional[Decision]
    stored_decision_id: Optional[str]
    
    # Search
    search_query: str
    search_results: List[Dict[str, Any]]
    search_threshold: float
    
    # Context window
    context_window_used: bool
    tokens_used: int
    tokens_remaining: int


class DeliveryAgentState(AgentState):
    """
    State for the Delivery Agent.
    
    Manages artifact export and delivery.
    """
    # Artifacts
    artifacts: Dict[str, Artifact]
    selected_artifact_ids: List[str]
    
    # Export
    export_format: str
    export_path: Optional[str]
    exported_content: Dict[str, str]
    export_status: str
    
    # Delivery
    delivery_method: str
    delivery_status: str
    delivery_destination: Optional[str]
    
    # Notifications
    notification_sent: bool
    notification_type: Optional[str]


class SupervisorAgentState(AgentState):
    """
    State for the Supervisor Agent.
    
    Orchestrates all other agents.
    """
    # Agent delegation
    current_agent: Optional[AgentType]
    agent_queue: List[AgentType]
    completed_agents: List[AgentType]
    
    # Task management
    current_task_id: Optional[str]
    task_queue: List[str]
    completed_tasks: List[str]
    
    # Coordination
    agent_outputs: Dict[str, Any]
    agent_inputs: Dict[str, Any]
    
    # Flow control
    should_continue: bool
    should_interrupt: bool
    interrupt_type: Optional[str]
    
    # Human-in-the-loop
    pending_interrupts: List[HumanInterrupt]
    completed_interrupts: List[str]


# ==================== State Validation ====================

class StateValidator:
    """
    Validator for agent states.
    
    Provides validation logic for state transitions.
    """
    
    @staticmethod
    def validate_agent_state(state: AgentState) -> List[str]:
        """Validate core agent state."""
        errors = []
        
        if not state.get("project_id"):
            errors.append("project_id is required")
        
        if not state.get("thread_id"):
            errors.append("thread_id is required")
        
        if not isinstance(state.get("messages", []), list):
            errors.append("messages must be a list")
        
        if not isinstance(state.get("context", {}), dict):
            errors.append("context must be a dict")
        
        return errors
    
    @staticmethod
    def validate_interrogation_state(state: InterrogationAgentState) -> List[str]:
        """Validate interrogation agent state."""
        errors = StateValidator.validate_agent_state(state)
        
        # Validate questions
        questions = state.get("pending_questions", [])
        for i, q in enumerate(questions):
            if not q.get("question_id"):
                errors.append(f"Question {i} missing question_id")
            if not q.get("text"):
                errors.append(f"Question {i} missing text")
        
        return errors
    
    @staticmethod
    def validate_specification_state(state: SpecificationAgentState) -> List[str]:
        """Validate specification agent state."""
        errors = StateValidator.validate_agent_state(state)
        
        # Validate decisions
        decisions = state.get("decisions", {})
        for did, decision in decisions.items():
            if not decision.get("decision_id"):
                errors.append(f"Decision {did} missing decision_id")
        
        return errors
    
    @staticmethod
    def validate_validation_state(state: ValidationAgentState) -> List[str]:
        """Validate validation agent state."""
        errors = StateValidator.validate_agent_state(state)
        
        # Check for contradictions
        contradictions = state.get("contradictions", {})
        for cid, contr in contradictions.items():
            if not contr.get("decision_1_id") or not contr.get("decision_2_id"):
                errors.append(f"Contradiction {cid} missing decision references")
        
        return errors


# ==================== State Transitions ====================

class StateTransition:
    """
    Represents a state transition.
    
    Used for tracking state changes and enabling undo/redo.
    """
    
    def __init__(
        self,
        from_state: Dict[str, Any],
        to_state: Dict[str, Any],
        node_name: str,
        action: str,
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.node_name = node_name
        self.action = action
        self.timestamp = datetime.utcnow()
        self.transition_id = str(uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transition to dictionary."""
        return {
            "transition_id": self.transition_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "node_name": self.node_name,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }


class StateHistory:
    """
    Manages state history for undo/redo functionality.
    
    Tracks all state transitions for an agent run.
    """
    
    def __init__(self, max_history: int = 100):
        self.transitions: List[StateTransition] = []
        self.current_index: int = -1
        self.max_history = max_history
    
    def add_transition(self, transition: StateTransition):
        """Add a new transition."""
        # Remove any future states if we're not at the end
        if self.current_index < len(self.transitions) - 1:
            self.transitions = self.transitions[:self.current_index + 1]
        
        self.transitions.append(transition)
        self.current_index = len(self.transitions) - 1
        
        # Trim history if needed
        if len(self.transitions) > self.max_history:
            self.transitions = self.transitions[-self.max_history:]
            self.current_index = len(self.transitions) - 1
    
    def undo(self) -> Optional[StateTransition]:
        """Undo the last transition."""
        if self.current_index >= 0:
            transition = self.transitions[self.current_index]
            self.current_index -= 1
            return transition
        return None
    
    def redo(self) -> Optional[StateTransition]:
        """Redo the next transition."""
        if self.current_index < len(self.transitions) - 1:
            self.current_index += 1
            return self.transitions[self.current_index]
        return None
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return self.current_index < len(self.transitions) - 1
    
    def get_current_state(self) -> Optional[Dict[str, Any]]:
        """Get the current state after all transitions."""
        if self.transitions:
            return self.transitions[self.current_index].to_state if self.current_index >= 0 else {}
        return {}


# ==================== State Factory ====================

def create_initial_state(
    project_id: str,
    thread_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentState:
    """
    Create an initial agent state.
    
    Args:
        project_id: Project identifier
        thread_id: Thread identifier (generated if not provided)
        metadata: Optional initial metadata
    
    Returns:
        Initial AgentState
    """
    return AgentState(
        project_id=project_id,
        thread_id=thread_id or str(uuid4()),
        run_id=str(uuid4()),
        messages=[],
        message_history=[],
        context={},
        retrieved_context=[],
        metadata=metadata or {},
        errors=[],
        checkpoint_id=None,
        version=1,
    )


def create_interrogation_state(
    project_id: str,
    thread_id: Optional[str] = None,
) -> InterrogationAgentState:
    """Create an initial interrogation agent state."""
    base = create_initial_state(project_id, thread_id)
    
    return InterrogationAgentState(
        **base,
        pending_questions=[],
        answered_question_ids=[],
        deferred_question_ids=[],
        current_question_id=None,
        generated_questions=[],
        question_queue=[],
        rag_context=[],
        decision_context={},
        answer_validated=False,
        validation_errors=[],
        ai_suggested_answer=None,
        ai_decision_made=False,
    )


def create_specification_state(
    project_id: str,
    thread_id: Optional[str] = None,
) -> SpecificationAgentState:
    """Create an initial specification agent state."""
    base = create_initial_state(project_id, thread_id)
    
    return SpecificationAgentState(
        **base,
        decisions={},
        locked_decisions=[],
        artifacts={},
        current_artifact_id=None,
        artifact_queue=[],
        generated_content={},
        generation_progress=0.0,
        missing_dependencies=[],
        resolved_dependencies=[],
        validation_queue=[],
        validated_artifacts=[],
    )


def create_validation_state(
    project_id: str,
    thread_id: Optional[str] = None,
) -> ValidationAgentState:
    """Create an initial validation agent state."""
    base = create_initial_state(project_id, thread_id)
    
    return ValidationAgentState(
        **base,
        decisions={},
        contradictions={},
        pending_contradictions=[],
        resolved_contradictions=[],
        dependency_checks={},
        incomplete_dependencies=[],
        artifact_validations={},
        validation_errors=[],
        validation_warnings=[],
        breaking_changes=[],
        breaking_change_detected=False,
        requires_human_review=False,
        human_review_type=None,
    )


def create_context_memory_state(
    project_id: str,
    query: str,
    thread_id: Optional[str] = None,
) -> ContextMemoryAgentState:
    """Create an initial context memory agent state."""
    base = create_initial_state(project_id, thread_id)
    
    return ContextMemoryAgentState(
        **base,
        query=query,
        retrieved_documents=[],
        similarity_scores={},
        embedding_used=None,
        embedding_dimensions=0,
        decision_to_store=None,
        stored_decision_id=None,
        search_query=query,
        search_results=[],
        search_threshold=0.7,
        context_window_used=False,
        tokens_used=0,
        tokens_remaining=0,
    )


def create_delivery_state(
    project_id: str,
    thread_id: Optional[str] = None,
) -> DeliveryAgentState:
    """Create an initial delivery agent state."""
    base = create_initial_state(project_id, thread_id)
    
    return DeliveryAgentState(
        **base,
        artifacts={},
        selected_artifact_ids=[],
        export_format="markdown",
        export_path=None,
        exported_content={},
        export_status="pending",
        delivery_method="download",
        delivery_status="pending",
        delivery_destination=None,
        notification_sent=False,
        notification_type=None,
    )


def create_supervisor_state(
    project_id: str,
    thread_id: Optional[str] = None,
) -> SupervisorAgentState:
    """Create an initial supervisor agent state."""
    base = create_initial_state(project_id, thread_id)
    
    return SupervisorAgentState(
        **base,
        current_agent=None,
        agent_queue=[],
        completed_agents=[],
        current_task_id=None,
        task_queue=[],
        completed_tasks=[],
        agent_outputs={},
        agent_inputs={},
        should_continue=True,
        should_interrupt=False,
        interrupt_type=None,
        pending_interrupts=[],
        completed_interrupts=[],
    )


# ==================== State Update Utilities ====================

def update_state(
    current_state: Dict[str, Any],
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Safely update state with new values.
    
    Args:
        current_state: Current state dictionary
        updates: Updates to apply
    
    Returns:
        Updated state
    """
    new_state = current_state.copy()
    new_state.update(updates)
    return new_state


def add_message(
    state: AgentState,
    role: str,
    content: str,
    name: Optional[str] = None,
) -> AgentState:
    """
    Add a message to the state.
    
    Args:
        state: Current state
        role: Message role (user, assistant, system)
        content: Message content
        name: Optional message sender name
    
    Returns:
        Updated state
    """
    message = Message(
        role=role,
        content=content,
        name=name,
    )
    
    state["messages"].append(message)
    state["message_history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    return state


def add_error(
    state: AgentState,
    error_message: str,
    error_type: str = "general",
    node_name: Optional[str] = None,
) -> AgentState:
    """
    Add an error to the state.
    
    Args:
        state: Current state
        error_message: Error message
        error_type: Error type
        node_name: Node where error occurred
    
    Returns:
        Updated state
    """
    state["errors"].append({
        "message": error_message,
        "type": error_type,
        "node": node_name,
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    return state
