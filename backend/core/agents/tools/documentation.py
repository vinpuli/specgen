"""
Tool Documentation and Description Generation for LangGraph agents.

Provides comprehensive tool documentation:
- Tool description generation
- Parameter documentation
- Usage examples
- Markdown/HTML documentation output
- OpenAPI-style tool specifications
- README generation for tool collections
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union
from uuid import UUID


class DocFormat(str, Enum):
    """Documentation output formats."""

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    OPENAPI = "openapi"
    RST = "rst"


class ParamStyle(str, Enum):
    """Parameter style for documentation."""

    REST = "rest"  # /users/{id}
    GRPC = "grpc"  # --user-id value
    JSON = "json"  # {"userId": "value"}
    CLI = "cli"  # --user-id value


class ToolStatus(str, Enum):
    """Tool status for documentation."""

    STABLE = "stable"
    BETA = "beta"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


@dataclass
class ParameterDoc:
    """Documentation for a tool parameter."""

    name: str
    param_type: str
    description: str
    required: bool = False
    default: Any = None
    enum_values: Optional[List[str]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    example: Any = None
    deprecated: bool = False
    secret: bool = False  # Sensitive parameter (passwords, tokens)


@dataclass
class ExampleDoc:
    """Documentation example for a tool."""

    title: str
    description: str
    request: Dict[str, Any]
    response: Dict[str, Any]
    notes: Optional[str] = None


@dataclass
class SeeAlsoDoc:
    """Related tool or resource reference."""

    tool_name: str
    relationship: str  # "related", "see also", "requires", "required by"
    description: Optional[str] = None


@dataclass
class ToolDoc:
    """
    Complete documentation for a tool.

    Provides comprehensive documentation including:
    - Description and purpose
    - Parameters with full documentation
    - Return values
    - Usage examples
    - Error handling
    - Related tools
    """

    tool_name: str
    display_name: str
    category: str
    description: str
    long_description: Optional[str] = None
    version: str = "1.0.0"
    status: ToolStatus = ToolStatus.STABLE
    author: Optional[str] = None
    parameters: List[ParameterDoc] = field(default_factory=list)
    returns: Optional[Dict[str, Any]] = None
    examples: List[ExampleDoc] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    see_also: List[SeeAlsoDoc] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def get_param_by_name(self, name: str) -> Optional[ParameterDoc]:
        """Get parameter by name."""
        for param in self.parameters:
            if param.name == name:
                return param
        return None

    def get_required_params(self) -> List[ParameterDoc]:
        """Get all required parameters."""
        return [p for p in self.parameters if p.required]

    def get_optional_params(self) -> List[ParameterDoc]:
        """Get all optional parameters."""
        return [p for p in self.parameters if not p.required]


class ToolDocumentationGenerator:
    """
    Generate comprehensive documentation for tools.

    Features:
    - Markdown documentation generation
    - OpenAPI specification generation
    - JSON documentation output
    - HTML documentation generation
    - README generation for tool collections
    - Parameter table generation
    - Example code generation
    """

    def __init__(self):
        """Initialize the documentation generator."""
        self._tool_docs: Dict[str, ToolDoc] = {}

    def register_tool_doc(self, doc: ToolDoc) -> None:
        """
        Register tool documentation.

        Args:
            doc: Tool documentation to register
        """
        self._tool_docs[doc.tool_name] = doc

    def generate_markdown(
        self,
        tool_name: Optional[str] = None,
        include_examples: bool = True,
        include_errors: bool = True,
    ) -> str:
        """
        Generate Markdown documentation for one or all tools.

        Args:
            tool_name: Specific tool to document (None for all)
            include_examples: Include usage examples
            include_errors: Include error documentation

        Returns:
            Markdown formatted documentation
        """
        if tool_name:
            return self._generate_tool_markdown(
                self._tool_docs[tool_name],
                include_examples,
                include_errors,
            )

        docs = []
        # Group by category
        categories: Dict[str, List[ToolDoc]] = {}
        for doc in self._tool_docs.values():
            if doc.category not in categories:
                categories[doc.category] = []
            categories[doc.category].append(doc)

        for category, tools in sorted(categories.items()):
            docs.append(f"## {category}\n")
            for tool in tools:
                docs.append(
                    self._generate_tool_markdown(
                        tool, include_examples, include_errors
                    )
                )
                docs.append("\n---\n")

        return "\n".join(docs)

    def _generate_tool_markdown(
        self,
        doc: ToolDoc,
        include_examples: bool = True,
        include_errors: bool = True,
    ) -> str:
        """Generate Markdown for a single tool."""
        lines = []

        # Header
        lines.append(f"# {doc.display_name}\n")
        lines.append(f"`{doc.tool_name}`\n")
        lines.append(f"\n**Category:** {doc.category}\n")
        lines.append(f"**Version:** {doc.version}\n")
        lines.append(f"**Status:** {self._get_status_badge(doc.status)}\n")

        if doc.author:
            lines.append(f"**Author:** {doc.author}\n")

        # Description
        lines.append(f"\n## Description\n\n{doc.description}\n")

        if doc.long_description:
            lines.append(f"\n{doc.long_description}\n")

        # Tags
        if doc.tags:
            lines.append(f"\n**Tags:** {' '.join(f'`{tag}`' for tag in doc.tags)}\n")

        # Parameters
        if doc.parameters:
            lines.append("\n## Parameters\n\n")
            lines.append("| Name | Type | Required | Description |\n")
            lines.append("|------|------|----------|-------------|\n")
            for param in doc.parameters:
                required = "Yes" if param.required else "No"
                param_type = self._format_type(param.param_type)
                desc = param.description.replace("\n", " ")
                lines.append(
                    f"| `{param.name}` | {param_type} | {required} | {desc} |\n"
                )

            # Detailed parameter docs
            for param in doc.parameters:
                lines.append(f"\n### `{param.name}`\n")
                lines.append(f"**Type:** `{param.param_type}`\n")
                lines.append(f"**Required:** {'Yes' if param.required else 'No'}\n")
                if param.default is not None:
                    lines.append(f"**Default:** `{param.default}`\n")
                if param.enum_values:
                    lines.append(
                        f"**Allowed Values:** `{'`, `'.join(param.enum_values)}`\n"
                    )
                if param.min_value is not None:
                    lines.append(f"**Minimum:** {param.min_value}\n")
                if param.max_value is not None:
                    lines.append(f"**Maximum:** {param.max_value}\n")
                if param.min_length is not None:
                    lines.append(f"**Min Length:** {param.min_length}\n")
                if param.max_length is not None:
                    lines.append(f"**Max Length:** {param.max_length}\n")
                if param.pattern:
                    lines.append(f"**Pattern:** `{param.pattern}`\n")
                if param.example:
                    lines.append(f"**Example:** `{param.example}`\n")
                lines.append(f"\n{param.description}\n")

        # Returns
        if doc.returns:
            lines.append("\n## Returns\n\n")
            if "type" in doc.returns:
                lines.append(f"**Type:** `{doc.returns['type']}`\n\n")
            if "description" in doc.returns:
                lines.append(f"{doc.returns['description']}\n")
            if "properties" in doc.returns:
                lines.append("\n| Property | Type | Description |\n")
                lines.append("|----------|------|-------------|\n")
                for prop, details in doc.returns["properties"].items():
                    prop_type = details.get("type", "any")
                    prop_desc = details.get("description", "")
                    lines.append(f"| `{prop}` | `{prop_type}` | {prop_desc} |\n")

        # Examples
        if include_examples and doc.examples:
            lines.append("\n## Examples\n\n")
            for i, example in enumerate(doc.examples, 1):
                lines.append(f"### Example {i}: {example.title}\n")
                lines.append(f"\n{example.description}\n")
                lines.append("\n**Request:**\n")
                lines.append(f"\n```json\n{json.dumps(example.request, indent=2)}\n```\n")
                lines.append("\n**Response:**\n")
                lines.append(f"\n```json\n{json.dumps(example.response, indent=2)}\n```\n")
                if example.notes:
                    lines.append(f"\n**Notes:** {example.notes}\n")
                lines.append("\n")

        # Errors
        if include_errors and doc.errors:
            lines.append("\n## Errors\n\n")
            lines.append("| Error Code | Description |\n")
            lines.append("|------------|-------------|\n")
            for error in doc.errors:
                code = error.get("code", "UNKNOWN")
                msg = error.get("message", "")
                lines.append(f"| `{code}` | {msg} |\n")

        # See Also
        if doc.see_also:
            lines.append("\n## See Also\n\n")
            for ref in doc.see_also:
                lines.append(f"- [{ref.tool_name}]({ref.tool_name}.md)")
                if ref.relationship:
                    lines.append(f" ({ref.relationship})")
                if ref.description:
                    lines.append(f" - {ref.description}")
                lines.append("\n")

        # Metadata
        lines.append("\n---\n")
        lines.append(f"\n*Last Updated: {doc.updated_at}*\n")

        return "\n".join(lines)

    def _get_status_badge(self, status: ToolStatus) -> str:
        """Get status badge for Markdown."""
        badges = {
            ToolStatus.STABLE: "🟢 Stable",
            ToolStatus.BETA: "🟡 Beta",
            ToolStatus.DEPRECATED: "🔴 Deprecated",
            ToolStatus.EXPERIMENTAL: "⚪ Experimental",
        }
        return badges.get(status, "⚪ Unknown")

    def _format_type(self, param_type: str) -> str:
        """Format parameter type for display."""
        # Handle union types
        if "Union" in param_type:
            return param_type.replace("Union[", "").replace("]", "").replace(", None", " (nullable)")
        return param_type

    def generate_openapi(
        self,
        title: str = "Tool API",
        version: str = "1.0.0",
        base_url: str = "/api/v1",
    ) -> Dict[str, Any]:
        """
        Generate OpenAPI specification for tools.

        Args:
            title: API title
            version: API version
            base_url: Base URL for endpoints

        Returns:
            OpenAPI specification dictionary
        """
        paths: Dict[str, Any] = {}

        for tool_name, doc in self._tool_docs.items():
            endpoint = f"{base_url}/{tool_name.replace('_', '-')}"

            # Convert snake_case to kebab-case for OpenAPI
            paths[endpoint] = {
                "post": {
                    "summary": doc.display_name,
                    "description": doc.description,
                    "operationId": f"execute_{tool_name}",
                    "tags": [doc.category],
                    "deprecated": doc.status == ToolStatus.DEPRECATED,
                    "parameters": [],
                    "requestBody": {
                        "required": len(doc.get_required_params()) > 0,
                        "content": {
                            "application/json": {
                                "schema": self._generate_openapi_schema(doc)
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": doc.returns or {"type": "object"}
                                }
                            },
                        },
                        "400": {"description": "Invalid request"},
                        "500": {"description": "Internal error"},
                    },
                }
            }

        return {
            "openapi": "3.0.0",
            "info": {
                "title": title,
                "version": version,
                "description": doc.long_description or doc.description,
            },
            "paths": paths,
        }

    def _generate_openapi_schema(self, doc: ToolDoc) -> Dict[str, Any]:
        """Generate OpenAPI schema from tool doc."""
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in doc.parameters:
            prop_schema: Dict[str, Any] = {
                "description": param.description,
            }

            # Type mapping
            type_map = {
                "str": "string",
                "int": "integer",
                "float": "number",
                "bool": "boolean",
                "list": "array",
                "dict": "object",
            }
            prop_schema["type"] = type_map.get(param.param_type, param.param_type)

            if param.enum_values:
                prop_schema["enum"] = param.enum_values
            if param.default is not None:
                prop_schema["default"] = param.default
            if param.min_value is not None:
                if prop_schema["type"] == "integer":
                    prop_schema["minimum"] = param.min_value
                else:
                    prop_schema["minimum"] = param.min_value
            if param.max_value is not None:
                if prop_schema["type"] == "integer":
                    prop_schema["maximum"] = param.max_value
                else:
                    prop_schema["maximum"] = param.max_value
            if param.min_length is not None:
                prop_schema["minLength"] = param.min_length
            if param.max_length is not None:
                prop_schema["maxLength"] = param.max_length
            if param.pattern:
                prop_schema["pattern"] = param.pattern

            properties[param.name] = prop_schema
            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def generate_json(self, tool_name: Optional[str] = None) -> str:
        """
        Generate JSON documentation.

        Args:
            tool_name: Specific tool to document (None for all)

        Returns:
            JSON formatted documentation
        """
        if tool_name:
            return json.dumps(asdict(self._tool_docs[tool_name]), indent=2)

        docs = {
            "tools": {
                name: asdict(doc)
                for name, doc in self._tool_docs.items()
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
        return json.dumps(docs, indent=2)

    def generate_readme(
        self,
        project_name: str,
        description: str,
        version: str = "1.0.0",
        package_name: str = None,
    ) -> str:
        """
        Generate README.md for tool collection.

        Args:
            project_name: Name of the tool collection
            description: Project description
            version: Version number
            package_name: Package name for pip install command

        Returns:
            README.md content
        """
        pkg_name = package_name or project_name.lower().replace(" ", "-")
        lines = []

        lines.append(f"# {project_name}\n")
        lines.append(f"\n![Version](https://img.shields.io/badge/version-{version}-blue.svg)\n")
        lines.append(f"\n## Description\n\n{description}\n")

        # Installation
        lines.append("\n## Installation\n\n")
        lines.append(f"```bash\npip install {pkg_name}\n```\n")

        # Quick Start
        lines.append("\n## Quick Start\n\n")
        lines.append("```python\nfrom tools import *\n\n# Initialize tools\n# ...\n```\n")

        # Available Tools
        lines.append("\n## Available Tools\n\n")

        categories: Dict[str, List[ToolDoc]] = {}
        for doc in self._tool_docs.values():
            if doc.category not in categories:
                categories[doc.category] = []
            categories[doc.category].append(doc)

        for category, tools in sorted(categories.items()):
            lines.append(f"### {category}\n\n")
            lines.append("| Tool | Description |\n")
            lines.append("|------|-------------|\n")
            for tool in tools:
                lines.append(
                    f"| [`{tool.display_name}`](docs/{tool.tool_name}.md) | {tool.description[:80]} |\n"
                )
            lines.append("\n")

        # Documentation
        lines.append("\n## Documentation\n\n")
        lines.append("See the [docs](docs/) directory for detailed documentation.\n")

        # Contributing
        lines.append("\n## Contributing\n\n")
        lines.append("Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.\n")

        # License
        lines.append("\n## License\n\n")
        lines.append("This project is licensed under the MIT License.\n")

        return "\n".join(lines)


class AutoDocumenter:
    """
    Automatically generate documentation from tool classes.

    Analyzes tool classes and generates comprehensive documentation.
    """

    def __init__(self):
        """Initialize the auto documenter."""
        self._generator = ToolDocumentationGenerator()

    def document_from_class(
        self,
        tool_class: Type,
        tool_name: Optional[str] = None,
        category: str = "General",
    ) -> ToolDoc:
        """
        Generate documentation from a tool class.

        Args:
            tool_class: Tool class to document
            tool_name: Override tool name
            category: Tool category

        Returns:
            Generated ToolDoc
        """
        tool_name = tool_name or tool_class.__name__

        # Extract docstring
        description = tool_class.__doc__ or ""
        if description:
            # Get first paragraph as summary
            paragraphs = description.strip().split("\n\n")
            summary = paragraphs[0] if paragraphs else ""
            long_description = "\n\n".join(paragraphs[1:]) if len(paragraphs) > 1 else None
        else:
            summary = f"Tool: {tool_name}"
            long_description = None

        # Create tool doc
        doc = ToolDoc(
            tool_name=tool_name,
            display_name=tool_name.replace("_", " ").title(),
            category=category,
            description=summary,
            long_description=long_description,
        )

        # Extract parameters from __init__ signature
        import inspect

        sig = inspect.signature(tool_class.__init__)
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Determine if required
            required = param.default == inspect.Parameter.empty

            # Get type
            param_type = param.annotation.__name__ if param.annotation else "any"

            # Get description from docstring
            param_desc = f"Parameter: {param_name}"

            parameter_doc = ParameterDoc(
                name=param_name,
                param_type=param_type,
                description=param_desc,
                required=required,
                default=param.default if param.default != inspect.Parameter.empty else None,
            )
            doc.parameters.append(parameter_doc)

        return doc


# Convenience functions
def create_documentation_generator() -> ToolDocumentationGenerator:
    """Create a new documentation generator."""
    return ToolDocumentationGenerator()


def create_auto_documenter() -> AutoDocumenter:
    """Create a new auto documenter."""
    return AutoDocumenter()


# Example usage
def generate_database_tools_docs() -> str:
    """Generate documentation for database tools."""
    generator = ToolDocumentationGenerator()

    # Document GetUserTool
    get_user_doc = ToolDoc(
        tool_name="get_user",
        display_name="Get User",
        category="Database",
        description="Retrieve a user by their ID.",
        long_description="This tool fetches user information from the database using the user's unique identifier. Returns None if the user is not found.",
        version="1.0.0",
        status=ToolStatus.STABLE,
        parameters=[
            ParameterDoc(
                name="user_id",
                param_type="str",
                description="The unique identifier of the user to retrieve",
                required=True,
                example="usr_1234567890",
            )
        ],
        returns={
            "type": "object",
            "description": "User object containing id, email, name, and created_at fields",
            "properties": {
                "id": {"type": "string", "description": "User ID"},
                "email": {"type": "string", "description": "User email"},
                "name": {"type": "string", "description": "User name"},
                "created_at": {"type": "string", "description": "Creation timestamp"},
            },
        },
        examples=[
            ExampleDoc(
                title="Get existing user",
                description="Retrieve a user that exists in the database",
                request={"user_id": "usr_1234567890"},
                response={
                    "id": "usr_1234567890",
                    "email": "user@example.com",
                    "name": "John Doe",
                    "created_at": "2024-01-15T10:30:00Z",
                },
            )
        ],
        errors=[
            {"code": "NOT_FOUND", "message": "User with given ID does not exist"},
            {"code": "INVALID_ID", "message": "Invalid user ID format"},
        ],
        see_also=[
            SeeAlsoDoc(tool_name="update_user", relationship="see also", description="Update user information")
        ],
        tags=["user", "database", "read"],
    )
    generator.register_tool_doc(get_user_doc)

    return generator.generate_markdown()


def generate_vector_tools_docs() -> str:
    """Generate documentation for vector store tools."""
    generator = ToolDocumentationGenerator()

    search_decisions_doc = ToolDoc(
        tool_name="search_decisions",
        display_name="Search Decisions",
        category="Vector Store",
        description="Search for decisions using semantic similarity.",
        long_description="This tool uses vector embeddings to find semantically similar decisions. It searches through the decision database using cosine similarity.",
        version="1.0.0",
        status=ToolStatus.STABLE,
        parameters=[
            ParameterDoc(
                name="query",
                param_type="str",
                description="The search query text",
                required=True,
                example="authentication and authorization patterns",
            ),
            ParameterDoc(
                name="limit",
                param_type="int",
                description="Maximum number of results to return",
                required=False,
                default=10,
                min_value=1,
                max_value=100,
                example=5,
            ),
            ParameterDoc(
                name="threshold",
                param_type="float",
                description="Minimum similarity score (0-1)",
                required=False,
                default=0.7,
                min_value=0.0,
                max_value=1.0,
                example=0.8,
            ),
        ],
        returns={
            "type": "array",
            "description": "List of matching decisions with scores",
        },
    )
    generator.register_tool_doc(search_decisions_doc)

    return generator.generate_markdown()
