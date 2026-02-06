"""
Interrogation Agent for LangGraph.

This module implements the InterrogationAgent as a LangGraph StateGraph
that manages the question-answer flow for gathering user decisions.
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from uuid import uuid4

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import CheckpointSaver
from langgraph.types import Command, Interrupt

from .types import (
    AgentType,
    Question,
    QuestionPriority,
    DecisionCategory,
    Message,
    MessageRole,
    InterrogationAgentState,
)
from .state import (
    create_interrogation_state,
    add_message,
    add_error,
)
from ..llm import get_llm_client, TaskComplexity


# ==================== Node Names ====================

class InterrogationNode:
    """Node names for the Interrogation Agent."""
    START = "start"
    ANALYZE_DECISIONS = "analyze_decisions"
    GENERATE_QUESTIONS = "generate_questions"
    FORMAT_QUESTION = "format_question"
    VALIDATE_ANSWER = "validate_answer"
    UPDATE_CONTEXT = "update_context"
    DEFER_DECISION = "defer_decision"
    AI_DECIDE = "ai_decide"
    END = "end"


# ==================== Interrogation Agent ====================

class InterrogationAgent:
    """
    Interrogation Agent for gathering user decisions.
    
    This agent manages the flow of:
    1. Analyzing existing decisions for gaps
    2. Generating relevant questions
    3. Presenting questions to users
    4. Validating answers
    5. Updating the decision context
    """
    
    def __init__(
        self,
        checkpoint_saver: Optional[CheckpointSaver] = None,
        on_question_ready: Optional[Callable[[Question], None]] = None,
        on_answer_received: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize the Interrogation Agent.
        
        Args:
            checkpoint_saver: Checkpoint saver for state persistence
            on_question_ready: Callback when a question is ready for the user
            on_answer_received: Callback when an answer is received
        """
        self.checkpoint_saver = checkpoint_saver
        self.on_question_ready = on_question_ready
        self.on_answer_received = on_answer_received
        self.llm = get_llm_client()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph for the Interrogation Agent."""
        builder = StateGraph(
            InterrogationAgentState,
            config_schema={
                "project_id": str,
                "thread_id": str,
            },
        )
        
        # Add nodes
        builder.add_node(InterrogationNode.START, self._start_node)
        builder.add_node(InterrogationNode.ANALYZE_DECISIONS, self._analyze_decisions_node)
        builder.add_node(InterrogationNode.GENERATE_QUESTIONS, self._generate_questions_node)
        builder.add_node(InterrogationNode.FORMAT_QUESTION, self._format_question_node)
        builder.add_node(InterrogationNode.VALIDATE_ANSWER, self._validate_answer_node)
        builder.add_node(InterrogationNode.UPDATE_CONTEXT, self._update_context_node)
        builder.add_node(InterrogationNode.DEFER_DECISION, self._defer_decision_node)
        builder.add_node(InterrogationNode.AI_DECIDE, self._ai_decide_node)
        builder.add_node(InterrogationNode.END, self._end_node)
        
        # Set entry point
        builder.set_entry_point(InterrogationNode.START)
        
        # Add edges
        builder.add_edge(InterrogationNode.START, InterrogationNode.ANALYZE_DECISIONS)
        builder.add_edge(InterrogationNode.ANALYZE_DECISIONS, InterrogationNode.GENERATE_QUESTIONS)
        builder.add_edge(InterrogationNode.FORMAT_QUESTION, InterrogationNode.VALIDATE_ANSWER)
        
        # Conditional edges
        builder.add_conditional_edges(
            InterrogationNode.GENERATE_QUESTIONS,
            self._should_ask_question,
            {
                "ask": InterrogationNode.FORMAT_QUESTION,
                "complete": InterrogationNode.END,
            },
        )
        
        builder.add_conditional_edges(
            InterrogationNode.VALIDATE_ANSWER,
            self._validate_answer_router,
            {
                "valid": InterrogationNode.UPDATE_CONTEXT,
                "retry": InterrogationNode.FORMAT_QUESTION,
                "defer": InterrogationNode.DEFER_DECISION,
                "ai_decide": InterrogationNode.AI_DECIDE,
            },
        )
        
        builder.add_edge(InterrogationNode.UPDATE_CONTEXT, InterrogationNode.ANALYZE_DECISIONS)
        builder.add_edge(InterrogationNode.DEFER_DECISION, InterrogationNode.END)
        builder.add_edge(InterrogationNode.AI_DECIDE, InterrogationNode.UPDATE_CONTEXT)
        
        # Compile with checkpoint saver
        if self.checkpoint_saver:
            builder.checkpointer = self.checkpoint_saver
        
        return builder.compile()
    
    async def _start_node(self, state: InterrogationAgentState) -> InterrogationAgentState:
        """Start the interrogation process."""
        # Initialize state
        state["messages"].append(Message(
            role=MessageRole.SYSTEM,
            content="Starting interrogation process to gather project decisions.",
        ))
        
        return state
    
    async def _analyze_decisions_node(
        self,
        state: InterrogationAgentState,
    ) -> InterrogationAgentState:
        """Analyze existing decisions for gaps."""
        project_id = state["project_id"]
        decisions = state.get("decision_context", {})
        
        # Check for missing categories
        existing_categories = set()
        for decision in decisions.values():
            if hasattr(decision, "category"):
                existing_categories.add(decision.category)
        
        # Determine which categories need questions
        all_categories = list(DecisionCategory)
        missing_categories = [c for c in all_categories if c not in existing_categories]
        
        # Store analysis results
        if "analysis" not in state["context"]:
            state["context"]["analysis"] = {}
        
        state["context"]["analysis"]["missing_categories"] = missing_categories
        state["context"]["analysis"]["existing_categories"] = list(existing_categories)
        state["context"]["analysis"]["questions_needed"] = len(missing_categories) > 0
        
        return state
    
    async def _generate_questions_node(
        self,
        state: InterrogationAgentState,
    ) -> InterrogationAgentState:
        """Generate questions for missing decision categories."""
        missing_categories = state.get("context", {}).get("analysis", {}).get(
            "missing_categories", []
        )
        
        rag_context = state.get("rag_context", [])
        existing_questions = state.get("generated_questions", [])
        
        generated_questions = []
        
        for category in missing_categories:
            # Generate question using LLM
            prompt = f"""
            Generate a thoughtful question for the '{category.value}' decision category.
            
            Context from similar decisions:
            {rag_context[:3] if rag_context else 'No prior context available.'}
            
            Existing questions in this category:
            {[q for q in existing_questions if q.category == category]}
            
            Generate a clear, specific question that helps clarify this architectural decision.
            """
            
            response = await self.llm.agenerate(
                prompt=prompt,
                system_message="You are an expert software architect helping to define project requirements.",
            )
            
            question = Question(
                text=response.text if hasattr(response, "text") else str(response),
                category=category,
                priority=self._determine_priority(category),
                context=self._build_question_context(category, rag_context),
            )
            
            generated_questions.append(question)
        
        state["generated_questions"].extend(generated_questions)
        state["question_queue"] = [q.question_id for q in generated_questions]
        
        return state
    
    async def _format_question_node(
        self,
        state: InterrogationAgentState,
    ) -> InterrogationAgentState:
        """Format a question for presentation to the user."""
        question_queue = state.get("question_queue", [])
        
        if not question_queue:
            return state
        
        current_question_id = question_queue[0]
        questions = state.get("generated_questions", [])
        
        current_question = next(
            (q for q in questions if q.question_id == current_question_id),
            None
        )
        
        if current_question:
            # Format the question with context
            formatted_text = self._format_question_text(current_question)
            
            current_question.text = formatted_text
            state["current_question_id"] = current_question_id
            state["pending_questions"].append(current_question)
            
            # Notify callback
            if self.on_question_ready:
                self.on_question_ready(current_question)
        
        return state
    
    async def _validate_answer_node(
        self,
        state: InterrogationAgentState,
    ) -> InterrogationAgentState:
        """Validate the user's answer to a question."""
        messages = state.get("messages", [])
        
        # Get the last user message (the answer)
        user_messages = [
            m for m in messages if m.role == MessageRole.USER
        ]
        
        if not user_messages:
            state["validation_errors"] = ["No answer provided"]
            return state
        
        last_answer = user_messages[-1].content
        current_question = state.get("current_question_id")
        
        # Validate answer
        validation_result = self._validate_answer_content(
            last_answer,
            current_question,
        )
        
        state["answer_validated"] = validation_result["valid"]
        state["validation_errors"] = validation_result.get("errors", [])
        
        # Store the answer
        if validation_result["valid"]:
            state["context"]["last_answer"] = last_answer
            state["context"]["answer_validated_at"] = datetime.utcnow().isoformat()
        
        return state
    
    async def _update_context_node(
        self,
        state: InterrogationAgentState,
    ) -> InterrogationAgentState:
        """Update the context with the validated answer."""
        current_question_id = state.get("current_question_id")
        last_answer = state.get("context", {}).get("last_answer")
        
        if current_question_id and last_answer:
            # Add to answered questions
            if current_question_id not in state["answered_question_ids"]:
                state["answered_question_ids"].append(current_question_id)
            
            # Remove from question queue
            question_queue = state.get("question_queue", [])
            if current_question_id in question_queue:
                question_queue.remove(current_question_id)
            
            # Update decision context
            questions = state.get("generated_questions", [])
            question = next(
                (q for q in questions if q.question_id == current_question_id),
                None
            )
            
            if question:
                if "decisions" not in state["context"]:
                    state["context"]["decisions"] = {}
                
                state["context"]["decisions"][current_question_id] = {
                    "question": question.text,
                    "answer": last_answer,
                    "category": question.category.value,
                    "answered_at": datetime.utcnow().isoformat(),
                }
            
            # Notify callback
            if self.on_answer_received:
                self.on_answer_received(current_question_id, last_answer)
        
        # Reset validation state
        state["answer_validated"] = False
        state["validation_errors"] = []
        
        return state
    
    async def _defer_decision_node(
        self,
        state: InterrogationAgentState,
    ) -> InterrogationAgentState:
        """Handle deferred decision."""
        current_question_id = state.get("current_question_id")
        
        if current_question_id:
            # Move to deferred
            if current_question_id not in state["deferred_question_ids"]:
                state["deferred_question_ids"].append(current_question_id)
            
            # Remove from queue
            question_queue = state.get("question_queue", [])
            if current_question_id in question_queue:
                question_queue.remove(current_question_id)
        
        return state
    
    async def _ai_decide_node(
        self,
        state: InterrogationAgentState,
    ) -> InterrogationAgentState:
        """Handle AI-assisted decision making."""
        current_question_id = state.get("current_question_id")
        context = state.get("context", {})
        rag_context = state.get("rag_context", [])
        
        if not current_question_id:
            return state
        
        # Get current question
        questions = state.get("generated_questions", [])
        question = next(
            (q for q in questions if q.question_id == current_question_id),
            None
        )
        
        if not question:
            return state
        
        # Generate AI suggestion
        prompt = f"""
        Question: {question.text}
        
        Context from similar projects:
        {rag_context[:3] if rag_context else 'No prior context available.'}
        
        Based on the context and best practices, suggest an appropriate answer for this architectural decision.
        """
        
        response = await self.llm.agenerate(
            prompt=prompt,
            system_message="You are an expert software architect. Provide a thoughtful suggestion for this architectural decision.",
        )
        
        suggested_answer = str(response)
        
        state["ai_suggested_answer"] = suggested_answer
        state["ai_decision_made"] = True
        
        # Auto-accept AI decision if configured
        if state.get("context", {}).get("auto_accept_ai_decisions", False):
            state["context"]["last_answer"] = suggested_answer
            state["context"]["answer_validated_at"] = datetime.utcnow().isoformat()
            state["ai_decision_made"] = True
        
        return state
    
    async def _end_node(self, state: InterrogationAgentState) -> InterrogationAgentState:
        """End the interrogation process."""
        state["messages"].append(Message(
            role=MessageRole.SYSTEM,
            content=f"Interrogation complete. Answered {len(state['answered_question_ids'])} questions, deferred {len(state['deferred_question_ids'])}.",
        ))
        
        return state
    
    # ==================== Routing Functions ====================
    
    def _should_ask_question(self, state: InterrogationAgentState) -> str:
        """Determine if we should ask another question or end."""
        question_queue = state.get("question_queue", [])
        
        if question_queue:
            return "ask"
        return "complete"
    
    def _validate_answer_router(self, state: InterrogationAgentState) -> str:
        """Route based on validation result."""
        if state.get("answer_validated", False):
            return "valid"
        elif state.get("validation_errors"):
            # Check if too many retries
            retry_count = state.get("context", {}).get("validation_retries", 0)
            if retry_count >= 3:
                return "defer"
            return "retry"
        return "ai_decide"
    
    # ==================== Helper Methods ====================
    
    def _determine_priority(self, category: DecisionCategory) -> QuestionPriority:
        """Determine question priority based on category."""
        high_priority = [
            DecisionCategory.ARCHITECTURE,
            DecisionCategory.TECHNOLOGY,
            DecisionCategory.SECURITY,
        ]
        
        medium_priority = [
            DecisionCategory.API_DESIGN,
            DecisionCategory.DATA_MODEL,
            DecisionCategory.PERFORMANCE,
        ]
        
        if category in high_priority:
            return QuestionPriority.HIGH
        elif category in medium_priority:
            return QuestionPriority.MEDIUM
        return QuestionPriority.LOW
    
    def _build_question_context(
        self,
        category: DecisionCategory,
        rag_context: List[Dict[str, Any]],
    ) -> str:
        """Build context string for a question."""
        relevant_context = [
            c for c in rag_context
            if c.get("category") == category.value
        ]
        
        return "\n".join([
            f"Related context {i+1}: {c.get('content', '')[:500]}"
            for i, c in enumerate(relevant_context[:3])
        ])
    
    def _format_question_text(self, question: Question) -> str:
        """Format question text for presentation."""
        parts = []
        
        # Category prefix
        parts.append(f"[{question.category.value.upper()}]")
        
        # Priority indicator
        if question.priority == QuestionPriority.HIGH:
            parts.append("🔴 HIGH PRIORITY")
        elif question.priority == QuestionPriority.MEDIUM:
            parts.append("🟡 MEDIUM PRIORITY")
        
        # Question text
        parts.append(question.text)
        
        # Context
        if question.context:
            parts.append(f"\n**Context:**\n{question.context}")
        
        # Answer options
        if question.answer_options:
            parts.append("\n**Options:**")
            for i, option in enumerate(question.answer_options, 1):
                parts.append(f"{i}. {option}")
        
        return "\n".join(parts)
    
    def _validate_answer_content(
        self,
        answer: str,
        question_id: Optional[str],
    ) -> Dict[str, Any]:
        """Validate answer content."""
        errors = []
        
        # Check minimum length
        if len(answer.strip()) < 10:
            errors.append("Answer is too short (minimum 10 characters)")
        
        # Check for placeholder text
        placeholder_phrases = ["not sure", "i don't know", "maybe later"]
        if any(phrase in answer.lower() for phrase in placeholder_phrases):
            errors.append("Please provide a more specific answer")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }
    
    # ==================== Public Interface ====================
    
    async def start(
        self,
        project_id: str,
        thread_id: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Start the interrogation process.
        
        Args:
            project_id: Project identifier
            thread_id: Thread identifier
            initial_context: Optional initial context
        
        Returns:
            Final state after interrogation
        """
        state = create_interrogation_state(project_id, thread_id)
        
        if initial_context:
            state["context"].update(initial_context)
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def submit_answer(
        self,
        thread_id: str,
        answer: str,
    ) -> Any:
        """
        Submit an answer to the current question.
        
        Args:
            thread_id: Thread identifier
            answer: User's answer
        
        Returns:
            Updated state
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        # Add the answer as a message
        state = {
            "messages": [Message(role=MessageRole.USER, content=answer)],
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def defer_question(self, thread_id: str) -> Any:
        """
        Defer the current question.
        
        Args:
            thread_id: Thread identifier
        
        Returns:
            Updated state
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        return await self.graph.ainvoke(
            {"messages": [Message(role=MessageRole.USER, content="/defer")]},
            config=config,
        )
    
    async def get_state(self, thread_id: str) -> Optional[InterrogationAgentState]:
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

def create_interrogation_agent(
    checkpoint_saver: Optional[CheckpointSaver] = None,
    redis_url: Optional[str] = None,
) -> InterrogationAgent:
    """
    Create an Interrogation Agent instance.
    
    Args:
        checkpoint_saver: Optional checkpoint saver
        redis_url: Redis URL for default checkpointing
    
    Returns:
        Configured InterrogationAgent instance
    """
    from ..checkpoint import get_checkpoint_saver
    
    if checkpoint_saver is None and redis_url:
        checkpoint_saver = get_checkpoint_saver(redis_url=redis_url)
    
    return InterrogationAgent(checkpoint_saver=checkpoint_saver)
