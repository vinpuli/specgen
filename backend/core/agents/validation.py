"""
Validation Agent for LangGraph.

This module implements the ValidationAgent as a LangGraph StateGraph
that manages decision and artifact validation, including contradiction detection.
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from uuid import uuid4
import json

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import CheckpointSaver

from .types import (
    AgentType,
    Decision,
    Artifact,
    Contradiction,
    ValidationStatus,
    ValidationAgentState,
)
from .state import create_validation_state
from ..llm import get_llm_client, select_model, TaskComplexity


# ==================== Node Names ====================

class ValidationNode:
    """Node names for the Validation Agent."""
    START = "start"
    VALIDATE_ANSWER_FORMAT = "validate_answer_format"
    DETECT_CONTRADICTIONS = "detect_contradictions"
    CHECK_DEPENDENCIES = "check_dependencies"
    VALIDATE_ARTIFACT = "validate_artifact"
    BREAKING_CHANGE_DETECTION = "breaking_change_detection"
    GENERATE_CONFLICT_RESOLUTION = "generate_conflict_resolution"
    END = "end"


# ==================== Validation Agent ====================

class ValidationAgent:
    """
    Validation Agent for decision and artifact validation.
    
    This agent manages:
    1. Answer format validation
    2. Contradiction detection between decisions
    3. Dependency completeness checking
    4. Artifact validation against decisions
    5. Breaking change detection (brownfield)
    6. Conflict resolution generation
    """
    
    def __init__(
        self,
        checkpoint_saver: Optional[CheckpointSaver] = None,
        on_contradiction: Optional[Callable[[Contradiction], None]] = None,
        on_human_review: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Validation Agent.
        
        Args:
            checkpoint_saver: Checkpoint saver for state persistence
            on_contradiction: Callback when contradiction is detected
            on_human_review: Callback when human review is needed
        """
        self.checkpoint_saver = checkpoint_saver
        self.on_contradiction = on_contradiction
        self.on_human_review = on_human_review
        self.llm = get_llm_client()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph for the Validation Agent."""
        builder = StateGraph(
            ValidationAgentState,
            config_schema={
                "project_id": str,
                "thread_id": str,
            },
        )
        
        # Add nodes
        builder.add_node(ValidationNode.START, self._start_node)
        builder.add_node(ValidationNode.VALIDATE_ANSWER_FORMAT, self._validate_answer_format_node)
        builder.add_node(ValidationNode.DETECT_CONTRADICTIONS, self._detect_contradictions_node)
        builder.add_node(ValidationNode.CHECK_DEPENDENCIES, self._check_dependencies_node)
        builder.add_node(ValidationNode.VALIDATE_ARTIFACT, self._validate_artifact_node)
        builder.add_node(ValidationNode.BREAKING_CHANGE_DETECTION, self._breaking_change_detection_node)
        builder.add_node(ValidationNode.GENERATE_CONFLICT_RESOLUTION, self._generate_conflict_resolution_node)
        builder.add_node(ValidationNode.END, self._end_node)
        
        # Set entry point
        builder.set_entry_point(ValidationNode.START)
        
        # Add edges
        builder.add_edge(ValidationNode.START, ValidationNode.VALIDATE_ANSWER_FORMAT)
        builder.add_edge(ValidationNode.VALIDATE_ANSWER_FORMAT, ValidationNode.DETECT_CONTRADICTIONS)
        builder.add_edge(ValidationNode.DETECT_CONTRADICTIONS, ValidationNode.CHECK_DEPENDENCIES)
        builder.add_edge(ValidationNode.CHECK_DEPENDENCIES, ValidationNode.VALIDATE_ARTIFACT)
        
        # Conditional edges for contradictions
        builder.add_conditional_edges(
            ValidationNode.DETECT_CONTRADICTIONS,
            self._contradictions_router,
            {
                "conflicts": ValidationNode.GENERATE_CONFLICT_RESOLUTION,
                "clean": ValidationNode.CHECK_DEPENDENCIES,
            },
        )
        
        # After conflict resolution, check dependencies
        builder.add_edge(ValidationNode.GENERATE_CONFLICT_RESOLUTION, ValidationNode.CHECK_DEPENDENCIES)
        
        # Artifact validation leads to breaking change detection
        builder.add_edge(ValidationNode.VALIDATE_ARTIFACT, ValidationNode.BREAKING_CHANGE_DETECTION)
        
        # Breaking changes may require human review
        builder.add_conditional_edges(
            ValidationNode.BREAKING_CHANGE_DETECTION,
            self._breaking_changes_router,
            {
                "review": ValidationNode.END,  # Human review needed
                "complete": ValidationNode.END,
            },
        )
        
        # Compile with checkpoint saver
        if self.checkpoint_saver:
            builder.checkpointer = self.checkpoint_saver
        
        return builder.compile()
    
    async def _start_node(self, state: ValidationAgentState) -> ValidationAgentState:
        """Start the validation process."""
        state["messages"] = state.get("messages", [])
        state["messages"].append({
            "role": "system",
            "content": "Starting validation process.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return state
    
    async def _validate_answer_format_node(
        self,
        state: ValidationAgentState,
    ) -> ValidationAgentState:
        """Validate the format of answers."""
        decisions = state.get("decisions", {})
        
        validation_results = {}
        
        for decision_id, decision in decisions.items():
            if not hasattr(decision, "answer_text"):
                continue
            
            answer = decision.answer_text
            
            # Check format based on category
            category = getattr(decision, "category", None)
            result = self._check_answer_format(answer, category)
            validation_results[decision_id] = result
        
        state["validation_results"] = validation_results
        
        return state
    
    async def _detect_contradictions_node(
        self,
        state: ValidationAgentState,
    ) -> ValidationAgentState:
        """Detect contradictions between decisions."""
        decisions = state.get("decisions", {})
        decision_list = list(decisions.values())
        
        contradictions = {}
        pending_contradictions = []
        
        # Compare each pair of decisions
        for i, d1 in enumerate(decision_list):
            for d2 in decision_list[i + 1:]:
                result = self._check_contradiction(d1, d2)
                
                if result["is_contradiction"]:
                    contradiction = Contradiction(
                        contradiction_id=str(uuid4()),
                        decision_1_id=getattr(d1, "decision_id", str(i)),
                        decision_2_id=getattr(d2, "decision_id", str(i + 1)),
                        decision_1_text=getattr(d1, "answer_text", ""),
                        decision_2_text=getattr(d2, "answer_text", ""),
                        similarity_score=result["similarity_score"],
                        description=result["description"],
                        suggested_resolution=result.get("resolution"),
                    )
                    
                    cid = contradiction.contradiction_id
                    contradictions[cid] = contradiction
                    pending_contradictions.append(cid)
                    
                    # Notify callback
                    if self.on_contradiction:
                        self.on_contradiction(contradiction)
        
        state["contradictions"] = contradictions
        state["pending_contradictions"] = pending_contradictions
        
        return state
    
    async def _check_dependencies_node(
        self,
        state: ValidationAgentState,
    ) -> ValidationAgentState:
        """Check if all dependencies are satisfied."""
        decisions = state.get("decisions", {})
        
        dependency_checks = {}
        incomplete_dependencies = []
        
        for decision_id, decision in decisions.items():
            deps = getattr(decision, "dependencies", [])
            checks = {}
            
            for dep_id in deps:
                if dep_id in decisions:
                    dep_decision = decisions[dep_id]
                    answer = getattr(dep_decision, "answer_text", None)
                    checks[dep_id] = {
                        "exists": True,
                        "answered": answer is not None and len(answer) > 0,
                        "answer": answer,
                    }
                else:
                    checks[dep_id] = {
                        "exists": False,
                        "answered": False,
                        "answer": None,
                    }
                    if dep_id not in incomplete_dependencies:
                        incomplete_dependencies.append(dep_id)
            
            dependency_checks[decision_id] = checks
        
        state["dependency_checks"] = dependency_checks
        state["incomplete_dependencies"] = incomplete_dependencies
        
        return state
    
    async def _validate_artifact_node(
        self,
        state: ValidationAgentState,
    ) -> ValidationAgentState:
        """Validate artifacts against decisions."""
        artifacts = state.get("artifacts", [])
        decisions = state.get("decisions", {})
        
        artifact_validations = {}
        validation_errors = []
        validation_warnings = []
        
        for artifact in artifacts:
            validation = self._validate_artifact_against_decisions(artifact, decisions)
            artifact_validations[artifact.artifact_id] = validation
            
            if validation["status"] == ValidationStatus.FAILED:
                validation_errors.extend(validation.get("errors", []))
            elif validation["status"] == ValidationStatus.WARNING:
                validation_warnings.extend(validation.get("warnings", []))
        
        state["artifact_validations"] = artifact_validations
        state["validation_errors"] = validation_errors
        state["validation_warnings"] = validation_warnings
        
        return state
    
    async def _breaking_change_detection_node(
        self,
        state: ValidationAgentState,
    ) -> ValidationAgentState:
        """Detect breaking changes for brownfield projects."""
        artifacts = state.get("artifacts", [])
        
        breaking_changes = []
        breaking_change_detected = False
        
        for artifact in artifacts:
            changes = self._detect_breaking_changes(artifact)
            breaking_changes.extend(changes)
        
        if breaking_changes:
            breaking_change_detected = True
            state["requires_human_review"] = True
            state["human_review_type"] = "breaking_changes"
            
            # Notify for human review
            if self.on_human_review:
                self.on_human_review("breaking_changes")
        
        state["breaking_changes"] = breaking_changes
        state["breaking_change_detected"] = breaking_change_detected
        
        return state
    
    async def _generate_conflict_resolution_node(
        self,
        state: ValidationAgentState,
    ) -> ValidationAgentState:
        """Generate resolution for detected contradictions."""
        pending = state.get("pending_contradictions", [])
        contradictions = state.get("contradictions", {})
        
        for cid in pending:
            contradiction = contradictions.get(cid)
            if not contradiction:
                continue
            
            resolution = await self._generate_resolution(contradiction)
            contradiction.suggested_resolution = resolution
            contradiction.resolved = True
        
        # Update state
        state["pending_contradictions"] = []
        state["contradictions"] = contradictions
        
        return state
    
    async def _end_node(self, state: ValidationAgentState) -> ValidationAgentState:
        """End the validation process."""
        pending_contr = len(state.get("pending_contradictions", []))
        breaking_changes = len(state.get("breaking_changes", []))
        errors = len(state.get("validation_errors", []))
        
        summary = []
        if pending_contr > 0:
            summary.append(f"{pending_contr} contradictions detected")
        if breaking_changes > 0:
            summary.append(f"{breaking_changes} breaking changes detected")
        if errors > 0:
            summary.append(f"{errors} validation errors")
        if not summary:
            summary.append("All validations passed")
        
        state["messages"].append({
            "role": "system",
            "content": f"Validation complete: {', '.join(summary)}.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return state
    
    # ==================== Helper Methods ====================
    
    def _check_answer_format(
        self,
        answer: str,
        category: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Check if answer meets format requirements."""
        errors = []
        warnings = []
        
        # Length check
        if len(answer) < 10:
            warnings.append("Answer seems too short")
        
        # Category-specific checks
        category_value = getattr(category, "value", str(category)) if category else ""
        
        if category_value == "api_design":
            if "http" not in answer.lower() and "rest" not in answer.lower():
                warnings.append("API design should specify HTTP/REST conventions")
        
        elif category_value == "database":
            if "table" not in answer.lower() and "schema" not in answer.lower():
                warnings.append("Database decision should reference tables or schema")
        
        elif category_value == "technology":
            if len(answer) < 20:
                warnings.append("Technology decision should include justification")
        
        return {
            "status": ValidationStatus.FAILED if len(errors) > 0 else (
                ValidationStatus.WARNING if len(warnings) > 0 else ValidationStatus.PASSED
            ),
            "errors": errors,
            "warnings": warnings,
        }
    
    def _check_contradiction(
        self,
        d1: Decision,
        d2: Decision,
    ) -> Dict[str, Any]:
        """Check if two decisions contradict each other."""
        # Skip if same category
        if getattr(d1, "category", None) == getattr(d2, "category", None):
            return {"is_contradiction": False}
        
        text1 = getattr(d1, "answer_text", "")
        text2 = getattr(d2, "answer_text", "")
        
        keywords1 = set(text1.lower().split())
        keywords2 = set(text2.lower().split())
        
        # Simple heuristic: high overlap but opposite keywords
        opposite_pairs = [
            ("sql", "nosql"),
            ("rest", "graphql"),
            ("monolith", "microservice"),
            ("synchronous", "asynchronous"),
            ("centralized", "decentralized"),
        ]
        
        for pair in opposite_pairs:
            if pair[0] in keywords1 and pair[1] in keywords2:
                return {
                    "is_contradiction": True,
                    "similarity_score": 0.8,
                    "description": f"Decisions contain opposite patterns: {pair[0]} vs {pair[1]}",
                    "resolution": f"Choose one: either '{pair[0]}' or '{pair[1]}', not both",
                }
        
        return {"is_contradiction": False}
    
    async def _generate_resolution(
        self,
        contradiction: Contradiction,
    ) -> str:
        """Generate resolution for a contradiction."""
        prompt = f"""
        Two architectural decisions contradict each other:

        Decision 1: {contradiction.decision_1_text}
        Decision 2: {contradiction.decision_2_text}

        Contradiction: {contradiction.description}

        Suggest a resolution that satisfies both constraints or recommends a specific choice.
        """
        
        selection = select_model(TaskComplexity.REASONING)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert software architect resolving conflicts.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        return str(response)
    
    def _validate_artifact_against_decisions(
        self,
        artifact: Artifact,
        decisions: Dict[str, Decision],
    ) -> Dict[str, Any]:
        """Validate an artifact against decisions."""
        errors = []
        warnings = []
        
        content = getattr(artifact, "content", "")
        based_on = getattr(artifact, "based_on_decisions", [])
        
        # Check if all referenced decisions exist
        for decision_id in based_on:
            if decision_id not in decisions:
                errors.append(f"Referenced decision {decision_id} not found")
        
        # Check for decision coverage
        covered_categories = set()
        for decision_id in based_on:
            decision = decisions.get(decision_id)
            if decision:
                category = getattr(decision, "category", None)
                if category:
                    covered_categories.add(category.value)
        
        return {
            "status": ValidationStatus.FAILED if len(errors) > 0 else (
                ValidationStatus.WARNING if len(warnings) > 0 else ValidationStatus.PASSED
            ),
            "errors": errors,
            "warnings": warnings,
            "covered_categories": list(covered_categories),
        }
    
    def _detect_breaking_changes(self, artifact: Artifact) -> List[Dict[str, Any]]:
        """Detect breaking changes in an artifact."""
        breaking_changes = []
        content = getattr(artifact, "content", "")
        
        # Check for common breaking patterns
        breaking_patterns = [
            ("REMOVE", "removing"),
            ("DELETE", "deleting"),
            ("rename", "renaming"),
            ("BREAKING", "breaking"),
        ]
        
        for pattern, description in breaking_patterns:
            if pattern in content.upper():
                breaking_changes.append({
                    "type": "content_change",
                    "description": f"Potential breaking change detected: {description}",
                    "severity": "high",
                })
        
        return breaking_changes
    
    # ==================== Routing Functions ====================
    
    def _contradictions_router(self, state: ValidationAgentState) -> str:
        """Route based on contradictions found."""
        pending = state.get("pending_contradictions", [])
        if pending:
            return "conflicts"
        return "clean"
    
    def _breaking_changes_router(self, state: ValidationAgentState) -> str:
        """Route based on breaking changes."""
        if state.get("breaking_change_detected", False):
            return "review"
        return "complete"
    
    # ==================== Public Interface ====================
    
    async def validate(
        self,
        project_id: str,
        decisions: Dict[str, Decision],
        artifacts: Optional[List[Artifact]] = None,
        thread_id: Optional[str] = None,
    ) -> ValidationAgentState:
        """
        Run full validation.
        
        Args:
            project_id: Project identifier
            decisions: Dictionary of decisions
            artifacts: Optional list of artifacts
            thread_id: Thread identifier
        
        Returns:
            Validation state with results
        """
        state = create_validation_state(project_id, thread_id)
        state["decisions"] = decisions
        if artifacts:
            state["artifacts"] = artifacts
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def detect_contradictions(
        self,
        decisions: Dict[str, Decision],
    ) -> List[Contradiction]:
        """
        Detect contradictions in decisions.
        
        Args:
            decisions: Dictionary of decisions
        
        Returns:
            List of detected contradictions
        """
        state = {
            "decisions": decisions,
            "contradictions": {},
            "pending_contradictions": [],
        }
        
        await self._detect_contradictions_node(state)
        
        return list(state["contradictions"].values())
    
    async def get_state(self, thread_id: str) -> Optional[ValidationAgentState]:
        """Get the current state for a thread."""
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        try:
            return await self.graph.aget_state(config)
        except Exception:
            return None


# ==================== Factory Function ====================

def create_validation_agent(
    checkpoint_saver: Optional[CheckpointSaver] = None,
    redis_url: Optional[str] = None,
) -> ValidationAgent:
    """
    Create a Validation Agent instance.
    
    Args:
        checkpoint_saver: Optional checkpoint saver
        redis_url: Redis URL for default checkpointing
    
    Returns:
        Configured ValidationAgent instance
    """
    from ..checkpoint import get_checkpoint_saver
    
    if checkpoint_saver is None and redis_url:
        checkpoint_saver = get_checkpoint_saver(redis_url=redis_url)
    
    return ValidationAgent(checkpoint_saver=checkpoint_saver)
