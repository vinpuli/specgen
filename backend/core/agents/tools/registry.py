"""
Tool Registry for LangGraph agents.

Provides tool discovery, registration, and management:
- Automatic tool discovery via decorators
- Tool registry singleton for centralized management
- Tool metadata and schema storage
- Tool versioning and compatibility checks
- Tool categorization and filtering
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type
from uuid import UUID, uuid4

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class ToolStatus(str, Enum):
    """Tool status enum."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    DISABLED = "disabled"


class ToolCategory(str, Enum):
    """Tool categories."""

    DATABASE = "database"
    VECTOR_STORE = "vector_store"
    FILE_OPERATIONS = "file_operations"
    GIT = "git"
    CODE_ANALYSIS = "code_analysis"
    EXPORT = "export"
    COMMUNICATION = "communication"
    UTILITY = "utility"


class ToolMetadata(BaseModel):
    """Metadata for a registered tool."""

    tool_id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    version: str = Field(default="1.0.0", description="Tool version")
    category: ToolCategory = Field(..., description="Tool category")
    status: ToolStatus = Field(default=ToolStatus.ACTIVE, description="Tool status")
    author: Optional[str] = Field(None, description="Tool author")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Creation timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Last update timestamp",
    )
    tags: List[str] = Field(default_factory=list, description="Tool tags")
    dependencies: Dict[str, str] = Field(
        default_factory=dict, description="Tool dependencies"
    )
    permissions: List[str] = Field(default_factory=list, description="Required permissions")
    rate_limit: Optional[Dict[str, int]] = Field(
        None, description="Rate limits (e.g., {'requests': 100, 'per': 'minute'})"
    )


class ToolSchema(BaseModel):
    """Input/output schema for a tool."""

    input_schema: Dict[str, Any] = Field(..., description="Input JSON schema")
    output_schema: Dict[str, Any] = Field(..., description="Output JSON schema")
    examples: List[Dict[str, Any]] = Field(
        default_factory=list, description="Usage examples"
    )
    return_direct: bool = Field(
        default=False, description="Whether to return result directly"
    )


class RegisteredTool(BaseModel):
    """A registered tool with metadata."""

    tool_id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    version: str = Field(default="1.0.0", description="Tool version")
    category: ToolCategory = Field(..., description="Tool category")
    status: ToolStatus = Field(default=ToolStatus.ACTIVE, description="Tool status")
    tool_instance: BaseTool = Field(..., description="Tool instance")
    metadata: ToolMetadata = Field(..., description="Tool metadata")
    schema: Optional[ToolSchema] = Field(None, description="Tool schema")
    usage_count: int = Field(default=0, description="Number of times used")
    last_used_at: Optional[str] = Field(None, description="Last usage timestamp")


class ToolFilter(BaseModel):
    """Filter criteria for searching tools."""

    categories: Optional[List[ToolCategory]] = Field(None, description="Category filter")
    statuses: Optional[List[ToolStatus]] = Field(None, description="Status filter")
    tags: Optional[List[str]] = Field(None, description="Tag filter")
    name_contains: Optional[str] = Field(None, description="Name contains filter")
    description_contains: Optional[str] = Field(None, description="Description contains filter")
    has_permission: Optional[str] = Field(None, description="Permission filter")


class ToolRegistry:
    """
    Centralized tool registry for LangGraph agents.

    Features:
    - Automatic tool registration via decorators
    - Tool discovery and filtering
    - Version management
    - Usage statistics
    - Tool compatibility checks
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, RegisteredTool] = {}
        self._tool_names: Dict[str, str] = {}  # name -> tool_id
        self._initialized = False

    def register_tool(
        self,
        tool_instance: BaseTool,
        name: str = None,
        description: str = None,
        version: str = "1.0.0",
        category: ToolCategory = ToolCategory.UTILITY,
        status: ToolStatus = ToolStatus.ACTIVE,
        author: str = None,
        tags: List[str] = None,
        permissions: List[str] = None,
        rate_limit: Dict[str, int] = None,
    ) -> str:
        """
        Register a tool instance.

        Args:
            tool_instance: LangChain BaseTool instance
            name: Tool name (defaults to instance name)
            description: Tool description (defaults to instance description)
            version: Tool version
            category: Tool category
            status: Tool status
            author: Tool author
            tags: Tool tags
            permissions: Required permissions
            rate_limit: Rate limits

        Returns:
            tool_id of registered tool
        """
        tool_id = str(uuid4())
        tool_name = name or tool_instance.name
        tool_description = description or tool_instance.description

        # Create metadata
        metadata = ToolMetadata(
            tool_id=tool_id,
            name=tool_name,
            description=tool_description,
            version=version,
            category=category,
            status=status,
            author=author,
            tags=tags or [],
            permissions=permissions or [],
            rate_limit=rate_limit,
        )

        # Create registered tool
        registered_tool = RegisteredTool(
            tool_id=tool_id,
            name=tool_name,
            description=tool_description,
            version=version,
            category=category,
            status=status,
            tool_instance=tool_instance,
            metadata=metadata,
        )

        # Store
        self._tools[tool_id] = registered_tool
        self._tool_names[tool_name] = tool_id

        return tool_id

    def register_decorator(
        self,
        name: str = None,
        description: str = None,
        version: str = "1.0.0",
        category: ToolCategory = ToolCategory.UTILITY,
        status: ToolStatus = ToolStatus.ACTIVE,
        author: str = None,
        tags: List[str] = None,
        permissions: List[str] = None,
        rate_limit: Dict[str, int] = None,
    ):
        """
        Decorator for registering tools.

        Usage:
            @registry.register_decorator(
                name="my_tool",
                category=ToolCategory.DATABASE,
            )
            class MyTool(BaseTool):
                ...
        """
        def decorator(tool_class):
            # Create instance
            if hasattr(tool_class, '_cls_instance'):
                tool_instance = tool_class._cls_instance
            else:
                tool_instance = tool_class()

            # Register
            self.register_tool(
                tool_instance=tool_instance,
                name=name,
                description=description,
                version=version,
                category=category,
                status=status,
                author=author,
                tags=tags,
                permissions=permissions,
                rate_limit=rate_limit,
            )

            return tool_class

        return decorator

    def get_tool(self, tool_id: str) -> Optional[RegisteredTool]:
        """
        Get a tool by ID.

        Args:
            tool_id: Tool identifier

        Returns:
            RegisteredTool or None
        """
        return self._tools.get(tool_id)

    def get_tool_by_name(self, name: str) -> Optional[RegisteredTool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            RegisteredTool or None
        """
        tool_id = self._tool_names.get(name)
        if tool_id:
            return self._tools.get(tool_id)
        return None

    def list_tools(
        self, filter_criteria: ToolFilter = None
    ) -> List[RegisteredTool]:
        """
        List all registered tools with optional filtering.

        Args:
            filter_criteria: Optional filter criteria

        Returns:
            List of registered tools
        """
        tools = list(self._tools.values())

        if not filter_criteria:
            return tools

        filtered = []
        for tool in tools:
            # Category filter
            if (
                filter_criteria.categories
                and tool.category not in filter_criteria.categories
            ):
                continue

            # Status filter
            if filter_criteria.statuses and tool.status not in filter_criteria.statuses:
                continue

            # Tag filter
            if filter_criteria.tags:
                if not any(tag in tool.metadata.tags for tag in filter_criteria.tags):
                    continue

            # Name contains filter
            if (
                filter_criteria.name_contains
                and filter_criteria.name_contains.lower() not in tool.name.lower()
            ):
                continue

            # Description contains filter
            if (
                filter_criteria.description_contains
                and filter_criteria.description_contains.lower()
                not in tool.description.lower()
            ):
                continue

            # Permission filter
            if filter_criteria.has_permission:
                if filter_criteria.has_permission not in tool.metadata.permissions:
                    continue

            filtered.append(tool)

        return filtered

    def list_tool_instances(self, filter_criteria: ToolFilter = None) -> List[BaseTool]:
        """
        List tool instances for LangGraph.

        Args:
            filter_criteria: Optional filter criteria

        Returns:
            List of BaseTool instances
        """
        tools = self.list_tools(filter_criteria)
        return [tool.tool_instance for tool in tools if tool.status == ToolStatus.ACTIVE]

    def get_tools_by_category(self, category: ToolCategory) -> List[RegisteredTool]:
        """
        Get all tools in a category.

        Args:
            category: Tool category

        Returns:
            List of registered tools
        """
        return [
            tool
            for tool in self._tools.values()
            if tool.category == category and tool.status == ToolStatus.ACTIVE
        ]

    def get_tools_by_tag(self, tag: str) -> List[RegisteredTool]:
        """
        Get all tools with a specific tag.

        Args:
            tag: Tag to search for

        Returns:
            List of registered tools
        """
        return [
            tool
            for tool in self._tools.values()
            if tag in tool.metadata.tags
        ]

    def search_tools(self, query: str) -> List[RegisteredTool]:
        """
        Search tools by name and description.

        Args:
            query: Search query

        Returns:
            List of matching tools
        """
        query = query.lower()
        return [
            tool
            for tool in self._tools.values()
            if query in tool.name.lower() or query in tool.description.lower()
        ]
        query = query.lower()
        return [
            tool
            for tool in self._tools.values()
            if query in tool.name.lower() or query in tool.description.lower()
        ]

    def update_tool_status(
        self, tool_id: str, status: ToolStatus
    ) -> Optional[RegisteredTool]:
        """
        Update tool status.

        Args:
            tool_id: Tool identifier
            status: New status

        Returns:
            Updated RegisteredTool or None
        """
        tool = self._tools.get(tool_id)
        if tool:
            tool.status = status
            tool.metadata.status = status
            tool.metadata.updated_at = datetime.utcnow().isoformat()
        return tool

    def increment_usage(self, tool_id: str) -> Optional[RegisteredTool]:
        """
        Increment tool usage counter.

        Args:
            tool_id: Tool identifier

        Returns:
            Updated RegisteredTool or None
        """
        tool = self._tools.get(tool_id)
        if tool:
            tool.usage_count += 1
            tool.last_used_at = datetime.utcnow().isoformat()
        return tool

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with statistics
        """
        tools = list(self._tools.values())

        # Count by category
        by_category = {}
        for category in ToolCategory:
            count = sum(1 for t in tools if t.category == category)
            if count > 0:
                by_category[category.value] = count

        # Count by status
        by_status = {}
        for status in ToolStatus:
            count = sum(1 for t in tools if t.status == status)
            if count > 0:
                by_status[status.value] = count

        # Total usage
        total_usage = sum(t.usage_count for t in tools)

        return {
            "total_tools": len(tools),
            "active_tools": sum(1 for t in tools if t.status == ToolStatus.ACTIVE),
            "by_category": by_category,
            "by_status": by_status,
            "total_usage": total_usage,
        }

    def remove_tool(self, tool_id: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            tool_id: Tool identifier

        Returns:
            True if removed, False otherwise
        """
        tool = self._tools.pop(tool_id, None)
        if tool:
            self._tool_names.pop(tool.name, None)
            return True
        return False

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._tool_names.clear()


# Convenience functions and decorators
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(
    tool_instance: BaseTool,
    name: str = None,
    description: str = None,
    version: str = "1.0.0",
    category: ToolCategory = ToolCategory.UTILITY,
    status: ToolStatus = ToolStatus.ACTIVE,
    author: str = None,
    tags: List[str] = None,
    permissions: List[str] = None,
    rate_limit: Dict[str, int] = None,
) -> str:
    """
    Register a tool in the global registry.

    Args:
        tool_instance: LangChain BaseTool instance
        name: Tool name
        description: Tool description
        version: Tool version
        category: Tool category
        status: Tool status
        author: Tool author
        tags: Tool tags
        permissions: Required permissions
        rate_limit: Rate limits

    Returns:
        tool_id of registered tool
    """
    return get_registry().register_tool(
        tool_instance=tool_instance,
        name=name,
        description=description,
        version=version,
        category=category,
        status=status,
        author=author,
        tags=tags,
        permissions=permissions,
        rate_limit=rate_limit,
    )


def register_decorator(
    name: str = None,
    description: str = None,
    version: str = "1.0.0",
    category: ToolCategory = ToolCategory.UTILITY,
    status: ToolStatus = ToolStatus.ACTIVE,
    author: str = None,
    tags: List[str] = None,
    permissions: List[str] = None,
    rate_limit: Dict[str, int] = None,
):
    """
    Decorator for registering tools in the global registry.

    Usage:
        @register_decorator(
            name="my_tool",
            category=ToolCategory.DATABASE,
        )
        class MyTool(BaseTool):
            ...
    """
    return get_registry().register_decorator(
        name=name,
        description=description,
        version=version,
        category=category,
        status=status,
        author=author,
        tags=tags,
        permissions=permissions,
        rate_limit=rate_limit,
    )


def list_tools(filter_criteria: ToolFilter = None) -> List[RegisteredTool]:
    """List all registered tools."""
    return get_registry().list_tools(filter_criteria)


def list_tool_instances(filter_criteria: ToolFilter = None) -> List[BaseTool]:
    """List all active tool instances for LangGraph."""
    return get_registry().list_tool_instances(filter_criteria)


def get_tool(tool_id: str) -> Optional[RegisteredTool]:
    """Get a tool by ID."""
    return get_registry().get_tool(tool_id)


def get_tool_by_name(name: str) -> Optional[RegisteredTool]:
    """Get a tool by name."""
    return get_registry().get_tool_by_name(name)


def search_tools(query: str) -> List[RegisteredTool]:
    """Search tools by query."""
    return get_registry().search_tools(query)


def auto_register_tools(module) -> int:
    """
    Auto-register all decorated tools from a module.

    Args:
        module: Python module to scan

    Returns:
        Number of tools registered
    """
    count = 0
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, BaseTool):
            # Check if it has _registered class attribute
            if getattr(attr, "_registered", False):
                try:
                    register_tool(
                        tool_instance=attr(),
                        name=getattr(attr, "_name", None),
                        description=getattr(attr, "_description", None),
                        version=getattr(attr, "_version", "1.0.0"),
                        category=getattr(attr, "_category", ToolCategory.UTILITY),
                        status=getattr(attr, "_status", ToolStatus.ACTIVE),
                        author=getattr(attr, "_author", None),
                        tags=getattr(attr, "_tags", []),
                        permissions=getattr(attr, "_permissions", []),
                    )
                    count += 1
                except Exception:
                    pass
    return count
