"""
Specification Agent for LangGraph.

This module implements the SpecificationAgent as a LangGraph StateGraph
that manages artifact generation from decisions.
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
    ArtifactType,
    ArtifactFormat,
    SpecificationAgentState,
)
from .state import create_specification_state
from ..llm import get_llm_client, TaskComplexity, select_model


# ==================== Node Names ====================

class SpecificationNode:
    """Node names for the Specification Agent."""
    START = "start"
    CHECK_DEPENDENCIES = "check_dependencies"
    GENERATE_PRD = "generate_prd"
    GENERATE_API_CONTRACTS = "generate_api_contracts"
    GENERATE_DB_SCHEMA = "generate_db_schema"
    GENERATE_TICKETS = "generate_tickets"
    GENERATE_ARCHITECTURE = "generate_architecture"
    GENERATE_TESTS = "generate_tests"
    GENERATE_DEPLOYMENT = "generate_deployment"
    VALIDATE_ARTIFACT = "validate_artifact"
    END = "end"


# ==================== Specification Agent ====================

class SpecificationAgent:
    """
    Specification Agent for generating artifacts from decisions.
    
    This agent manages:
    1. Checking decision dependencies
    2. Generating various artifact types (PRD, API specs, etc.)
    3. Validating generated artifacts
    """
    
    def __init__(
        self,
        checkpoint_saver: Optional[CheckpointSaver] = None,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ):
        """
        Initialize the Specification Agent.
        
        Args:
            checkpoint_saver: Checkpoint saver for state persistence
            on_progress: Progress callback
        """
        self.checkpoint_saver = checkpoint_saver
        self.on_progress = on_progress
        self.llm = get_llm_client()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph for the Specification Agent."""
        builder = StateGraph(
            SpecificationAgentState,
            config_schema={
                "project_id": str,
                "thread_id": str,
            },
        )
        
        # Add nodes
        builder.add_node(SpecificationNode.START, self._start_node)
        builder.add_node(SpecificationNode.CHECK_DEPENDENCIES, self._check_dependencies_node)
        builder.add_node(SpecificationNode.GENERATE_PRD, self._generate_prd_node)
        builder.add_node(SpecificationNode.GENERATE_API_CONTRACTS, self._generate_api_contracts_node)
        builder.add_node(SpecificationNode.GENERATE_DB_SCHEMA, self._generate_db_schema_node)
        builder.add_node(SpecificationNode.GENERATE_TICKETS, self._generate_tickets_node)
        builder.add_node(SpecificationNode.GENERATE_ARCHITECTURE, self._generate_architecture_node)
        builder.add_node(SpecificationNode.GENERATE_TESTS, self._generate_tests_node)
        builder.add_node(SpecificationNode.GENERATE_DEPLOYMENT, self._generate_deployment_node)
        builder.add_node(SpecificationNode.VALIDATE_ARTIFACT, self._validate_artifact_node)
        builder.add_node(SpecificationNode.END, self._end_node)
        
        # Set entry point
        builder.set_entry_point(SpecificationNode.START)
        
        # Add edges
        builder.add_edge(SpecificationNode.START, SpecificationNode.CHECK_DEPENDENCIES)
        
        # Parallel generation edges
        builder.add_edge(SpecificationNode.CHECK_DEPENDENCIES, SpecificationNode.GENERATE_PRD)
        builder.add_edge(SpecificationNode.CHECK_DEPENDENCIES, SpecificationNode.GENERATE_API_CONTRACTS)
        builder.add_edge(SpecificationNode.CHECK_DEPENDENCIES, SpecificationNode.GENERATE_DB_SCHEMA)
        builder.add_edge(SpecificationNode.CHECK_DEPENDENCIES, SpecificationNode.GENERATE_ARCHITECTURE)
        builder.add_edge(SpecificationNode.CHECK_DEPENDENCIES, SpecificationNode.GENERATE_TESTS)
        builder.add_edge(SpecificationNode.CHECK_DEPENDENCIES, SpecificationNode.GENERATE_DEPLOYMENT)
        
        # All generation nodes go to validation
        all_generation = [
            SpecificationNode.GENERATE_PRD,
            SpecificationNode.GENERATE_API_CONTRACTS,
            SpecificationNode.GENERATE_DB_SCHEMA,
            SpecificationNode.GENERATE_TICKETS,
            SpecificationNode.GENERATE_ARCHITECTURE,
            SpecificationNode.GENERATE_TESTS,
            SpecificationNode.GENERATE_DEPLOYMENT,
        ]
        
        for node in all_generation:
            builder.add_edge(node, SpecificationNode.VALIDATE_ARTIFACT)
        
        builder.add_edge(SpecificationNode.VALIDATE_ARTIFACT, SpecificationNode.END)
        
        # Conditional edge for missing dependencies
        builder.add_conditional_edges(
            SpecificationNode.CHECK_DEPENDENCIES,
            self._dependencies_router,
            {
                "complete": all_generation,
                "incomplete": SpecificationNode.END,
            },
        )
        
        # Compile with checkpoint saver
        if self.checkpoint_saver:
            builder.checkpointer = self.checkpoint_saver
        
        return builder.compile()
    
    async def _start_node(self, state: SpecificationAgentState) -> SpecificationAgentState:
        """Start the specification process."""
        state["messages"] = state.get("messages", [])
        state["messages"].append({
            "role": "system",
            "content": "Starting specification generation process.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        state["generation_progress"] = 0.0
        
        if self.on_progress:
            self.on_progress("started", 0.0)
        
        return state
    
    async def _check_dependencies_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Check if all required decisions are made."""
        decisions = state.get("decisions", {})
        
        # Required decision categories for complete specification
        required_categories = [
            "architecture",
            "technology",
            "api_design",
            "data_model",
            "security",
        ]
        
        available = set()
        missing = []
        
        for decision_id, decision in decisions.items():
            if hasattr(decision, "category"):
                available.add(decision.category.value)
        
        for category in required_categories:
            if category not in available:
                missing.append(category)
        
        state["missing_dependencies"] = missing
        state["resolved_dependencies"] = list(available)
        
        # Update progress
        progress = 0.1
        state["generation_progress"] = progress
        if self.on_progress:
            self.on_progress("checking_dependencies", progress)
        
        return state
    
    async def _generate_prd_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Generate Product Requirements Document."""
        decisions = state.get("decisions", {})
        
        # Collect all decision text
        decision_texts = []
        for decision_id, decision in decisions.items():
            if hasattr(decision, "answer_text"):
                decision_texts.append(f"- **{decision.category.value}**: {decision.answer_text}")
        
        prompt = f"""
        Generate a comprehensive Product Requirements Document (PRD) based on the following architectural decisions:

        {chr(10).join(decision_texts)}

        The PRD should include:
        1. Executive Summary
        2. Goals and Objectives
        3. User Stories
        4. Functional Requirements
        5. Non-Functional Requirements
        6. Constraints and Assumptions
        7. Success Criteria

        Format the output as well-structured markdown.
        """
        
        selection = select_model(TaskComplexity.COMPLEX)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert product manager creating comprehensive PRDs.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        artifact = Artifact(
            artifact_id=str(uuid4()),
            project_id=state["project_id"],
            type=ArtifactType.PRD,
            format=ArtifactFormat.MARKDOWN,
            title="Product Requirements Document",
            content=str(response) if hasattr(response, "__str__") else response.text,
            based_on_decisions=list(decisions.keys()),
        )
        
        state["artifacts"][artifact.artifact_id] = artifact
        state["artifact_queue"].append(artifact.artifact_id)
        
        # Update progress
        progress = state.get("generation_progress", 0.0) + 0.15
        state["generation_progress"] = progress
        if self.on_progress:
            self.on_progress("prd_generated", progress)
        
        return state
    
    async def _generate_api_contracts_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Generate API contracts (OpenAPI)."""
        decisions = state.get("decisions", {})
        
        # Extract API-related decisions
        api_decisions = [
            d for d in decisions.values()
            if hasattr(d, "category") and d.category.value in ["api_design", "architecture"]
        ]
        
        prompt = f"""
        Generate OpenAPI 3.0 specification based on these architectural decisions:

        {json.dumps([d.answer_text if hasattr(d, 'answer_text') else str(d) for d in api_decisions], indent=2)}

        Include:
        - API title and version
        - Base path and servers
        - Authentication schemes
        - Common error responses
        - Rate limiting headers

        Return valid OpenAPI YAML.
        """
        
        selection = select_model(TaskComplexity.MODERATE)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert API designer creating OpenAPI specifications.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        artifact = Artifact(
            artifact_id=str(uuid4()),
            project_id=state["project_id"],
            type=ArtifactType.API_SPEC,
            format=ArtifactFormat.OPENAPI,
            title="API Specification",
            content=str(response),
            based_on_decisions=list(decisions.keys()),
        )
        
        state["artifacts"][artifact.artifact_id] = artifact
        state["artifact_queue"].append(artifact.artifact_id)
        
        return state
    
    async def _generate_db_schema_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Generate database schema."""
        decisions = state.get("decisions", {})
        
        # Extract data model decisions
        db_decisions = [
            d for d in decisions.values()
            if hasattr(d, "category") and d.category.value in ["data_model", "architecture"]
        ]
        
        prompt = f"""
        Generate database schema (SQL DDL and Mermaid ERD) based on:

        {json.dumps([d.answer_text if hasattr(d, 'answer_text') else str(d) for d in db_decisions], indent=2)}

        Include:
        - Create table statements with constraints
        - Indexes for performance
        - Foreign key relationships
        - Mermaid ERD diagram

        Output as markdown with SQL and Mermaid code blocks.
        """
        
        selection = select_model(TaskComplexity.MODERATE)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert database designer creating schemas.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        artifact = Artifact(
            artifact_id=str(uuid4()),
            project_id=state["project_id"],
            type=ArtifactType.DATABASE_SCHEMA,
            format=ArtifactFormat.MERMAID,
            title="Database Schema",
            content=str(response),
            based_on_decisions=list(decisions.keys()),
        )
        
        state["artifacts"][artifact.artifact_id] = artifact
        state["artifact_queue"].append(artifact.artifact_id)
        
        return state
    
    async def _generate_tickets_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Generate development tickets."""
        decisions = state.get("decisions", {})
        
        prompt = f"""
        Generate development tickets (user stories with acceptance criteria) based on:

        {json.dumps({d.decision_id: d.answer_text for d in decisions.values() if hasattr(d, 'decision_id')}, indent=2)}

        Format each ticket as:
        ## Ticket Title
        - **As a**: [user persona]
        - **I want**: [feature]
        - **So that**: [benefit]
        
        ### Acceptance Criteria
        - [ ] Criterion 1
        - [ ] Criterion 2
        
        ### Technical Notes
        - Notes here
        """
        
        selection = select_model(TaskComplexity.MODERATE)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert project manager creating tickets.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        artifact = Artifact(
            artifact_id=str(uuid4()),
            project_id=state["project_id"],
            type=ArtifactType.TICKETS,
            format=ArtifactFormat.MARKDOWN,
            title="Development Tickets",
            content=str(response),
            based_on_decisions=list(decisions.keys()),
        )
        
        state["artifacts"][artifact.artifact_id] = artifact
        state["artifact_queue"].append(artifact.artifact_id)
        
        return state
    
    async def _generate_architecture_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Generate architecture diagrams."""
        decisions = state.get("decisions", {})
        
        prompt = f"""
        Generate C4 architecture diagrams (Mermaid) based on:

        {json.dumps([d.answer_text if hasattr(d, 'answer_text') else str(d) for d in decisions.values()], indent=2)}

        Include:
        - System Context diagram
        - Container diagram
        - Component diagrams (for key areas)
        - Deployment diagram

        Use Mermaid syntax for all diagrams.
        """
        
        selection = select_model(TaskComplexity.COMPLEX)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert architect creating diagrams.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        artifact = Artifact(
            artifact_id=str(uuid4()),
            project_id=state["project_id"],
            type=ArtifactType.ARCHITECTURE_DIAGRAM,
            format=ArtifactFormat.MERMAID,
            title="Architecture Diagrams",
            content=str(response),
            based_on_decisions=list(decisions.keys()),
        )
        
        state["artifacts"][artifact.artifact_id] = artifact
        state["artifact_queue"].append(artifact.artifact_id)
        
        return state
    
    async def _generate_tests_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Generate test specifications."""
        decisions = state.get("decisions", {})
        
        prompt = f"""
        Generate Gherkin test specifications (Given-When-Then format) based on:

        {json.dumps([d.answer_text if hasattr(d, 'answer_text') else str(d) for d in decisions.values()], indent=2)}

        Include:
        - Feature files with scenarios
        - Background context
        - Examples table for scenarios
        """
        
        selection = select_model(TaskComplexity.MODERATE)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert QA engineer creating test specs.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        artifact = Artifact(
            artifact_id=str(uuid4()),
            project_id=state["project_id"],
            type=ArtifactType.TEST_PLAN,
            format=ArtifactFormat.GHERKIN,
            title="Test Specifications",
            content=str(response),
            based_on_decisions=list(decisions.keys()),
        )
        
        state["artifacts"][artifact.artifact_id] = artifact
        state["artifact_queue"].append(artifact.artifact_id)
        
        return state
    
    async def _generate_deployment_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Generate deployment guide."""
        decisions = state.get("decisions", {})
        
        prompt = f"""
        Generate deployment guide based on:

        {json.dumps([d.answer_text if hasattr(d, 'answer_text') else str(d) for d in decisions.values()], indent=2)}

        Include:
        - Infrastructure requirements
        - Environment setup
        - Build and deployment steps
        - Rollback procedures
        - Monitoring setup
        """
        
        selection = select_model(TaskComplexity.MODERATE)
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert DevOps engineer creating deployment guides.",
            model=selection.model_name if hasattr(selection, "model_name") else None,
        )
        
        artifact = Artifact(
            artifact_id=str(uuid4()),
            project_id=state["project_id"],
            type=ArtifactType.DEPLOYMENT_GUIDE,
            format=ArtifactFormat.MARKDOWN,
            title="Deployment Guide",
            content=str(response),
            based_on_decisions=list(decisions.keys()),
        )
        
        state["artifacts"][artifact.artifact_id] = artifact
        state["artifact_queue"].append(artifact.artifact_id)
        
        return state
    
    async def _validate_artifact_node(
        self,
        state: SpecificationAgentState,
    ) -> SpecificationAgentState:
        """Validate generated artifacts."""
        validation_queue = state.get("validation_queue", [])
        artifacts = state.get("artifacts", {})
        
        validated = []
        errors = []
        
        for artifact_id in validation_queue:
            artifact = artifacts.get(artifact_id)
            if not artifact:
                continue
            
            # Basic validation
            content = artifact.content if hasattr(artifact, "content") else str(artifact)
            
            if len(content) < 100:
                errors.append(f"Artifact {artifact_id} is too short")
                continue
            
            # Check for required sections based on type
            required_sections = {
                ArtifactType.PRD: ["Goals", "Requirements", "Success"],
                ArtifactType.API_SPEC: ["paths", "components", "openapi"],
                ArtifactType.DATABASE_SCHEMA: ["CREATE", "TABLE"],
            }
            
            sections = required_sections.get(artifact.type, [])
            missing = [s for s in sections if s.lower() not in content.lower()]
            
            if missing:
                errors.append(f"Artifact {artifact_id} missing sections: {missing}")
            else:
                validated.append(artifact_id)
        
        state["validated_artifacts"] = validated
        state["validation_queue"] = errors  # Store errors in queue
        
        # Update progress
        progress = 1.0
        state["generation_progress"] = progress
        if self.on_progress:
            self.on_progress("validation_complete", progress)
        
        return state
    
    async def _end_node(self, state: SpecificationAgentState) -> SpecificationAgentState:
        """End the specification process."""
        artifacts_count = len(state.get("artifacts", {}))
        validated_count = len(state.get("validated_artifacts", []))
        
        state["messages"].append({
            "role": "system",
            "content": f"Specification complete. Generated {artifacts_count} artifacts, validated {validated_count}.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return state
    
    # ==================== Routing Functions ====================
    
    def _dependencies_router(self, state: SpecificationAgentState) -> str:
        """Route based on dependency check."""
        missing = state.get("missing_dependencies", [])
        
        if not missing:
            return "complete"
        return "incomplete"
    
    # ==================== Public Interface ====================
    
    async def start(
        self,
        project_id: str,
        decisions: Dict[str, Decision],
        thread_id: Optional[str] = None,
    ) -> SpecificationAgentState:
        """
        Start the specification process.
        
        Args:
            project_id: Project identifier
            decisions: Dictionary of decisions
            thread_id: Thread identifier
        
        Returns:
            Final state after specification generation
        """
        state = create_specification_state(project_id, thread_id)
        state["decisions"] = decisions
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def generate_artifact(
        self,
        project_id: str,
        artifact_type: ArtifactType,
        decisions: Dict[str, Decision],
        thread_id: Optional[str] = None,
    ) -> Artifact:
        """
        Generate a single artifact.
        
        Args:
            project_id: Project identifier
            artifact_type: Type of artifact to generate
            decisions: Dictionary of decisions
            thread_id: Thread identifier
        
        Returns:
            Generated artifact
        """
        state = create_specification_state(project_id, thread_id)
        state["decisions"] = decisions
        state["artifact_queue"] = [artifact_type.value]
        
        # Generate based on type
        node_map = {
            ArtifactType.PRD: SpecificationNode.GENERATE_PRD,
            ArtifactType.API_SPEC: SpecificationNode.GENERATE_API_CONTRACTS,
            ArtifactType.DATABASE_SCHEMA: SpecificationNode.GENERATE_DB_SCHEMA,
            ArtifactType.TICKETS: SpecificationNode.GENERATE_TICKETS,
            ArtifactType.ARCHITECTURE_DIAGRAM: SpecificationNode.GENERATE_ARCHITECTURE,
            ArtifactType.TEST_PLAN: SpecificationNode.GENERATE_TESTS,
            ArtifactType.DEPLOYMENT_GUIDE: SpecificationNode.GENERATE_DEPLOYMENT,
        }
        
        node = node_map.get(artifact_type)
        if node:
            # Execute single node
            state = await node(state)
        
        artifacts = state.get("artifacts", {})
        return list(artifacts.values())[-1] if artifacts else None
    
    async def get_state(self, thread_id: str) -> Optional[SpecificationAgentState]:
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

def create_specification_agent(
    checkpoint_saver: Optional[CheckpointSaver] = None,
    redis_url: Optional[str] = None,
) -> SpecificationAgent:
    """
    Create a Specification Agent instance.
    
    Args:
        checkpoint_saver: Optional checkpoint saver
        redis_url: Redis URL for default checkpointing
    
    Returns:
        Configured SpecificationAgent instance
    """
    from ..checkpoint import get_checkpoint_saver
    
    if checkpoint_saver is None and redis_url:
        checkpoint_saver = get_checkpoint_saver(redis_url=redis_url)
    
    return SpecificationAgent(checkpoint_saver=checkpoint_saver)
