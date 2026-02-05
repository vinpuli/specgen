"""
LLM Provider integration for Anthropic, OpenAI, and embeddings.

This module provides a unified interface for LLM operations with
support for multiple providers, model selection, and retry logic.
"""

import os
import time
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from functools import wraps, lru_cache
from concurrent.futures import ThreadPoolExecutor
import asyncio

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_anthropic import AnthropicEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.language_models import BaseChatModel

from .exceptions import (
    LLMException,
    LLMGenerationError,
    LLMTimeoutError,
    LLMRateLimitError,
)


# ==================== Provider Types ====================

class LLMProvider(str, Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    provider: LLMProvider
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: Optional[float] = None
    streaming: bool = True
    api_key_env: str = "ANTHROPIC_API_KEY"


@dataclass
class EmbeddingConfig:
    """Configuration for an embedding model."""
    provider: EmbeddingProvider
    model_name: str
    dimensions: int = 1536
    api_key_env: str = "ANTHROPIC_API_KEY"


# ==================== Default Model Configurations ====================

# Chat models
DEFAULT_ANTHROPIC_MODEL = ModelConfig(
    provider=LLMProvider.ANTHROPIC,
    model_name="claude-sonnet-4-20250514",
    max_tokens=8192,
    temperature=0.7,
    api_key_env="ANTHROPIC_API_KEY",
)

DEFAULT_OPENAI_MODEL = ModelConfig(
    provider=LLMProvider.OPENAI,
    model_name="gpt-4o",
    max_tokens=4096,
    temperature=0.7,
    api_key_env="OPENAI_API_KEY",
)

# Embedding models
DEFAULT_ANTHROPIC_EMBEDDING = EmbeddingConfig(
    provider=EmbeddingProvider.ANTHROPIC,
    model_name="claude-sonnet-4-20250514",
    dimensions=1024,
    api_key_env="ANTHROPIC_API_KEY",
)

DEFAULT_OPENAI_EMBEDDING = EmbeddingConfig(
    provider=EmbeddingProvider.OPENAI,
    model_name="text-embedding-3-small",
    dimensions=1536,
    api_key_env="OPENAI_API_KEY",
)


# ==================== Callback Handler ====================

class LLMCallbackHandler(BaseCallbackHandler):
    """Callback handler for LLM operations."""
    
    def __init__(self, on_token: Optional[Callable[[str], None]] = None):
        self.on_token = on_token
        self.tokens: List[str] = []
        self.total_tokens: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs,
    ):
        self.tokens.clear()
    
    def on_llm_new_token(self, token: str, **kwargs):
        self.tokens.append(token)
        self.total_tokens += 1
        if self.on_token:
            self.on_token(token)
    
    def on_llm_end(self, response: ChatResult, **kwargs):
        if response.usage_metadata:
            self.prompt_tokens = response.usage_metadata.get("input_tokens", 0)
            self.completion_tokens = response.usage_metadata.get("output_tokens", 0)
            self.total_tokens = self.prompt_tokens + self.completion_tokens
    
    def on_llm_error(self, error: Exception, **kwargs):
        pass


# ==================== LLM Client ====================

class LLMClient:
    """
    Unified LLM client supporting multiple providers.
    
    Provides a consistent interface for chat completions,
    streaming, and embeddings across Anthropic and OpenAI.
    """
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        default_model: Optional[ModelConfig] = None,
        callback_handler: Optional[LLMCallbackHandler] = None,
    ):
        """
        Initialize the LLM client.
        
        Args:
            anthropic_api_key: Anthropic API key
            openai_api_key: OpenAI API key
            default_model: Default model configuration
            callback_handler: Optional callback handler
        """
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.default_model = default_model or DEFAULT_ANTHROPIC_MODEL
        self.callback_handler = callback_handler
        self._clients: Dict[LLMProvider, BaseChatModel] = {}
    
    def _get_anthropic_client(self, model: ModelConfig) -> ChatAnthropic:
        """Get or create Anthropic client."""
        if LLMProvider.ANTHROPIC not in self._clients:
            self._clients[LLMProvider.ANTHROPIC] = ChatAnthropic(
                model=model.model_name,
                max_tokens=model.max_tokens,
                temperature=model.temperature,
                anthropic_api_key=self.anthropic_api_key,
                callbacks=[self.callback_handler] if self.callback_handler else [],
                streaming=model.streaming,
            )
        return self._clients[LLMProvider.ANTHROPIC]
    
    def _get_openai_client(self, model: ModelConfig) -> ChatOpenAI:
        """Get or create OpenAI client."""
        if LLMProvider.OPENAI not in self._clients:
            self._clients[LLMProvider.OPENAI] = ChatOpenAI(
                model=model.model_name,
                max_tokens=model.max_tokens,
                temperature=model.temperature,
                api_key=self.openai_api_key,
                callbacks=[self.callback_handler] if self.callback_handler else [],
                streaming=model.streaming,
            )
        return self._clients[LLMProvider.OPENAI]
    
    def get_client(
        self,
        model: Optional[ModelConfig] = None,
    ) -> BaseChatModel:
        """
        Get an LLM client for the specified model.
        
        Args:
            model: Model configuration (uses default if not specified)
        
        Returns:
            LangChain chat model instance
        """
        model = model or self.default_model
        
        if model.provider == LLMProvider.ANTHROPIC:
            return self._get_anthropic_client(model)
        elif model.provider == LLMProvider.OPENAI:
            return self._get_openai_client(model)
        else:
            raise ValueError(f"Unknown provider: {model.provider}")
    
    async def ainvoke(
        self,
        messages: List[Union[BaseMessage, str]],
        model: Optional[ModelConfig] = None,
        **kwargs,
    ) -> ChatResult:
        """
        Invoke the LLM with messages (non-streaming).
        
        Args:
            messages: List of messages
            model: Model configuration
            **kwargs: Additional arguments
        
        Returns:
            ChatResult from the LLM
        """
        client = self.get_client(model)
        
        # Convert strings to messages
        processed_messages = []
        for msg in messages:
            if isinstance(msg, str):
                processed_messages.append(HumanMessage(content=msg))
            else:
                processed_messages.append(msg)
        
        try:
            return await client.ainvoke(processed_messages, **kwargs)
        except Exception as e:
            self._handle_error(e, model)
    
    async def astream(
        self,
        messages: List[Union[BaseMessage, str]],
        model: Optional[ModelConfig] = None,
        on_token: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from the LLM.
        
        Args:
            messages: List of messages
            model: Model configuration
            on_token: Callback for each token
            **kwargs: Additional arguments
        
        Yields:
            Token strings from the LLM
        """
        client = self.get_client(model)
        
        # Convert strings to messages
        processed_messages = []
        for msg in messages:
            if isinstance(msg, str):
                processed_messages.append(HumanMessage(content=msg))
            else:
                processed_messages.append(msg)
        
        callback = LLMCallbackHandler(on_token=on_token)
        
        try:
            async for chunk in client.astream(processed_messages, **kwargs):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            self._handle_error(e, model)
    
    async def agenerate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        model: Optional[ModelConfig] = None,
        **kwargs,
    ) -> ChatGeneration:
        """
        Generate a response with optional system message.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            model: Model configuration
            **kwargs: Additional arguments
        
        Returns:
            ChatGeneration with the response
        """
        messages = []
        
        if system_message:
            messages.append(SystemMessage(content=system_message))
        
        messages.append(HumanMessage(content=prompt))
        
        result = await self.ainvoke(messages, model, **kwargs)
        
        if result.generations:
            return result.generations[0]
        else:
            raise LLMGenerationError(
                message="No generations returned",
                provider=model.provider if model else self.default_model.provider,
                model=model.model_name if model else self.default_model.model_name,
            )
    
    def _handle_error(
        self,
        error: Exception,
        model: Optional[ModelConfig],
    ) -> None:
        """Handle LLM errors with appropriate exception types."""
        model_config = model or self.default_model
        provider = model_config.provider.value
        model_name = model_config.model_name
        
        error_str = str(error).lower()
        
        if "timeout" in error_str or "timed out" in error_str:
            raise LLMTimeoutError(
                provider=provider,
                model=model_name,
                timeout_seconds=30,
            )
        elif "rate limit" in error_str or "429" in error_str:
            raise LLMRateLimitError(
                provider=provider,
                retry_after=60,
            )
        else:
            raise LLMGenerationError(
                message=str(error),
                provider=provider,
                model=model_name,
            )


# ==================== Embedding Client ====================

class EmbeddingClient:
    """
    Unified embedding client for multiple providers.
    
    Provides a consistent interface for generating embeddings
    with Anthropic and OpenAI providers.
    """
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        default_config: Optional[EmbeddingConfig] = None,
    ):
        """
        Initialize the embedding client.
        
        Args:
            anthropic_api_key: Anthropic API key
            openai_api_key: OpenAI API key
            default_config: Default embedding configuration
        """
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.default_config = default_config or DEFAULT_OPENAI_EMBEDDING
        self._clients: Dict[EmbeddingProvider, Any] = {}
    
    def _get_anthropic_embeddings(self, config: EmbeddingConfig):
        """Get Anthropic embeddings client."""
        if EmbeddingProvider.ANTHROPIC not in self._clients:
            self._clients[EmbeddingProvider.ANTHROPIC] = AnthropicEmbeddings(
                model=config.model_name,
                api_key=self.anthropic_api_key,
            )
        return self._clients[EmbeddingProvider.ANTHROPIC]
    
    def _get_openai_embeddings(self, config: EmbeddingConfig):
        """Get OpenAI embeddings client."""
        if EmbeddingProvider.OPENAI not in self._clients:
            self._clients[EmbeddingProvider.OPENAI] = OpenAIEmbeddings(
                model=config.model_name,
                api_key=self.openai_api_key,
            )
        return self._clients[EmbeddingProvider.OPENAI]
    
    def get_client(
        self,
        config: Optional[EmbeddingConfig] = None,
    ):
        """Get an embeddings client."""
        config = config or self.default_config
        
        if config.provider == EmbeddingProvider.ANTHROPIC:
            return self._get_anthropic_embeddings(config)
        elif config.provider == EmbeddingProvider.OPENAI:
            return self._get_openai_embeddings(config)
        else:
            raise ValueError(f"Unknown provider: {config.provider}")
    
    async def aembed_query(self, text: str, config: Optional[EmbeddingConfig] = None) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            text: Text to embed
            config: Embedding configuration
        
        Returns:
            List of embedding dimensions
        """
        client = self.get_client(config)
        
        # Check if client supports async
        if hasattr(client, 'aembed_query'):
            return await client.aembed_query(text)
        else:
            # Fall back to sync in executor
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                return await loop.run_in_executor(executor, client.embed_query, text)
    
    async def aembed_documents(
        self,
        texts: List[str],
        config: Optional[EmbeddingConfig] = None,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple documents.
        
        Args:
            texts: List of texts to embed
            config: Embedding configuration
        
        Returns:
            List of embeddings
        """
        client = self.get_client(config)
        
        # Check if client supports async
        if hasattr(client, 'aembed_documents'):
            return await client.aembed_documents(texts)
        else:
            # Fall back to sync in executor
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                return await loop.run_in_executor(executor, client.embed_documents, texts)


# ==================== Model Selector ====================

class TaskComplexity(str, Enum):
    """Task complexity levels for model selection."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    REASONING = "reasoning"


@dataclass
class ModelSelection:
    """Result of model selection."""
    provider: LLMProvider
    model_name: str
    reasoning: str
    estimated_cost: float


def select_model(
    task_complexity: TaskComplexity,
    prefer_speed: bool = False,
    prefer_cost: bool = False,
) -> ModelSelection:
    """
    Select the appropriate model based on task complexity.
    
    Args:
        task_complexity: Complexity of the task
        prefer_speed: Prefer faster models
        prefer_cost: Prefer cheaper models
    
    Returns:
        ModelSelection with chosen model
    """
    selection_rules = {
        TaskComplexity.SIMPLE: ModelSelection(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4o-mini",
            reasoning="Simple tasks use faster, cheaper model",
            estimated_cost=0.01,
        ),
        TaskComplexity.MODERATE: ModelSelection(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4o",
            reasoning="Moderate tasks use balanced model",
            estimated_cost=0.03,
        ),
        TaskComplexity.COMPLEX: ModelSelection(
            provider=LLMProvider.ANTHROPIC,
            model_name="claude-sonnet-4-20250514",
            reasoning="Complex tasks use Claude for better quality",
            estimated_cost=0.08,
        ),
        TaskComplexity.REASONING: ModelSelection(
            provider=LLMProvider.ANTHROPIC,
            model_name="claude-sonnet-4-20250514",
            reasoning="Reasoning tasks use Claude for extended thinking",
            estimated_cost=0.15,
        ),
    }
    
    return selection_rules[task_complexity]


# ==================== Retry Logic ====================

def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
):
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
    
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except LLMRateLimitError as e:
                    last_exception = e
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    await asyncio.sleep(delay)
                except LLMTimeoutError as e:
                    last_exception = e
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    await asyncio.sleep(delay)
                except Exception as e:
                    # Don't retry on other errors
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator


# ==================== Factory Functions ====================

@lru_cache()
def get_llm_client(
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> LLMClient:
    """
    Get a cached LLM client instance.
    
    Args:
        anthropic_api_key: Anthropic API key
        openai_api_key: OpenAI API key
    
    Returns:
        LLMClient instance
    """
    return LLMClient(
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
    )


@lru_cache()
def get_embedding_client(
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> EmbeddingClient:
    """
    Get a cached embedding client instance.
    
    Args:
        anthropic_api_key: Anthropic API key
        openai_api_key: OpenAI API key
    
    Returns:
        EmbeddingClient instance
    """
    return EmbeddingClient(
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
    )
