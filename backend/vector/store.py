"""
Vector Store integration for Pinecone and Weaviate.

This module provides vector store configurations and utilities
for semantic search and embedding storage.
"""

import os
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from uuid import uuid4
from enum import Enum

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings

# Pinecone imports
try:
    from pinecone import Pinecone, ServerlessSpec
    from pinecone.core.grpc import GRPCIndex
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

# Weaviate imports
try:
    import weaviate
    from weaviate import WeaviateClient
    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False

from ..core.llm import get_embedding_client


# ==================== Provider Types ====================

class VectorStoreProvider(str, Enum):
    """Supported vector store providers."""
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    MOCK = "mock"


# ==================== Configuration ====================

@dataclass
class VectorStoreConfig:
    """Configuration for vector store."""
    provider: VectorStoreProvider
    api_key: Optional[str] = None
    environment: Optional[str] = None
    index_name: str = "specgen"
    dimension: int = 1536
    metric: str = "cosine"
    host: Optional[str] = None
    port: Optional[int] = None
    
    # Metadata
    namespace: Optional[str] = None
    batch_size: int = 100
    recreate_index: bool = False


# ==================== Base Vector Store ====================

class SpecGenVectorStore:
    """
    Unified vector store interface for the specgen application.
    
    Provides a consistent API for Pinecone and Weaviate.
    """
    
    def __init__(self, config: VectorStoreConfig):
        """
        Initialize the vector store.
        
        Args:
            config: Vector store configuration
        """
        self.config = config
        self.provider = config.provider
        self._client: Any = None
        self._index: Any = None
        self._embedding_client = get_embedding_client()
    
    async def initialize(self) -> bool:
        """
        Initialize the vector store connection.
        
        Returns:
            True if successful
        """
        raise NotImplementedError
    
    async def create_index(self) -> bool:
        """
        Create the index if it doesn't exist.
        
        Returns:
            True if created or already exists
        """
        raise NotImplementedError
    
    async def delete_index(self) -> bool:
        """
        Delete the index.
        
        Returns:
            True if deleted
        """
        raise NotImplementedError
    
    async def add_documents(
        self,
        documents: List[Document],
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: Documents to add
            namespace: Optional namespace
        
        Returns:
            List of document IDs
        """
        raise NotImplementedError
    
    async def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[str]:
        """
        Add texts to the vector store.
        
        Args:
            texts: Texts to add
            metadatas: Optional metadata for each text
            namespace: Optional namespace
        
        Returns:
            List of document IDs
        """
        documents = [
            Document(page_content=text, metadata=meta or {})
            for text, meta in zip(texts, metadatas or [{}] * len(texts))
        ]
        return await self.add_documents(documents, namespace)
    
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[Document]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            k: Number of results
            filter: Optional metadata filter
            namespace: Optional namespace
        
        Returns:
            List of similar documents
        """
        raise NotImplementedError
    
    async def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[tuple[Document, float]]:
        """
        Search for similar documents with scores.
        
        Args:
            query: Search query
            k: Number of results
            filter: Optional metadata filter
            namespace: Optional namespace
        
        Returns:
            List of (document, score) tuples
        """
        raise NotImplementedError
    
    async def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Document]:
        """
        Search with Maximal Marginal Relevance for diversity.
        
        Args:
            query: Search query
            k: Number of results
            fetch_k: Number of candidates
            lambda_mult: Diversity factor (0 = max diversity, 1 = max relevance)
            filter: Optional metadata filter
        
        Returns:
            List of diverse documents
        """
        raise NotImplementedError
    
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Delete documents by ID or filter.
        
        Args:
            ids: Document IDs to delete
            filter: Metadata filter
            namespace: Namespace
        
        Returns:
            True if deleted
        """
        raise NotImplementedError
    
    async def update_document(
        self,
        id: str,
        document: Document,
        **kwargs,
    ) -> bool:
        """
        Update a document.
        
        Args:
            id: Document ID
            document: New document content
        
        Returns:
            True if updated
        """
        await self.delete(ids=[id])
        await self.add_documents([document])
        return True
    
    async def get_document(
        self,
        id: str,
        **kwargs,
    ) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            id: Document ID
        
        Returns:
            Document if found
        """
        raise NotImplementedError
    
    async def list_namespaces(self) -> List[str]:
        """
        List all namespaces.
        
        Returns:
            List of namespace names
        """
        raise NotImplementedError
    
    async def close(self):
        """Close the vector store connection."""
        pass


# ==================== Pinecone Implementation ====================

class PineconeVectorStore(SpecGenVectorStore):
    """Pinecone vector store implementation."""
    
    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self._index: Optional[GRPCIndex] = None
    
    async def initialize(self) -> bool:
        """Initialize Pinecone connection."""
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone SDK not installed. Run: pip install pinecone")
        
        api_key = self.config.api_key or os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not set")
        
        pc = Pinecone(api_key=api_key)
        
        # Check if index exists
        if self.config.index_name in [idx.name for idx in pc.list_indexes()]:
            self._index = pc.Index(self.config.index_name)
        else:
            raise ValueError(f"Index {self.config.index_name} not found")
        
        return True
    
    async def create_index(self) -> bool:
        """Create Pinecone index."""
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone SDK not installed")
        
        api_key = self.config.api_key or os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not set")
        
        pc = Pinecone(api_key=api_key)
        
        # Check if exists
        existing = [idx.name for idx in pc.list_indexes()]
        
        if self.config.index_name in existing:
            return True
        
        # Create index
        pc.create_index(
            name=self.config.index_name,
            dimension=self.config.dimension,
            metric=self.config.metric,
            spec=ServerlessSpec(
                cloud="aws",
                region=self.config.environment or "us-west-2",
            ),
        )
        
        self._index = pc.Index(self.config.index_name)
        return True
    
    async def delete_index(self) -> bool:
        """Delete Pinecone index."""
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone SDK not installed")
        
        if self._index:
            self._index.delete(delete_all=True)
        
        api_key = self.config.api_key or os.getenv("PINECONE_API_KEY")
        if api_key:
            pc = Pinecone(api_key=api_key)
            try:
                pc.delete_index(self.config.index_name)
            except Exception:
                pass
        
        return True
    
    async def add_documents(
        self,
        documents: List[Document],
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[str]:
        """Add documents to Pinecone."""
        if not self._index:
            await self.initialize()
        
        texts = [doc.page_content for doc in documents]
        embeddings = await self._embedding_client.aembed_documents(texts)
        
        ids = [str(uuid4()) for _ in documents]
        
        # Prepare vectors
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            vectors.append({
                "id": ids[i],
                "values": embedding,
                "metadata": {
                    **doc.metadata,
                    "text": doc.page_content[:1000],  # Pinecone limit
                    "created_at": datetime.utcnow().isoformat(),
                },
            })
        
        # Upsert in batches
        batch_size = self.config.batch_size
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self._index.upsert(vectors=batch, namespace=namespace)
        
        return ids
    
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[Document]:
        """Search Pinecone."""
        results = await self.similarity_search_with_score(
            query=query, k=k, filter=filter, namespace=namespace
        )
        return [doc for doc, _ in results]
    
    async def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[tuple[Document, float]]:
        """Search Pinecone with scores."""
        if not self._index:
            await self.initialize()
        
        embedding = await self._embedding_client.aembed_query(query)
        
        query_params = {
            "vector": embedding,
            "top_k": k,
            "include_metadata": True,
            "include_values": False,
        }
        
        if namespace:
            query_params["namespace"] = namespace
        
        if filter:
            query_params["filter"] = filter
        
        response = self._index.query(**query_params)
        
        results = []
        for match in response.matches:
            metadata = dict(match.metadata) if match.metadata else {}
            text = metadata.pop("text", "")
            
            doc = Document(
                page_content=text,
                metadata=metadata,
            )
            results.append((doc, match.score))
        
        return results
    
    async def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Document]:
        """MMR search in Pinecone."""
        if not self._index:
            await self.initialize()
        
        embedding = await self._embedding_client.aembed_query(query)
        
        # Fetch candidates
        candidates = await self.similarity_search_with_score(
            query=query, k=fetch_k, filter=filter
        )
        
        # Simple MMR implementation
        selected = []
        selected_ids = set()
        
        for _ in range(k):
            best_score = -1
            best_doc = None
            best_idx = -1
            
            for idx, (doc, score) in enumerate(candidates):
                if doc.metadata.get("id") in selected_ids:
                    continue
                
                # Calculate MMR score
                if selected:
                    # Max similarity to selected
                    max_sim = max(
                        self._cosine_similarity(
                            doc.page_content, s[0].page_content
                        ) for s in selected
                    )
                    mmr_score = lambda_mult * score - (1 - lambda_mult) * max_sim
                else:
                    mmr_score = score
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_doc = doc
                    best_idx = idx
            
            if best_doc:
                selected.append((best_doc, best_score))
                selected_ids.add(best_doc.metadata.get("id", str(best_idx)))
        
        return [doc for doc, _ in selected]
    
    def _cosine_similarity(self, text1: str, text2: str) -> float:
        """Simple cosine similarity (placeholder)."""
        # In production, use actual embeddings
        return 0.5
    
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """Delete from Pinecone."""
        if not self._index:
            return False
        
        if ids:
            self._index.delete(ids=ids, namespace=namespace)
        elif filter:
            self._index.delete(filter=filter, namespace=namespace)
        
        return True
    
    async def get_document(
        self,
        id: str,
        **kwargs,
    ) -> Optional[Document]:
        """Get document by ID."""
        if not self._index:
            await self.initialize()
        
        response = self._index.fetch(ids=[id])
        
        if id in response.vectors:
            vec = response.vectors[id]
            return Document(
                page_content=vec.metadata.get("text", ""),
                metadata=vec.metadata,
            )
        
        return None


# ==================== Weaviate Implementation ====================

class WeaviateVectorStore(SpecGenVectorStore):
    """Weaviate vector store implementation."""
    
    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self._client: Optional[WeaviateClient] = None
    
    async def initialize(self) -> bool:
        """Initialize Weaviate connection."""
        if not WEAVIATE_AVAILABLE:
            raise ImportError("Weaviate client not installed. Run: pip install weaviate-client")
        
        url = self.config.host or os.getenv("WEAVIATE_URL", "http://localhost:8080")
        api_key = self.config.api_key or os.getenv("WEAVIATE_API_KEY")
        
        auth_config = None
        if api_key:
            from weaviate.auth import AuthApiKey
            auth_config = AuthApiKey(api_key=api_key)
        
        self._client = weaviate.Client(
            url=url,
            auth_client_secret=auth_config,
        )
        
        return self._client.is_ready()
    
    async def create_index(self) -> bool:
        """Create Weaviate class."""
        if not self._client:
            await self.initialize()
        
        class_name = self.config.index_name.title().replace("_", "")
        
        if self._client.schema.exists(class_name):
            return True
        
        class_obj = {
            "class": class_name,
            "description": f"SpecGen {self.config.index_name} store",
            "vectorizer": "none",  # Use our embeddings
            "moduleConfig": {
                "text2vec-transformers": {
                    "vectorizeClassName": False,
                }
            },
            "properties": [
                {"name": "text", "dataType": ["text"]},
                {"name": "project_id", "dataType": ["text"]},
                {"name": "decision_id", "dataType": ["text"]},
                {"name": "category", "dataType": ["text"]},
                {"name": "created_at", "dataType": ["date"]},
            ],
        }
        
        self._client.schema.create_class(class_obj)
        return True
    
    async def delete_index(self) -> bool:
        """Delete Weaviate class."""
        if self._client:
            class_name = self.config.index_name.title().replace("_", "")
            try:
                self._client.schema.delete_class(class_name)
            except Exception:
                pass
        return True
    
    async def add_documents(
        self,
        documents: List[Document],
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[str]:
        """Add documents to Weaviate."""
        if not self._client:
            await self.initialize()
        
        class_name = self.config.index_name.title().replace("_", "")
        
        texts = [doc.page_content for doc in documents]
        embeddings = await self._embedding_client.aembed_documents(texts)
        
        ids = [str(uuid4()) for _ in documents]
        
        # Prepare data objects
        data_objects = []
        for i, doc in enumerate(documents):
            data_objects.append({
                "text": doc.page_content,
                "project_id": doc.metadata.get("project_id", ""),
                "decision_id": doc.metadata.get("decision_id", ""),
                "category": doc.metadata.get("category", ""),
                "created_at": datetime.utcnow().isoformat(),
            })
        
        # Add with vectors
        self._client.data_object.create(
            class_name=class_name,
            data_object=data_objects[0],
            vector=embeddings[0] if len(embeddings) == 1 else None,
        )
        
        # Batch add
        if len(documents) > 1:
            with self._client.batch as batch:
                for i, doc in enumerate(documents[1:], 1):
                    batch.add_data_object(
                        data_object=data_objects[i],
                        class_name=class_name,
                        vector=embeddings[i] if i < len(embeddings) else None,
                    )
        
        return ids
    
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[Document]:
        """Search Weaviate."""
        results = await self.similarity_search_with_score(
            query=query, k=k, filter=filter, namespace=namespace
        )
        return [doc for doc, _ in results]
    
    async def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[tuple[Document, float]]:
        """Search Weaviate with scores."""
        if not self._client:
            await self.initialize()
        
        class_name = self.config.index_name.title().replace("_", "")
        
        embedding = await self._embedding_client.aembed_query(query)
        
        # Build where filter
        where_filter = None
        if filter:
            where_filter = {
                "operator": "And",
                "operands": [
                    {"path": [key], "operator": "Eq", "valueString": value}
                    for key, value in filter.items()
                ]
            }
        
        # Search
        response = (
            self._client.query.get(class_name, ["text", "project_id", "decision_id", "category"])
            .with_near_vector({"vector": embedding})
            .with_limit(k)
            .with_where(where_filter)
            .with_additional(["certainty"])  # Score
            .do()
        )
        
        results = []
        for obj in response.get("data", {}).get("Get", {}).get(class_name, []):
            doc = Document(
                page_content=obj.get("text", ""),
                metadata={
                    "project_id": obj.get("project_id"),
                    "decision_id": obj.get("decision_id"),
                    "category": obj.get("category"),
                },
            )
            score = obj.get("_additional", {}).get("certainty", 0.0)
            results.append((doc, score))
        
        return results
    
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """Delete from Weaviate."""
        if not self._client:
            return False
        
        class_name = self.config.index_name.title().replace("_", "")
        
        if ids:
            for id in ids:
                try:
                    self._client.data_object.delete(id, class_name)
                except Exception:
                    pass
        elif filter:
            where = {
                "operator": "And",
                "operands": [
                    {"path": [key], "operator": "Eq", "valueString": value}
                    for key, value in filter.items()
                ]
            }
            response = (
                self._client.query.get(class_name, ["_id"])
                .with_where(where)
                .with_additional(["id"])
                .do()
            )
            for obj in response.get("data", {}).get("Get", {}).get(class_name, []):
                try:
                    self._client.data_object.delete(obj["_id"], class_name)
                except Exception:
                    pass
        
        return True
    
    async def get_document(
        self,
        id: str,
        **kwargs,
    ) -> Optional[Document]:
        """Get document by ID."""
        if not self._client:
            await self.initialize()
        
        class_name = self.config.index_name.title().replace("_", "")
        
        try:
            obj = self._client.data_object.get_by_id(id, class_name=class_name)
            if obj:
                return Document(
                    page_content=obj.get("text", ""),
                    metadata=obj.get("metadata", {}),
                )
        except Exception:
            pass
        
        return None


# ==================== Mock Vector Store ====================

class MockVectorStore(SpecGenVectorStore):
    """Mock vector store for testing."""
    
    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self._documents: List[Document] = []
    
    async def initialize(self) -> bool:
        return True
    
    async def create_index(self) -> bool:
        return True
    
    async def delete_index(self) -> bool:
        self._documents = []
        return True
    
    async def add_documents(
        self,
        documents: List[Document],
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[str]:
        ids = [str(uuid4()) for _ in documents]
        for i, doc in enumerate(documents):
            doc.metadata["id"] = ids[i]
        self._documents.extend(documents)
        return ids
    
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[Document]:
        results = await self.similarity_search_with_score(
            query=query, k=k, filter=filter, namespace=namespace
        )
        return [doc for doc, _ in results]
    
    async def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> List[tuple[Document, float]]:
        # Simple keyword matching for mock
        query_words = set(query.lower().split())
        
        scored = []
        for doc in self._documents:
            doc_words = set(doc.page_content.lower().split())
            overlap = len(query_words & doc_words)
            score = overlap / max(len(query_words), 1)
            scored.append((doc, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
    
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> bool:
        if ids:
            self._documents = [
                d for d in self._documents
                if d.metadata.get("id") not in ids
            ]
        return True


# ==================== Factory Functions ====================

def create_vector_store(
    provider: Optional[str] = None,
    config: Optional[VectorStoreConfig] = None,
) -> SpecGenVectorStore:
    """
    Create a vector store instance.
    
    Args:
        provider: Provider name (pinecone, weaviate, mock)
        config: Optional configuration
    
    Returns:
        Vector store instance
    """
    if config is None:
        provider = provider or os.getenv("VECTOR_DB_PROVIDER", "mock")
        
        if provider == "pinecone":
            config = VectorStoreConfig(
                provider=VectorStoreProvider.PINECONE,
                api_key=os.getenv("PINECONE_API_KEY"),
                environment=os.getenv("PINECONE_ENVIRONMENT"),
                index_name=os.getenv("PINECONE_INDEX_NAME", "specgen"),
                dimension=1536,
            )
        elif provider == "weaviate":
            config = VectorStoreConfig(
                provider=VectorStoreProvider.WEAVIATE,
                host=os.getenv("WEAVIATE_URL"),
                api_key=os.getenv("WEAVIATE_API_KEY"),
                index_name=os.getenv("WEAVIATE_INDEX_NAME", "specgen"),
                dimension=1536,
            )
        else:
            config = VectorStoreConfig(provider=VectorStoreProvider.MOCK)
    
    if config.provider == VectorStoreProvider.PINECONE:
        return PineconeVectorStore(config)
    elif config.provider == VectorStoreProvider.WEAVIATE:
        return WeaviateVectorStore(config)
    else:
        return MockVectorStore(config)


async def get_vector_store(
    provider: Optional[str] = None,
    config: Optional[VectorStoreConfig] = None,
) -> SpecGenVectorStore:
    """
    Get an initialized vector store.
    
    Args:
        provider: Provider name
        config: Optional configuration
    
    Returns:
        Initialized vector store
    """
    store = create_vector_store(provider, config)
    await store.initialize()
    return store
