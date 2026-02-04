"""
Vector Database Client

Supports multiple vector database providers:
- Pinecone (cloud)
- Weaviate (local/cloud)
- PGVector (PostgreSQL extension)
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
import numpy as np


class VectorDBClient(ABC):
    """Abstract base class for vector database clients."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the vector database."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the vector database."""
        pass

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimension: int,
        metric: str = "cosine",
        **kwargs,
    ) -> None:
        """Create a collection/index."""
        pass

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """Delete a collection/index."""
        pass

    @abstractmethod
    async def upsert(
        self,
        collection_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> None:
        """Upsert vectors with metadata."""
        pass

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        pass

    @abstractmethod
    async def delete(self, collection_name: str, ids: List[str]) -> None:
        """Delete vectors by ID."""
        pass

    @abstractmethod
    async def get_collection_info(self, name: str) -> Dict[str, Any]:
        """Get collection/index information."""
        pass


class PineconeClient(VectorDBClient):
    """Pinecone cloud vector database client."""

    def __init__(
        self,
        api_key: str = None,
        environment: str = None,
        index_name: str = None,
    ):
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment or os.getenv("PINECONE_ENVIRONMENT")
        self.index_name = index_name or os.getenv("PINECONE_INDEX_NAME", "specgen")
        self.base_url = f"https://controller.{self.environment}.pinecone.io"
        self.index_url = f"https://{self.index_name}-{self.environment}.svc.pinecone.io"
        self._client = httpx.AsyncClient(
            headers={"Api-Key": self.api_key},
            timeout=30.0,
        )

    async def connect(self) -> None:
        """Connect to Pinecone."""
        # Verify connection by fetching index info
        response = await self._client.get(
            f"{self.base_url}/databases/{self.index_name}"
        )
        response.raise_for_status()

    async def disconnect(self) -> None:
        """Disconnect from Pinecone."""
        await self._client.aclose()

    async def create_collection(
        self,
        name: str,
        dimension: int,
        metric: str = "cosine",
        **kwargs,
    ) -> None:
        """Create a Pinecone index."""
        response = await self._client.post(
            f"{self.base_url}/databases",
            json={
                "name": name,
                "dimension": dimension,
                "metric": metric,
                "pod_type": kwargs.get("pod_type", "p1"),
                "replicas": kwargs.get("replicas", 1),
            },
        )
        response.raise_for_status()

    async def delete_collection(self, name: str) -> None:
        """Delete a Pinecone index."""
        response = await self._client.delete(
            f"{self.base_url}/databases/{name}"
        )
        response.raise_for_status()

    async def upsert(
        self,
        collection_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> None:
        """Upsert vectors to Pinecone."""
        vectors_data = [
            {
                "id": id,
                "values": vector,
                "metadata": metadata,
            }
            for id, vector, metadata in vectors
        ]

        response = await self._client.post(
            f"{self.index_url}/vectors/upsert",
            json={"vectors": vectors_data},
        )
        response.raise_for_status()

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors in Pinecone."""
        query_request = {
            "vector": query_vector,
            "topK": limit,
            "includeMetadata": True,
        }

        if filters:
            query_request["filter"] = filters

        response = await self._client.post(
            f"{self.index_url}/query",
            json=query_request,
        )
        response.raise_for_status()

        return [
            {
                "id": match["id"],
                "score": match["score"],
                "metadata": match.get("metadata", {}),
            }
            for match in response.json()["matches"]
        ]

    async def delete(self, collection_name: str, ids: List[str]) -> None:
        """Delete vectors by ID."""
        response = await self._client.post(
            f"{self.index_url}/vectors/delete",
            json={"ids": ids},
        )
        response.raise_for_status()

    async def get_collection_info(self, name: str) -> Dict[str, Any]:
        """Get Pinecone index information."""
        response = await self._client.get(
            f"{self.base_url}/databases/{name}"
        )
        response.raise_for_status()
        return response.json()


class WeaviateClient(VectorDBClient):
    """Weaviate vector database client."""

    def __init__(
        self,
        url: str = None,
        api_key: str = None,
    ):
        self.url = url or os.getenv("WEAVIATE_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("WEAVIATE_API_KEY", "")
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            base_url=self.url,
            timeout=30.0,
        )

    async def connect(self) -> None:
        """Connect to Weaviate."""
        response = await self._client.get("/v1/meta")
        response.raise_for_status()

    async def disconnect(self) -> None:
        """Disconnect from Weaviate."""
        await self._client.aclose()

    async def create_collection(
        self,
        name: str,
        dimension: int,
        metric: str = "cosine",
        **kwargs,
    ) -> None:
        """Create a Weaviate class."""
        class_schema = {
            "class": name,
            "description": kwargs.get("description", ""),
            "vectorizer": kwargs.get("vectorizer", "text2vec-transformers"),
            "moduleConfig": {
                "text2vec-transformers": {
                    "vectorizeClassName": False,
                }
            },
            "properties": kwargs.get(
                "properties",
                [
                    {"name": "text", "dataType": ["text"]},
                    {"name": "source", "dataType": ["text"]},
                    {"name": "metadata", "dataType": ["object"]},
                ],
            ),
        }

        response = await self._client.post(
            "/v1/schema",
            json=class_schema,
        )
        if response.status_code != 409:  # Ignore if already exists
            response.raise_for_status()

    async def delete_collection(self, name: str) -> None:
        """Delete a Weaviate class."""
        response = await self._client.delete(f"/v1/schema/{name}")
        response.raise_for_status()

    async def upsert(
        self,
        collection_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> None:
        """Upsert vectors to Weaviate."""
        objects = [
            {
                "id": id,
                "vector": vector,
                "properties": metadata,
            }
            for id, vector, metadata in vectors
        ]

        response = await self._client.post(
            f"/v1/objects/batch",
            json={"objects": objects},
        )
        response.raise_for_status()

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors in Weaviate."""
        query = {
            "vector": query_vector,
            "limit": limit,
            "fields": "id,metadata,text",
        }

        if filters:
            query["where_filter"] = filters

        response = await self._client.post(
            f"/v1/objects/{collection_name}",
            params={"search": "vector"},
            json=query,
        )
        response.raise_for_status()

        return [
            {
                "id": obj.get("id"),
                "score": obj.get("_additional", {}).get("certainty", 0),
                "metadata": obj.get("metadata", {}),
                "text": obj.get("text", ""),
            }
            for obj in response.json().get("results", response.json())
        ]

    async def delete(self, collection_name: str, ids: List[str]) -> None:
        """Delete vectors by ID."""
        for id in ids:
            response = await self._client.delete(f"/v1/objects/{collection_name}/{id}")
            response.raise_for_status()

    async def get_collection_info(self, name: str) -> Dict[str, Any]:
        """Get Weaviate class information."""
        response = await self._client.get(f"/v1/schema/{name}")
        response.raise_for_status()
        return response.json()


class PGVectorClient(VectorDBClient):
    """PGVector PostgreSQL extension client."""

    def __init__(
        self,
        connection_string: str = None,
    ):
        from backend.db.connection import DATABASE_URL_SYNC

        self.connection_string = connection_string or DATABASE_URL_SYNC
        self._engine = None
        self._conn = None

    async def connect(self) -> None:
        """Connect to PostgreSQL with PGVector."""
        from sqlalchemy import create_engine, text

        self._engine = create_engine(self.connection_string)
        self._conn = self._engine.connect()

        # Enable vector extension
        self._conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        self._conn.commit()

    async def disconnect(self) -> None:
        """Disconnect from PostgreSQL."""
        if self._conn:
            self._conn.close()
        if self._engine:
            self._engine.dispose()

    async def create_collection(
        self,
        name: str,
        dimension: int,
        metric: str = "cosine",
        **kwargs,
    ) -> None:
        """Create a PGVector table."""
        from sqlalchemy import text

        # Create table with vector column
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {name} (
            id VARCHAR(64) PRIMARY KEY,
            embedding vector({dimension}),
            metadata JSONB DEFAULT '{{}}',
            text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
        self._conn.execute(text(create_sql))
        self._conn.commit()

        # Create index for vector similarity search
        if metric == "cosine":
            index_type = "vector_cosine_ops"
        elif metric == "l2":
            index_type = "vector_l2_ops"
        else:
            index_type = "vector_inner_product_ops"

        index_sql = f"""
        CREATE INDEX IF NOT EXISTS {name}_embedding_idx
        ON {name} USING ivfflat (embedding {index_type})
        """
        try:
            self._conn.execute(text(index_sql))
            self._conn.commit()
        except Exception:
            # IVFFLAT index might need data first
            pass

    async def delete_collection(self, name: str) -> None:
        """Delete a PGVector table."""
        from sqlalchemy import text

        self._conn.execute(text(f"DROP TABLE IF EXISTS {name} CASCADE"))
        self._conn.commit()

    async def upsert(
        self,
        collection_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> None:
        """Upsert vectors to PGVector."""
        from sqlalchemy import text

        for id, vector, metadata in vectors:
            upsert_sql = f"""
            INSERT INTO {collection_name} (id, embedding, metadata, text)
            VALUES (:id, :embedding, :metadata, :text)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                text = EXCLUDED.text,
                created_at = NOW()
            """
            self._conn.execute(
                text(upsert_sql),
                {
                    "id": id,
                    "embedding": vector,
                    "metadata": metadata,
                    "text": metadata.get("text", ""),
                },
            )
        self._conn.commit()

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors in PGVector."""
        from sqlalchemy import text
        import numpy as np

        # Calculate similarity
        if filters:
            # Basic filtering support
            where_clause = "WHERE " + " AND ".join(
                f"metadata->>'{k}' = :{k}" for k in filters.keys()
            )
        else:
            where_clause = ""

        search_sql = f"""
        SELECT id, embedding <-> :query_vector as distance,
               metadata, text
        FROM {collection_name}
        {where_clause}
        ORDER BY embedding <=> :query_vector
        LIMIT :limit
        """

        params = {"query_vector": query_vector, "limit": limit}
        params.update(filters or {})

        result = self._conn.execute(text(search_sql), params)

        return [
            {
                "id": row[0],
                "score": 1 - float(row[1]) if row[1] else 0,  # Convert distance to similarity
                "metadata": row[2] or {},
                "text": row[3],
            }
            for row in result.fetchall()
        ]

    async def delete(self, collection_name: str, ids: List[str]) -> None:
        """Delete vectors by ID."""
        from sqlalchemy import text

        for id in ids:
            self._conn.execute(
                text(f"DELETE FROM {collection_name} WHERE id = :id"),
                {"id": id},
            )
        self._conn.commit()

    async def get_collection_info(self, name: str) -> Dict[str, Any]:
        """Get PGVector table information."""
        from sqlalchemy import text

        result = self._conn.execute(
            text(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = :name
            """),
            {"name": name},
        )

        return {
            "name": name,
            "columns": [dict(row._mapping) for row in result.fetchall()],
        }


def get_vector_client() -> VectorDBClient:
    """Get vector database client based on configuration."""
    provider = os.getenv("VECTOR_DB_PROVIDER", "pinecone")

    if provider == "pinecone":
        return PineconeClient()
    elif provider == "weaviate":
        return WeaviateClient()
    elif provider == "pgvector":
        return PGVectorClient()
    else:
        raise ValueError(f"Unknown vector database provider: {provider}")
