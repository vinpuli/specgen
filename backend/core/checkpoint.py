"""
LangGraph checkpoint system with Redis backend for state persistence.

This module provides checkpoint saving and loading functionality
for LangGraph agents, enabling state recovery and conversation resumption.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    Serializable,
    dump_python,
    load_python,
)
from langgraph.checkpoint.serde.base import SerializerProtocol

from ..core.exceptions import CheckpointError


# ==================== Redis Serializer ====================

class RedisSerializer(SerializerProtocol):
    """Custom serializer for Redis checkpoint storage."""
    
    def dumps(self, value: Serializable) -> bytes:
        """Serialize a value to bytes for Redis storage."""
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, dict):
            return json.dumps(value, default=str).encode("utf-8")
        if isinstance(value, list):
            return json.dumps(value, default=str).encode("utf-8")
        # For complex objects, use dump_python from langgraph
        return dump_python(value)
    
    def loads(self, value: bytes) -> Any:
        """Deserialize bytes from Redis storage."""
        try:
            # Try JSON first for simple types
            return json.loads(value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to langgraph's load_python
            return load_python(value)


# ==================== Redis Checkpoint Saver ====================

class RedisCheckpointSaver(BaseCheckpointSaver):
    """
    Redis-backed checkpoint saver for LangGraph.
    
    Provides persistent storage for agent state, enabling
    conversation resumption and recovery after failures.
    """
    
    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        redis_url: Optional[str] = None,
        key_prefix: str = "checkpoint:",
        ttl_seconds: Optional[int] = None,
        thread_id_prefix: str = "",
    ):
        """
        Initialize the Redis checkpoint saver.
        
        Args:
            redis_client: Pre-configured Redis client
            redis_url: Redis connection URL
            key_prefix: Prefix for checkpoint keys in Redis
            ttl_seconds: Time-to-live for checkpoints (None = no expiration)
            thread_id_prefix: Prefix for thread IDs
        """
        super().__init__(serde=RedisSerializer())
        self.redis_client = redis_client
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds
        self.thread_id_prefix = thread_id_prefix
        self._own_client = redis_client is None
    
    @asynccontextmanager
    async def client(self):
        """Get a Redis client, creating one if needed."""
        if self.redis_client:
            yield self.redis_client
        else:
            client = redis.from_url(self.redis_url, decode_responses=False)
            try:
                yield client
            finally:
                await client.close()
    
    def _make_key(self, thread_id: str, checkpoint_id: str) -> str:
        """Generate a Redis key for a checkpoint."""
        return f"{self.key_prefix}{self.thread_id_prefix}{thread_id}:{checkpoint_id}"
    
    def _make_thread_key(self, thread_id: str) -> str:
        """Generate a Redis key for thread metadata."""
        return f"{self.key_prefix}{self.thread_id_prefix}{thread_id}:meta"
    
    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> Dict[str, Any]:
        """
        Save a checkpoint to Redis.
        
        Args:
            config: Runnable configuration
            checkpoint: Checkpoint data to save
            metadata: Checkpoint metadata
        
        Returns:
            Updated configuration with checkpoint ID
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise CheckpointError(
                operation="save",
                thread_id=thread_id or "unknown",
                message="thread_id is required in config",
            )
        
        checkpoint_id = checkpoint.get("id", str(datetime.utcnow().timestamp()))
        
        async with self.client() as client:
            try:
                # Serialize checkpoint
                checkpoint_data = self.serde.dumps(checkpoint)
                
                # Serialize metadata
                metadata_data = self.serde.dumps({
                    "metadata": metadata,
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "created_at": datetime.utcnow().isoformat(),
                })
                
                # Create composite key
                key = self._make_key(thread_id, checkpoint_id)
                
                # Store checkpoint and metadata
                await client.set(key, checkpoint_data)
                await client.set(f"{key}:meta", metadata_data)
                
                # Update thread metadata
                thread_key = self._make_thread_key(thread_id)
                thread_data = {
                    "last_checkpoint_id": checkpoint_id,
                    "last_updated": datetime.utcnow().isoformat(),
                    "checkpoint_count": await client.incr(f"{thread_key}:count"),
                }
                await client.hset(thread_key, mapping=thread_data)
                
                # Set TTL if configured
                if self.ttl_seconds:
                    await client.expire(key, self.ttl_seconds)
                    await client.expire(f"{key}:meta", self.ttl_seconds)
                
                return {
                    "configurable": {
                        **config.get("configurable", {}),
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                    }
                }
            
            except RedisError as e:
                raise CheckpointError(
                    operation="save",
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    original_error=e,
                )
    
    async def aget(
        self,
        config: Dict[str, Any],
    ) -> Optional[Checkpoint]:
        """
        Retrieve a checkpoint from Redis.
        
        Args:
            config: Runnable configuration with thread_id and checkpoint_id
        
        Returns:
            Checkpoint data if found, None otherwise
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")
        
        if not thread_id:
            return None
        
        async with self.client() as client:
            try:
                if checkpoint_id:
                    key = self._make_key(thread_id, checkpoint_id)
                    data = await client.get(key)
                    if data:
                        return self.serde.loads(data)
                else:
                    # Get latest checkpoint
                    thread_key = self._make_thread_key(thread_id)
                    last_id = await client.hget(thread_key, "last_checkpoint_id")
                    if last_id:
                        key = self._make_key(thread_id, last_id)
                        data = await client.get(key)
                        if data:
                            return self.serde.loads(data)
                
                return None
            
            except RedisError as e:
                raise CheckpointError(
                    operation="load",
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    original_error=e,
                )
    
    async def aget_next_version(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
    ) -> int:
        """
        Get the next version number for a checkpoint.
        
        Args:
            thread_id: Thread identifier
            checkpoint_ns: Namespace for the checkpoint
        
        Returns:
            Next version number
        """
        async with self.client() as client:
            key = f"{self.key_prefix}{self.thread_id_prefix}{thread_id}:versions:{checkpoint_ns}"
            version = await client.incr(key)
            return version
    
    async def alist(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        limit: int = 10,
        before: Optional[str] = None,
        after: Optional[str] = None,
    ) -> List[Checkpoint]:
        """
        List checkpoints for a thread.
        
        Args:
            config: Runnable configuration with thread_id
            limit: Maximum number of checkpoints to return
            before: Return checkpoints before this ID
            after: Return checkpoints after this ID
        
        Returns:
            List of checkpoints
        """
        thread_id = config.get("configurable", {}).get("thread_id") if config else None
        
        if not thread_id:
            return []
        
        async with self.client() as client:
            try:
                pattern = f"{self.key_prefix}{self.thread_id_prefix}{thread_id}:*"
                keys = []
                async for key in client.scan_iter(match=pattern, count=100):
                    if not key.endswith(":meta"):
                        keys.append(key)
                
                checkpoints = []
                for key in keys[:limit]:
                    data = await client.get(key)
                    if data:
                        checkpoint = self.serde.loads(data)
                        checkpoints.append(checkpoint)
                
                # Sort by checkpoint ID (timestamp-based)
                checkpoints.sort(key=lambda x: x.get("id", ""), reverse=True)
                
                return checkpoints[:limit]
            
            except RedisError as e:
                raise CheckpointError(
                    operation="list",
                    thread_id=thread_id or "unknown",
                    original_error=e,
                )
    
    async def adelete(
        self,
        config: Dict[str, Any],
    ) -> bool:
        """
        Delete a checkpoint from Redis.
        
        Args:
            config: Runnable configuration with thread_id and checkpoint_id
        
        Returns:
            True if deleted, False otherwise
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")
        
        if not thread_id or not checkpoint_id:
            return False
        
        async with self.client() as client:
            try:
                key = self._make_key(thread_id, checkpoint_id)
                deleted = await client.delete(key)
                await client.delete(f"{key}:meta")
                return deleted > 0
            
            except RedisError as e:
                raise CheckpointError(
                    operation="delete",
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    original_error=e,
                )
    
    async def aclose(self):
        """Close the Redis client if we own it."""
        if self._own_client and self.redis_client:
            await self.redis_client.close()


# ==================== Checkpoint Manager ====================

class CheckpointManager:
    """
    High-level manager for LangGraph checkpoints.
    
    Provides simplified API for common checkpoint operations.
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "specgen:checkpoint:",
        ttl_hours: int = 24,
    ):
        """
        Initialize the checkpoint manager.
        
        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for checkpoint keys
            ttl_hours: Default TTL for checkpoints in hours
        """
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_hours * 3600
        self._saver: Optional[RedisCheckpointSaver] = None
    
    @property
    def saver(self) -> RedisCheckpointSaver:
        """Get or create the checkpoint saver."""
        if self._saver is None:
            self._saver = RedisCheckpointSaver(
                redis_url=self.redis_url,
                key_prefix=self.key_prefix,
                ttl_seconds=self.ttl_seconds,
            )
        return self._saver
    
    async def save_checkpoint(
        self,
        thread_id: str,
        checkpoint: Checkpoint,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save a checkpoint for a thread.
        
        Args:
            thread_id: Unique thread identifier
            checkpoint: Checkpoint data to save
            metadata: Optional metadata to store
        
        Returns:
            Configuration with checkpoint ID
        """
        checkpoint_metadata = CheckpointMetadata(
            thread_id=thread_id,
            checkpoint_id=checkpoint.get("id", str(datetime.utcnow().timestamp())),
            source="api",
            steps_completed=checkpoint.get("versions", {}),
            metadata=metadata or {},
        )
        
        config = {"configurable": {"thread_id": thread_id}}
        return await self.saver.aput(config, checkpoint, checkpoint_metadata)
    
    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """
        Load a checkpoint for a thread.
        
        Args:
            thread_id: Unique thread identifier
            checkpoint_id: Specific checkpoint ID (latest if not provided)
        
        Returns:
            Checkpoint data if found
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        return await self.saver.aget(config)
    
    async def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> List[Checkpoint]:
        """
        List all checkpoints for a thread.
        
        Args:
            thread_id: Unique thread identifier
            limit: Maximum number to return
        
        Returns:
            List of checkpoints
        """
        config = {"configurable": {"thread_id": thread_id}}
        return await self.saver.alist(config, limit=limit)
    
    async def delete_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
    ) -> bool:
        """
        Delete a specific checkpoint.
        
        Args:
            thread_id: Unique thread identifier
            checkpoint_id: Checkpoint to delete
        
        Returns:
            True if deleted
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        return await self.saver.adelete(config)
    
    async def delete_thread_checkpoints(
        self,
        thread_id: str,
    ) -> int:
        """
        Delete all checkpoints for a thread.
        
        Args:
            thread_id: Unique thread identifier
        
        Returns:
            Number of checkpoints deleted
        """
        checkpoints = await self.list_checkpoints(thread_id, limit=1000)
        deleted = 0
        
        for checkpoint in checkpoints:
            cid = checkpoint.get("id")
            if cid:
                success = await self.delete_checkpoint(thread_id, cid)
                if success:
                    deleted += 1
        
        return deleted
    
    async def get_thread_info(
        self,
        thread_id: str,
    ) -> Dict[str, Any]:
        """
        Get information about a thread's checkpoints.
        
        Args:
            thread_id: Unique thread identifier
        
        Returns:
            Thread information dict
        """
        async with self.saver.client() as client:
            thread_key = f"{self.key_prefix}{thread_id}:meta"
            info = await client.hgetall(thread_key)
            
            if info:
                return {
                    "thread_id": thread_id,
                    "last_checkpoint_id": info.get("last_checkpoint_id"),
                    "last_updated": info.get("last_updated"),
                    "checkpoint_count": int(info.get("checkpoint_count", 0)),
                }
            
            return {
                "thread_id": thread_id,
                "last_checkpoint_id": None,
                "last_updated": None,
                "checkpoint_count": 0,
            }
    
    async def close(self):
        """Close the checkpoint manager."""
        if self._saver:
            await self._saver.aclose()
            self._saver = None


# ==================== Factory Functions ====================

def get_checkpoint_saver(
    redis_url: Optional[str] = None,
    key_prefix: str = "specgen:checkpoint:",
    ttl_seconds: Optional[int] = None,
) -> RedisCheckpointSaver:
    """
    Factory function to create a Redis checkpoint saver.
    
    Args:
        redis_url: Redis connection URL
        key_prefix: Prefix for checkpoint keys
        ttl_seconds: Optional TTL for checkpoints
    
    Returns:
        Configured RedisCheckpointSaver instance
    """
    return RedisCheckpointSaver(
        redis_url=redis_url,
        key_prefix=key_prefix,
        ttl_seconds=ttl_seconds,
    )


def get_checkpoint_manager(
    redis_url: Optional[str] = None,
    key_prefix: str = "specgen:checkpoint:",
    ttl_hours: int = 24,
) -> CheckpointManager:
    """
    Factory function to create a checkpoint manager.
    
    Args:
        redis_url: Redis connection URL
        key_prefix: Prefix for checkpoint keys
        ttl_hours: Default TTL in hours
    
    Returns:
        Configured CheckpointManager instance
    """
    return CheckpointManager(
        redis_url=redis_url,
        key_prefix=key_prefix,
        ttl_hours=ttl_hours,
    )
