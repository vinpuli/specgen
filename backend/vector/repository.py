"""
Vector Search Repository

Provides high-level operations for:
- Storing and retrieving decisions with embeddings
- Semantic search across decision content
- Similar decision discovery
- RAG (Retrieval-Augmented Generation) support
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from backend.vector.client import VectorDBClient, get_vector_client


class VectorSearchRepository:
    """
    Repository for vector-based decision search.

    Handles:
    - Creating embeddings for decisions
    - Storing decisions with their embeddings
    - Semantic similarity search
    - Context retrieval for RAG
    """

    # Collection names
    DECISIONS_COLLECTION = "decisions"
    ARTIFACTS_COLLECTION = "artifacts"
    CONVERSATIONS_COLLECTION = "conversations"

    def __init__(self, client: VectorDBClient = None):
        """
        Initialize repository.

        Args:
            client: Vector database client (auto-initialized if not provided)
        """
        self.client = client or get_vector_client()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the repository and create collections."""
        if self._initialized:
            return

        await self.client.connect()

        # Create collections if they don't exist
        for collection in [
            self.DECISIONS_COLLECTION,
            self.ARTIFACTS_COLLECTION,
            self.CONVERSATIONS_COLLECTION,
        ]:
            try:
                await self.client.create_collection(
                    name=collection,
                    dimension=self._get_embedding_dimension(),
                    metric="cosine",
                )
            except Exception:
                # Collection might already exist
                pass

        self._initialized = True

    def _get_embedding_dimension(self) -> int:
        """Get embedding dimension based on provider."""
        provider = os.getenv("VECTOR_DB_PROVIDER", "pinecone")

        # Different models have different dimensions
        if provider == "openai":
            return 1536  # text-embedding-3-small
        elif provider == "anthropic":
            return 1024  # Claude embeddings
        else:
            return 768  # sentence-transformers default

    async def index_decision(
        self,
        decision_id: UUID,
        question_text: str,
        answer_text: str,
        category: str,
        project_id: UUID,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Index a decision for semantic search.

        Args:
            decision_id: Decision UUID
            question_text: Original question
            answer_text: Decision answer
            category: Decision category
            project_id: Project UUID
            metadata: Additional metadata
        """
        if not self._initialized:
            await self.initialize()

        # Combine question and answer for embedding
        text = f"Question: {question_text}\n\nAnswer: {answer_text}"

        # Create embedding (in production, use actual embedding model)
        embedding = await self._generate_embedding(text)

        await self.client.upsert(
            collection_name=self.DECISIONS_COLLECTION,
            vectors=[
                (
                    str(decision_id),
                    embedding,
                    {
                        "question": question_text,
                        "answer": answer_text,
                        "category": category,
                        "project_id": str(project_id),
                        "text": text,
                        "indexed_at": datetime.utcnow().isoformat(),
                        **(metadata or {}),
                    },
                )
            ],
        )

    async def search_decisions(
        self,
        query: str,
        project_id: UUID = None,
        limit: int = 10,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search decisions by semantic similarity.

        Args:
            query: Search query
            project_id: Optional project filter
            limit: Maximum results
            filters: Additional filters

        Returns:
            List of similar decisions with scores
        """
        if not self._initialized:
            await self.initialize()

        # Generate query embedding
        embedding = await self._generate_embedding(query)

        # Build filters
        search_filters = filters or {}
        if project_id:
            search_filters["project_id"] = str(project_id)

        results = await self.client.search(
            collection_name=self.DECISIONS_COLLECTION,
            query_vector=embedding,
            limit=limit,
            filters=search_filters if search_filters else None,
        )

        return results

    async def find_similar_decisions(
        self,
        decision_id: UUID,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find decisions similar to a given decision.

        Args:
            decision_id: Source decision ID
            limit: Maximum results

        Returns:
            List of similar decisions
        """
        if not self._initialized:
            await self.initialize()

        # Get the source decision's embedding
        source = await self.client.get_collection_info(self.DECISIONS_COLLECTION)
        # In production, store embeddings in a separate index

        # For now, search by the decision's text content
        # This is a simplified implementation
        return []

    async def delete_decision(self, decision_id: UUID) -> None:
        """Delete a decision from the index."""
        if not self._initialized:
            await self.initialize()

        await self.client.delete(
            collection_name=self.DECISIONS_COLLECTION,
            ids=[str(decision_id)],
        )

    async def get_context_for_rag(
        self,
        query: str,
        project_id: UUID,
        max_tokens: int = 4000,
    ) -> str:
        """
        Get context for RAG (Retrieval-Augmented Generation).

        Args:
            query: User query
            project_id: Project context
            max_tokens: Maximum context tokens

        Returns:
            Formatted context string
        """
        # Search for relevant decisions
        results = await self.search_decisions(
            query=query,
            project_id=project_id,
            limit=10,
        )

        # Format context from results
        context_parts = []
        for result in results:
            metadata = result.get("metadata", {})
            context_parts.append(
                f"Decision (score: {result['score']:.2f}):\n"
                f"Question: {metadata.get('question', '')}\n"
                f"Answer: {metadata.get('answer', '')}\n"
            )

        return "\n\n".join(context_parts)

    async def index_artifact(
        self,
        artifact_id: UUID,
        title: str,
        content: str,
        artifact_type: str,
        project_id: UUID,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Index an artifact for semantic search.

        Args:
            artifact_id: Artifact UUID
            title: Artifact title
            content: Artifact content
            artifact_type: Type of artifact
            project_id: Project UUID
            metadata: Additional metadata
        """
        if not self._initialized:
            await self.initialize()

        embedding = await self._generate_embedding(f"{title}\n\n{content}")

        await self.client.upsert(
            collection_name=self.ARTIFACTS_COLLECTION,
            vectors=[
                (
                    str(artifact_id),
                    embedding,
                    {
                        "title": title,
                        "content": content,
                        "type": artifact_type,
                        "project_id": str(project_id),
                        "indexed_at": datetime.utcnow().isoformat(),
                        **(metadata or {}),
                    },
                )
            ],
        )

    async def search_artifacts(
        self,
        query: str,
        project_id: UUID = None,
        artifact_type: str = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search artifacts by semantic similarity.

        Args:
            query: Search query
            project_id: Optional project filter
            artifact_type: Optional artifact type filter
            limit: Maximum results

        Returns:
            List of similar artifacts
        """
        if not self._initialized:
            await self.initialize()

        embedding = await self._generate_embedding(query)

        filters = {}
        if project_id:
            filters["project_id"] = str(project_id)
        if artifact_type:
            filters["type"] = artifact_type

        return await self.client.search(
            collection_name=self.ARTIFACTS_COLLECTION,
            query_vector=embedding,
            limit=limit,
            filters=filters if filters else None,
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        In production, this would call an embedding API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # In production, use actual embedding model
        # Example with OpenAI:
        # from openai import OpenAI
        # client = OpenAI()
        # response = client.embeddings.create(input=text, model="text-embedding-3-small")
        # return response.data[0].embedding

        # For now, return a placeholder
        import hashlib
        import numpy as np

        # Create deterministic placeholder embedding based on text hash
        hash_value = hashlib.sha256(text.encode()).hexdigest()
        hash_int = int(hash_value[:16], 16)

        # Generate pseudo-random embedding
        np.random.seed(hash_int)
        dimension = self._get_embedding_dimension()
        embedding = np.random.randn(dimension).tolist()

        # Normalize
        norm = sum(x**2 for x in embedding) ** 0.5
        embedding = [x / norm for x in embedding]

        return embedding

    async def health_check(self) -> Dict[str, Any]:
        """Check repository health."""
        try:
            await self.client.get_collection_info(self.DECISIONS_COLLECTION)
            return {"status": "healthy", "provider": type(self.client).__name__}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def close(self) -> None:
        """Close the repository."""
        await self.client.disconnect()
        self._initialized = False


# Repository instance
_vector_repo: Optional[VectorSearchRepository] = None


def get_vector_repo() -> VectorSearchRepository:
    """Get vector search repository instance."""
    global _vector_repo

    if _vector_repo is None:
        _vector_repo = VectorSearchRepository()

    return _vector_repo
