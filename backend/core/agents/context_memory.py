"""
Context Memory Agent for LangGraph.

This module implements the ContextMemoryAgent as a LangGraph StateGraph
that manages RAG-based context retrieval and decision embedding storage.
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from uuid import uuid4

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import CheckpointSaver
from langgraph.types import Command

from .types import (
    AgentType,
    Decision,
    DecisionCategory,
    ContextMemoryAgentState,
)
from .state import create_context_memory_state
from ..llm import get_embedding_client


# ==================== Node Names ====================

class ContextMemoryNode:
    """Node names for the Context Memory Agent."""
    START = "start"
    RETRIEVE_CONTEXT = "retrieve_context"
    STORE_DECISION = "store_decision"
    UPDATE_DEPENDENCIES = "update_dependencies"
    MANAGE_CONTEXT_WINDOW = "manage_context_window"
    SEARCH_DECISIONS = "search_decisions"
    END = "end"


# ==================== Context Memory Agent ====================

class ContextMemoryAgent:
    """
    Context Memory Agent for RAG-based context retrieval.
    
    This agent manages:
    1. Retrieving relevant context from vector store
    2. Storing decisions with embeddings
    3. Updating dependency graphs
    4. Managing context window limits
    5. Semantic search for decisions
    """
    
    def __init__(
        self,
        checkpoint_saver: Optional[CheckpointSaver] = None,
        vector_store: Optional[Any] = None,
        on_retrieve: Optional[Callable[[List[Dict]], None]] = None,
        on_store: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Context Memory Agent.
        
        Args:
            checkpoint_saver: Checkpoint saver for state persistence
            vector_store: Vector store for embeddings
            on_retrieve: Callback when context is retrieved
            on_store: Callback when decision is stored
        """
        self.checkpoint_saver = checkpoint_saver
        self.vector_store = vector_store
        self.on_retrieve = on_retrieve
        self.on_store = on_store
        self.embedding_client = get_embedding_client()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph for the Context Memory Agent."""
        builder = StateGraph(
            ContextMemoryAgentState,
            config_schema={
                "project_id": str,
                "thread_id": str,
            },
        )
        
        # Add nodes
        builder.add_node(ContextMemoryNode.START, self._start_node)
        builder.add_node(ContextMemoryNode.RETRIEVE_CONTEXT, self._retrieve_context_node)
        builder.add_node(ContextMemoryNode.STORE_DECISION, self._store_decision_node)
        builder.add_node(ContextMemoryNode.UPDATE_DEPENDENCIES, self._update_dependencies_node)
        builder.add_node(ContextMemoryNode.MANAGE_CONTEXT_WINDOW, self._manage_context_window_node)
        builder.add_node(ContextMemoryNode.SEARCH_DECISIONS, self._search_decisions_node)
        builder.add_node(ContextMemoryNode.END, self._end_node)
        
        # Set entry point
        builder.set_entry_point(ContextMemoryNode.START)
        
        # Add edges
        builder.add_edge(ContextMemoryNode.START, ContextMemoryNode.RETRIEVE_CONTEXT)
        builder.add_edge(ContextMemoryNode.RETRIEVE_CONTEXT, ContextMemoryNode.MANAGE_CONTEXT_WINDOW)
        builder.add_edge(ContextMemoryNode.MANAGE_CONTEXT_WINDOW, ContextMemoryNode.UPDATE_DEPENDENCIES)
        builder.add_edge(ContextMemoryNode.UPDATE_DEPENDENCIES, ContextMemoryNode.SEARCH_DECISIONS)
        
        # Conditional edges
        builder.add_conditional_edges(
            ContextMemoryNode.RETRIEVE_CONTEXT,
            self._should_store_decision,
            {
                "store": ContextMemoryNode.STORE_DECISION,
                "skip": ContextMemoryNode.MANAGE_CONTEXT_WINDOW,
            },
        )
        
        builder.add_conditional_edges(
            ContextMemoryNode.SEARCH_DECISIONS,
            self._search_complete_router,
            {
                "more": ContextMemoryNode.RETRIEVE_CONTEXT,
                "complete": ContextMemoryNode.END,
            },
        )
        
        # Compile with checkpoint saver
        if self.checkpoint_saver:
            builder.checkpointer = self.checkpoint_saver
        
        return builder.compile()
    
    async def _start_node(self, state: ContextMemoryAgentState) -> ContextMemoryAgentState:
        """Start the context memory process."""
        state["messages"] = state.get("messages", [])
        state["messages"].append({
            "role": "system",
            "content": "Starting context memory retrieval process.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return state
    
    async def _retrieve_context_node(
        self,
        state: ContextMemoryAgentState,
    ) -> ContextMemoryAgentState:
        """Retrieve relevant context from vector store."""
        query = state.get("query", state.get("search_query", ""))
        
        if not query:
            state["retrieved_documents"] = []
            state["similarity_scores"] = {}
            return state
        
        # Get embedding for query
        embedding = await self.embedding_client.aembed_query(query)
        state["embedding_used"] = "claude"  # or model used
        
        # Search vector store
        if self.vector_store:
            results = await self.vector_store.similarity_search_with_score(
                query=query,
                k=5,
                filter={"project_id": state["project_id"]},
            )
            
            retrieved = []
            scores = {}
            
            for doc, score in results:
                retrieved.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score,
                    "id": doc.metadata.get("decision_id", uuid4().hex),
                })
                scores[doc.metadata.get("decision_id", "")] = score
            
            state["retrieved_documents"] = retrieved
            state["similarity_scores"] = scores
            
            # Notify callback
            if self.on_retrieve:
                self.on_retrieve(retrieved)
        else:
            # Fallback to mock retrieval
            state["retrieved_documents"] = [{
                "content": f"Mock context for: {query}",
                "metadata": {"category": "general"},
                "score": 0.9,
                "id": uuid4().hex,
            }]
        
        return state
    
    async def _store_decision_node(
        self,
        state: ContextMemoryAgentState,
    ) -> ContextMemoryAgentState:
        """Store a decision with embedding."""
        decision = state.get("decision_to_store")
        
        if not decision:
            return state
        
        # Generate embedding for decision
        decision_text = f"{decision.get('question_text', '')} {decision.get('answer_text', '')}"
        embedding = await self.embedding_client.aembed_query(decision_text)
        
        # Store in vector store
        if self.vector_store:
            from langchain_core.documents import Document
            
            doc = Document(
                page_content=decision_text,
                metadata={
                    "decision_id": decision.get("decision_id", uuid4().hex),
                    "project_id": state["project_id"],
                    "category": decision.get("category", ""),
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
            
            await self.vector_store.add_documents([doc])
        
        state["stored_decision_id"] = decision.get("decision_id")
        
        # Notify callback
        if self.on_store:
            self.on_store(state["stored_decision_id"])
        
        return state
    
    async def _update_dependencies_node(
        self,
        state: ContextMemoryAgentState,
    ) -> ContextMemoryAgentState:
        """Update dependency graph for decisions."""
        retrieved = state.get("retrieved_documents", [])
        current_decision = state.get("decision_to_store")
        
        dependencies = []
        
        for doc in retrieved:
            doc_id = doc.get("id", "")
            doc_content = doc.get("content", "")
            
            # Check for dependency relationships
            if current_decision:
                if self._has_dependency(current_decision, doc_content):
                    dependencies.append({
                        "from": current_decision.get("decision_id"),
                        "to": doc_id,
                        "relationship": "related",
                        "strength": doc.get("score", 0.0),
                    })
        
        if "dependencies" not in state["context"]:
            state["context"]["dependencies"] = []
        
        state["context"]["dependencies"].extend(dependencies)
        
        return state
    
    async def _manage_context_window_node(
        self,
        state: ContextMemoryAgentState,
    ) -> ContextMemoryAgentState:
        """Manage context window limits."""
        retrieved = state.get("retrieved_documents", [])
        
        # Calculate tokens used
        total_tokens = sum(
            len(doc.get("content", "").split()) * 1.3  # Rough token estimate
            for doc in retrieved
        )
        
        state["tokens_used"] = int(total_tokens)
        
        # Context window limit (e.g., 8192 tokens)
        max_tokens = 7000  # Leave room for other content
        state["tokens_remaining"] = max(max_tokens - state["tokens_used"], 0)
        
        # Mark if context window is used
        state["context_window_used"] = state["tokens_used"] > max_tokens * 0.8
        
        # Prune if necessary
        if state["context_window_used"]:
            pruned = self._prune_context(retrieved, max_tokens * 0.7)
            state["retrieved_documents"] = pruned
            state["tokens_used"] = int(sum(
                len(doc.get("content", "").split()) * 1.3
                for doc in pruned
            ))
        
        return state
    
    async def _search_decisions_node(
        self,
        state: ContextMemoryAgentState,
    ) -> ContextMemoryAgentState:
        """Search for related decisions."""
        search_query = state.get("search_query", "")
        threshold = state.get("search_threshold", 0.7)
        
        if not search_query:
            state["search_results"] = []
            return state
        
        # Get embedding for search query
        embedding = await self.embedding_client.aembed_query(search_query)
        
        # Search vector store
        if self.vector_store:
            results = await self.vector_store.similarity_search_with_score(
                query=search_query,
                k=10,
                filter={"project_id": state["project_id"]},
            )
            
            filtered_results = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score,
                    "id": doc.metadata.get("decision_id", ""),
                }
                for doc, score in results
                if score >= threshold
            ]
            
            state["search_results"] = filtered_results
        else:
            state["search_results"] = [{
                "content": f"Mock search result for: {search_query}",
                "metadata": {"category": "mock"},
                "score": 0.85,
                "id": uuid4().hex,
            }]
        
        return state
    
    async def _end_node(self, state: ContextMemoryAgentState) -> ContextMemoryAgentState:
        """End the context memory process."""
        state["messages"] = state.get("messages", [])
        state["messages"].append({
            "role": "system",
            "content": f"Context retrieval complete. Retrieved {len(state.get('retrieved_documents', []))} documents.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return state
    
    # ==================== Routing Functions ====================
    
    def _should_store_decision(self, state: ContextMemoryAgentState) -> str:
        """Determine if we should store a decision."""
        decision = state.get("decision_to_store")
        
        if decision and decision.get("decision_id"):
            return "store"
        return "skip"
    
    def _search_complete_router(self, state: ContextMemoryAgentState) -> str:
        """Route after search completion."""
        search_results = state.get("search_results", [])
        
        # If we have results and haven't reached enough, continue
        if len(search_results) < 5 and state.get("should_continue", False):
            return "more"
        return "complete"
    
    # ==================== Helper Methods ====================
    
    def _has_dependency(
        self,
        decision: Dict[str, Any],
        other_content: str,
    ) -> bool:
        """Check if a dependency relationship exists."""
        # Simple keyword-based dependency detection
        # In production, use more sophisticated methods
        
        keywords = {
            "api": ["api", "endpoint", "interface"],
            "database": ["database", "schema", "model"],
            "authentication": ["auth", "login", "security"],
        }
        
        decision_text = f"{decision.get('question_text', '')} {decision.get('answer_text', '')}"
        
        for category, words in keywords.items():
            if any(word in decision_text.lower() for word in words):
                if any(word in other_content.lower() for word in words):
                    return True
        
        return False
    
    def _prune_context(
        self,
        documents: List[Dict[str, Any]],
        max_tokens: int,
    ) -> List[Dict[str, Any]]:
        """Prune documents to fit within token limit."""
        # Sort by score (keep highest scoring first)
        sorted_docs = sorted(documents, key=lambda x: x.get("score", 0), reverse=True)
        
        pruned = []
        current_tokens = 0
        
        for doc in sorted_docs:
            doc_tokens = len(doc.get("content", "").split()) * 1.3
            
            if current_tokens + doc_tokens <= max_tokens:
                pruned.append(doc)
                current_tokens += doc_tokens
        
        return pruned
    
    # ==================== Public Interface ====================
    
    async def retrieve(
        self,
        project_id: str,
        query: str,
        thread_id: Optional[str] = None,
    ) -> ContextMemoryAgentState:
        """
        Retrieve context for a query.
        
        Args:
            project_id: Project identifier
            query: Search query
            thread_id: Thread identifier
        
        Returns:
            State with retrieved context
        """
        state = create_context_memory_state(
            project_id=project_id,
            query=query,
            thread_id=thread_id,
        )
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def store(
        self,
        project_id: str,
        decision: Dict[str, Any],
        thread_id: Optional[str] = None,
    ) -> ContextMemoryAgentState:
        """
        Store a decision.
        
        Args:
            project_id: Project identifier
            decision: Decision to store
            thread_id: Thread identifier
        
        Returns:
            State after storing decision
        """
        state = create_context_memory_state(
            project_id=project_id,
            query=decision.get("question_text", ""),
            thread_id=thread_id,
        )
        
        state["decision_to_store"] = decision
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def search(
        self,
        project_id: str,
        query: str,
        threshold: float = 0.7,
        thread_id: Optional[str] = None,
    ) -> ContextMemoryAgentState:
        """
        Search for decisions.
        
        Args:
            project_id: Project identifier
            query: Search query
            threshold: Similarity threshold
            thread_id: Thread identifier
        
        Returns:
            State with search results
        """
        state = create_context_memory_state(
            project_id=project_id,
            query=query,
            thread_id=thread_id,
        )
        
        state["search_query"] = query
        state["search_threshold"] = threshold
        state["should_continue"] = True
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def get_state(self, thread_id: str) -> Optional[ContextMemoryAgentState]:
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

def create_context_memory_agent(
    checkpoint_saver: Optional[CheckpointSaver] = None,
    vector_store: Optional[Any] = None,
    redis_url: Optional[str] = None,
) -> ContextMemoryAgent:
    """
    Create a Context Memory Agent instance.
    
    Args:
        checkpoint_saver: Optional checkpoint saver
        vector_store: Vector store for embeddings
        redis_url: Redis URL for default checkpointing
    
    Returns:
        Configured ContextMemoryAgent instance
    """
    from ..checkpoint import get_checkpoint_saver
    
    if checkpoint_saver is None and redis_url:
        checkpoint_saver = get_checkpoint_saver(redis_url=redis_url)
    
    return ContextMemoryAgent(
        checkpoint_saver=checkpoint_saver,
        vector_store=vector_store,
    )
