"""
Vector Store ToolNode for LangGraph agents.

Provides LangChain tools for vector store operations including:
- Semantic search for decisions and artifacts
- Indexing decisions and artifacts
- Finding similar decisions
- RAG context retrieval
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from uuid import UUID, uuid4

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from backend.vector.repository import VectorSearchRepository, get_vector_repo


class SearchDecisionsInput(BaseModel):
    """Input schema for SearchDecisionsTool."""

    query: str = Field(..., description="Search query for semantic similarity search")
    project_id: Optional[str] = Field(
        None, description="Optional project UUID filter"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results to return")


class SearchDecisionsTool(BaseTool):
    """Tool for searching decisions by semantic similarity."""

    name: str = "search_decisions"
    description: str = """
    Search for decisions in the vector store using semantic similarity.
    Useful for finding related or similar decisions based on content meaning.
    Returns decisions with their similarity scores.
    """
    args_schema: Type[BaseModel] = SearchDecisionsInput

    def __init__(self, repo: VectorSearchRepository = None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    async def _arun(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Execute semantic search for decisions."""
        try:
            project_uuid = UUID(project_id) if project_id else None
            results = await self.repo.search_decisions(
                query=query,
                project_id=project_uuid,
                limit=limit,
            )
            return results
        except Exception as e:
            return [{"error": str(e)}]

    def _run(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper for search decisions."""
        import asyncio

        return asyncio.run(self._arun(query, project_id, limit))


class IndexDecisionInput(BaseModel):
    """Input schema for IndexDecisionTool."""

    decision_id: str = Field(..., description="Decision UUID to index")
    question_text: str = Field(..., description="Original question text")
    answer_text: str = Field(..., description="Decision answer text")
    category: str = Field(..., description="Decision category")
    project_id: str = Field(..., description="Project UUID")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class IndexDecisionTool(BaseTool):
    """Tool for indexing decisions in the vector store."""

    name: str = "index_decision"
    description: str = """
    Index a decision in the vector store for semantic search.
    The decision will be embedded and stored for future similarity searches.
    Call this after creating or updating a decision.
    """
    args_schema: Type[BaseModel] = IndexDecisionInput

    def __init__(self, repo: VectorSearchRepository = None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    async def _arun(
        self,
        decision_id: str,
        question_text: str,
        answer_text: str,
        category: str,
        project_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute decision indexing."""
        try:
            await self.repo.index_decision(
                decision_id=UUID(decision_id),
                question_text=question_text,
                answer_text=answer_text,
                category=category,
                project_id=UUID(project_id),
                metadata=metadata,
            )
            return {
                "status": "success",
                "decision_id": decision_id,
                "indexed_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run(
        self,
        decision_id: str,
        question_text: str,
        answer_text: str,
        category: str,
        project_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for index decision."""
        import asyncio

        return asyncio.run(
            self._arun(
                decision_id, question_text, answer_text, category, project_id, metadata
            )
        )


class SearchArtifactsInput(BaseModel):
    """Input schema for SearchArtifactsTool."""

    query: str = Field(..., description="Search query for semantic similarity")
    project_id: Optional[str] = Field(
        None, description="Optional project UUID filter"
    )
    artifact_type: Optional[str] = Field(
        None, description="Optional artifact type filter (prd, api_contract, etc.)"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")


class SearchArtifactsTool(BaseTool):
    """Tool for searching artifacts by semantic similarity."""

    name: str = "search_artifacts"
    description: str = """
    Search for artifacts in the vector store using semantic similarity.
    Useful for finding related artifacts like PRDs, API contracts, or specs.
    Returns artifacts with their similarity scores.
    """
    args_schema: Type[BaseModel] = SearchArtifactsInput

    def __init__(self, repo: VectorSearchRepository = None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    async def _arun(
        self,
        query: str,
        project_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Execute semantic search for artifacts."""
        try:
            project_uuid = UUID(project_id) if project_id else None
            results = await self.repo.search_artifacts(
                query=query,
                project_id=project_uuid,
                artifact_type=artifact_type,
                limit=limit,
            )
            return results
        except Exception as e:
            return [{"error": str(e)}]

    def _run(
        self,
        query: str,
        project_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper for search artifacts."""
        import asyncio

        return asyncio.run(self._arun(query, project_id, artifact_type, limit))


class IndexArtifactInput(BaseModel):
    """Input schema for IndexArtifactTool."""

    artifact_id: str = Field(..., description="Artifact UUID to index")
    title: str = Field(..., description="Artifact title")
    content: str = Field(..., description="Artifact content")
    artifact_type: str = Field(..., description="Type of artifact (prd, api_contract, etc.)")
    project_id: str = Field(..., description="Project UUID")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class IndexArtifactTool(BaseTool):
    """Tool for indexing artifacts in the vector store."""

    name: str = "index_artifact"
    description: str = """
    Index an artifact in the vector store for semantic search.
    Call this after generating or updating an artifact.
    """
    args_schema: Type[BaseModel] = IndexArtifactInput

    def __init__(self, repo: VectorSearchRepository = None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    async def _arun(
        self,
        artifact_id: str,
        title: str,
        content: str,
        artifact_type: str,
        project_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute artifact indexing."""
        try:
            await self.repo.index_artifact(
                artifact_id=UUID(artifact_id),
                title=title,
                content=content,
                artifact_type=artifact_type,
                project_id=UUID(project_id),
                metadata=metadata,
            )
            return {
                "status": "success",
                "artifact_id": artifact_id,
                "indexed_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run(
        self,
        artifact_id: str,
        title: str,
        content: str,
        artifact_type: str,
        project_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for index artifact."""
        import asyncio

        return asyncio.run(
            self._arun(artifact_id, title, content, artifact_type, project_id, metadata)
        )


class GetRAGContextInput(BaseModel):
    """Input schema for GetRAGContextTool."""

    query: str = Field(..., description="User query for context retrieval")
    project_id: str = Field(..., description="Project UUID for context")
    max_tokens: int = Field(
        default=4000, ge=1000, le=16000, description="Maximum context tokens"
    )


class GetRAGContextTool(BaseTool):
    """Tool for retrieving RAG context from the vector store."""

    name: str = "get_rag_context"
    description: str = """
    Get context for Retrieval-Augmented Generation (RAG).
    Searches for relevant decisions and formats them as context.
    Useful for providing LLM with relevant decision history.
    """
    args_schema: Type[BaseModel] = GetRAGContextInput

    def __init__(self, repo: VectorSearchRepository = None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    async def _arun(
        self, query: str, project_id: str, max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """Execute RAG context retrieval."""
        try:
            context = await self.repo.get_context_for_rag(
                query=query,
                project_id=UUID(project_id),
                max_tokens=max_tokens,
            )
            return {
                "status": "success",
                "context": context,
                "query": query,
                "project_id": project_id,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run(
        self, query: str, project_id: str, max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """Synchronous wrapper for get rag context."""
        import asyncio

        return asyncio.run(self._arun(query, project_id, max_tokens))


class FindSimilarDecisionsInput(BaseModel):
    """Input schema for FindSimilarDecisionsTool."""

    decision_id: str = Field(..., description="Source decision UUID")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum results")


class FindSimilarDecisionsTool(BaseTool):
    """Tool for finding similar decisions."""

    name: str = "find_similar_decisions"
    description: str = """
    Find decisions that are similar to a given decision.
    Useful for discovering related decisions or finding patterns.
    """
    args_schema: Type[BaseModel] = FindSimilarDecisionsInput

    def __init__(self, repo: VectorSearchRepository = None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    async def _arun(self, decision_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Execute similar decisions search."""
        try:
            results = await self.repo.find_similar_decisions(
                decision_id=UUID(decision_id),
                limit=limit,
            )
            return results
        except Exception as e:
            return [{"error": str(e)}]

    def _run(self, decision_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Synchronous wrapper for find similar decisions."""
        import asyncio

        return asyncio.run(self._arun(decision_id, limit))


class DeleteFromIndexInput(BaseModel):
    """Input schema for DeleteFromIndexTool."""

    decision_id: Optional[str] = Field(
        None, description="Decision UUID to delete"
    )
    artifact_id: Optional[str] = Field(
        None, description="Artifact UUID to delete"
    )


class DeleteFromIndexTool(BaseTool):
    """Tool for deleting items from the vector index."""

    name: str = "delete_from_index"
    description: str = """
    Delete a decision or artifact from the vector store index.
    Use when a decision or artifact is deleted.
    """
    args_schema: Type[BaseModel] = DeleteFromIndexInput

    def __init__(self, repo: VectorSearchRepository = None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    async def _arun(
        self,
        decision_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute deletion from index."""
        try:
            if decision_id:
                await self.repo.delete_decision(decision_id=UUID(decision_id))
                return {"status": "success", "decision_id": decision_id}
            elif artifact_id:
                # Artifact deletion would need a similar method
                return {
                    "status": "error",
                    "error": "Artifact deletion not yet implemented",
                }
            else:
                return {"status": "error", "error": "No ID provided"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run(
        self,
        decision_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for delete from index."""
        import asyncio

        return asyncio.run(self._arun(decision_id, artifact_id))


class VectorStoreToolNode:
    """
    Factory for creating vector store tool nodes for LangGraph agents.

    Provides easy access to all vector store tools as a unified interface.
    """

    def __init__(self, repo: VectorSearchRepository = None):
        """
        Initialize the tool node factory.

        Args:
            repo: Optional vector repository instance
        """
        self._repo = repo
        self._tools: List[BaseTool] = []

    @property
    def repo(self) -> VectorSearchRepository:
        """Get the vector repository instance."""
        if self._repo is None:
            self._repo = get_vector_repo()
        return self._repo

    def get_all_tools(self) -> List[BaseTool]:
        """Get all vector store tools."""
        if not self._tools:
            self._tools = [
                SearchDecisionsTool(repo=self.repo),
                IndexDecisionTool(repo=self.repo),
                SearchArtifactsTool(repo=self.repo),
                IndexArtifactTool(repo=self.repo),
                GetRAGContextTool(repo=self.repo),
                FindSimilarDecisionsTool(repo=self.repo),
                DeleteFromIndexTool(repo=self.repo),
            ]
        return self._tools

    def get_tool(self, name: str) -> BaseTool:
        """
        Get a specific tool by name.

        Args:
            name: Tool name

        Returns:
            BaseTool instance
        """
        tools = {tool.name: tool for tool in self.get_all_tools()}
        if name not in tools:
            raise ValueError(f"Unknown tool: {name}")
        return tools[name]

    async def initialize(self) -> None:
        """Initialize the vector repository."""
        await self.repo.initialize()


# Convenience functions for creating tools
def create_vector_tools() -> List[BaseTool]:
    """Create all vector store tools."""
    node = VectorStoreToolNode()
    return node.get_all_tools()


def get_search_decisions_tool() -> SearchDecisionsTool:
    """Get the search decisions tool."""
    return SearchDecisionsTool()


def get_index_decision_tool() -> IndexDecisionTool:
    """Get the index decision tool."""
    return IndexDecisionTool()


def get_search_artifacts_tool() -> SearchArtifactsTool:
    """Get the search artifacts tool."""
    return SearchArtifactsTool()


def get_index_artifact_tool() -> IndexArtifactTool:
    """Get the index artifact tool."""
    return IndexArtifactTool()


def get_rag_context_tool() -> GetRAGContextTool:
    """Get the RAG context tool."""
    return GetRAGContextTool()


def get_find_similar_decisions_tool() -> FindSimilarDecisionsTool:
    """Get the find similar decisions tool."""
    return FindSimilarDecisionsTool()


def get_delete_from_index_tool() -> DeleteFromIndexTool:
    """Get the delete from index tool."""
    return DeleteFromIndexTool()
