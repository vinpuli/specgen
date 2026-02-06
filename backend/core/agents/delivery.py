"""
Delivery Agent for LangGraph.

This module implements the DeliveryAgent as a LangGraph StateGraph
that manages artifact export and delivery in multiple formats.
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from uuid import uuid4
import json
import yaml

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import CheckpointSaver
from langgraph.constants import Send

from .types import (
    AgentType,
    Artifact,
    ArtifactFormat,
    DeliveryAgentState,
)
from .state import create_delivery_state
from ..llm import get_llm_client


# ==================== Node Names ====================

class DeliveryNode:
    """Node names for the Delivery Agent."""
    START = "start"
    EXPORT_MARKDOWN = "export_markdown"
    EXPORT_JSON_YAML = "export_json_yaml"
    EXPORT_OPENAPI = "export_openapi"
    EXPORT_GITHUB_ISSUES = "export_github_issues"
    EXPORT_CURSOR_AI = "export_cursor_ai"
    EXPORT_CLAUDE_CODE = "export_claude_code"
    STORE_ARTIFACT = "store_artifact"
    END = "end"


# ==================== Delivery Agent ====================

class DeliveryAgent:
    """
    Delivery Agent for artifact export and delivery.
    
    This agent manages:
    1. Exporting artifacts in various formats
    2. Storing artifacts
    3. Delivering to various destinations
    """
    
    def __init__(
        self,
        checkpoint_saver: Optional[CheckpointSaver] = None,
        on_export: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize the Delivery Agent.
        
        Args:
            checkpoint_saver: Checkpoint saver for state persistence
            on_export: Callback when export is complete
        """
        self.checkpoint_saver = checkpoint_saver
        self.on_export = on_export
        self.llm = get_llm_client()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph for the Delivery Agent."""
        builder = StateGraph(
            DeliveryAgentState,
            config_schema={
                "project_id": str,
                "thread_id": str,
            },
        )
        
        # Add nodes
        builder.add_node(DeliveryNode.START, self._start_node)
        builder.add_node(DeliveryNode.EXPORT_MARKDOWN, self._export_markdown_node)
        builder.add_node(DeliveryNode.EXPORT_JSON_YAML, self._export_json_yaml_node)
        builder.add_node(DeliveryNode.EXPORT_OPENAPI, self._export_openapi_node)
        builder.add_node(DeliveryNode.EXPORT_GITHUB_ISSUES, self._export_github_issues_node)
        builder.add_node(DeliveryNode.EXPORT_CURSOR_AI, self._export_cursor_ai_node)
        builder.add_node(DeliveryNode.EXPORT_CLAUDE_CODE, self._export_claude_code_node)
        builder.add_node(DeliveryNode.STORE_ARTIFACT, self._store_artifact_node)
        builder.add_node(DeliveryNode.END, self._end_node)
        
        # Set entry point
        builder.set_entry_point(DeliveryNode.START)
        
        # Add edges - export format selection
        builder.add_conditional_edges(
            DeliveryNode.START,
            self._select_export_format,
            {
                "markdown": DeliveryNode.EXPORT_MARKDOWN,
                "json_yaml": DeliveryNode.EXPORT_JSON_YAML,
                "openapi": DeliveryNode.EXPORT_OPENAPI,
                "github_issues": DeliveryNode.EXPORT_GITHUB_ISSUES,
                "cursor_ai": DeliveryNode.EXPORT_CURSOR_AI,
                "claude_code": DeliveryNode.EXPORT_CLAUDE_CODE,
            },
        )
        
        # All exports go to store
        export_nodes = [
            DeliveryNode.EXPORT_MARKDOWN,
            DeliveryNode.EXPORT_JSON_YAML,
            DeliveryNode.EXPORT_OPENAPI,
            DeliveryNode.EXPORT_GITHUB_ISSUES,
            DeliveryNode.EXPORT_CURSOR_AI,
            DeliveryNode.EXPORT_CLAUDE_CODE,
        ]
        
        for node in export_nodes:
            builder.add_edge(node, DeliveryNode.STORE_ARTIFACT)
        
        builder.add_edge(DeliveryNode.STORE_ARTIFACT, DeliveryNode.END)
        
        # Add parallel export branch using Send API
        builder.add_conditional_edges(
            DeliveryNode.START,
            self._select_parallel_formats,
            {
                "parallel_markdown": DeliveryNode.EXPORT_MARKDOWN,
                "parallel_json_yaml": DeliveryNode.EXPORT_JSON_YAML,
                "parallel_openapi": DeliveryNode.EXPORT_OPENAPI,
                "parallel_github_issues": DeliveryNode.EXPORT_GITHUB_ISSUES,
                "parallel_cursor_ai": DeliveryNode.EXPORT_CURSOR_AI,
                "parallel_claude_code": DeliveryNode.EXPORT_CLAUDE_CODE,
            },
        )
        
        # All parallel exports go to store
        parallel_nodes = [
            DeliveryNode.EXPORT_MARKDOWN,
            DeliveryNode.EXPORT_JSON_YAML,
            DeliveryNode.EXPORT_OPENAPI,
            DeliveryNode.EXPORT_GITHUB_ISSUES,
            DeliveryNode.EXPORT_CURSOR_AI,
            DeliveryNode.EXPORT_CLAUDE_CODE,
        ]
        
        for node in parallel_nodes:
            builder.add_edge(node, DeliveryNode.STORE_ARTIFACT)
        
        # Compile with checkpoint saver
        if self.checkpoint_saver:
            builder.checkpointer = self.checkpoint_saver
        
        return builder.compile()
    
    async def _start_node(self, state: DeliveryAgentState) -> DeliveryAgentState:
        """Start the delivery process."""
        state["messages"] = state.get("messages", [])
        state["messages"].append({
            "role": "system",
            "content": "Starting delivery process.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Select export format(s)
        export_format = state.get("export_format", "markdown").lower()
        export_formats = state.get("export_formats", [])
        
        # If export_formats is provided, use it for parallel export
        if export_formats:
            state["export_mode"] = "parallel"
        else:
            state["export_mode"] = "single"
            state["export_formats"] = [export_format]
        
        state["export_status"] = "in_progress"
        
        return state
    
    async def _export_markdown_node(
        self,
        state: DeliveryAgentState,
    ) -> DeliveryAgentState:
        """Export artifacts as Markdown."""
        artifacts = state.get("artifacts", {})
        
        markdown_content = []
        
        for artifact_id, artifact in artifacts.items():
            content = getattr(artifact, "content", "")
            
            # Format as structured markdown
            formatted = f"""# {getattr(artifact, 'title', 'Artifact')}

**Type:** {getattr(artifact, 'type', 'unknown')}
**Format:** Markdown
**Version:** {getattr(artifact, 'version', 1)}

---

{content}

---
"""
            markdown_content.append(formatted)
        
        combined = "\n\n".join(markdown_content)
        
        state["exported_content"]["markdown"] = combined
        state["delivered_formats"].append(ArtifactFormat.MARKDOWN)
        
        # Notify callback
        if self.on_export:
            self.on_export("markdown", combined)
        
        return state
    
    async def _export_json_yaml_node(
        self,
        state: DeliveryAgentState,
    ) -> DeliveryAgentState:
        """Export artifacts as JSON/YAML."""
        artifacts = state.get("artifacts", {})
        
        export_data = {
            "project_id": state.get("project_id"),
            "exported_at": datetime.utcnow().isoformat(),
            "artifacts": [],
        }
        
        for artifact_id, artifact in artifacts.items():
            export_data["artifacts"].append({
                "artifact_id": artifact_id,
                "type": getattr(artifact, "type", ""),
                "title": getattr(artifact, "title", ""),
                "content": getattr(artifact, "content", ""),
                "format": getattr(artifact, "format", ""),
                "based_on_decisions": getattr(artifact, "based_on_decisions", []),
                "version": getattr(artifact, "version", 1),
            })
        
        # Export as JSON
        json_content = json.dumps(export_data, indent=2)
        state["exported_content"]["json"] = json_content
        
        # Export as YAML
        yaml_content = yaml.dump(export_data, default_flow_style=False)
        state["exported_content"]["yaml"] = yaml_content
        
        state["delivered_formats"].append(ArtifactFormat.JSON)
        state["delivered_formats"].append(ArtifactFormat.YAML)
        
        return state
    
    async def _export_openapi_node(
        self,
        state: DeliveryAgentState,
    ) -> DeliveryAgentState:
        """Export API specs as OpenAPI."""
        artifacts = state.get("artifacts", {})
        
        openapi_spec = {
            "openapi": "3.0.3",
            "info": {
                "title": "API Specification",
                "version": "1.0.0",
            },
            "servers": [
                {"url": "https://api.example.com/v1"},
            ],
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": {},
            },
        }
        
        for artifact_id, artifact in artifacts.items():
            artifact_type = getattr(artifact, "type", "")
            
            if artifact_type == "api_spec":
                content = getattr(artifact, "content", "")
                
                # Parse existing OpenAPI content
                try:
                    # Try to parse as JSON
                    existing = json.loads(content)
                    if "paths" in existing:
                        openapi_spec["paths"].update(existing["paths"])
                    if "components" in existing:
                        openapi_spec["components"].update(existing["components"])
                except json.JSONDecodeError:
                    # Content is raw, add as-is placeholder
                    pass
        
        state["exported_content"]["openapi_json"] = json.dumps(openapi_spec, indent=2)
        state["exported_content"]["openapi_yaml"] = yaml.dump(openapi_spec, default_flow_style=False)
        state["delivered_formats"].append(ArtifactFormat.OPENAPI)
        
        return state
    
    async def _export_github_issues_node(
        self,
        state: DeliveryAgentState,
    ) -> DeliveryAgentState:
        """Export tickets as GitHub Issues."""
        artifacts = state.get("artifacts", {})
        
        issues = []
        
        for artifact_id, artifact in artifacts.items():
            artifact_type = getattr(artifact, "type", "")
            
            if artifact_type in ["tickets", "user_stories"]:
                content = getattr(artifact, "content", "")
                
                # Parse ticket content and create issue format
                lines = content.split("\n")
                current_ticket = {"title": "", "body": "", "labels": []}
                
                for line in lines:
                    if line.startswith("# "):
                        if current_ticket["title"]:
                            issues.append(current_ticket)
                        current_ticket = {"title": line[2:], "body": "", "labels": []}
                    elif line.startswith("**"):
                        # Extract labels from bold text
                        if "priority" in line.lower():
                            current_ticket["labels"].append(line.strip("*"))
                    elif current_ticket["title"]:
                        current_ticket["body"] += line + "\n"
                
                if current_ticket["title"]:
                    issues.append(current_ticket)
        
        # Create markdown file with issue templates
        issue_markdown = "# GitHub Issues Export\n\n"
        
        for i, issue in enumerate(issues, 1):
            issue_markdown += f"## Issue {i}: {issue['title']}\n\n"
            issue_markdown += f"**Labels:** {', '.join(issue['labels']) if issue['labels'] else 'None'}\n\n"
            issue_markdown += f"**Body:**\n{issue['body']}\n\n"
            issue_markdown += "---\n\n"
        
        state["exported_content"]["github_issues"] = issue_markdown
        state["exported_content"]["github_issues_json"] = json.dumps(issues, indent=2)
        state["delivered_formats"].append(ArtifactFormat.MARKDOWN)
        
        return state
    
    async def _export_cursor_ai_node(
        self,
        state: DeliveryAgentState,
    ) -> DeliveryAgentState:
        """Export for Cursor AI with YAML frontmatter."""
        artifacts = state.get("artifacts", {})
        
        cursor_content = []
        
        for artifact_id, artifact in artifacts.items():
            content = getattr(artifact, "content", "")
            title = getattr(artifact, "title", "")
            artifact_type = getattr(artifact, "type", "")
            
            # Create frontmatter
            frontmatter = {
                "title": title,
                "type": artifact_type,
                "version": getattr(artifact, "version", 1),
                "created": datetime.utcnow().isoformat(),
                "tags": [artifact_type],
            }
            
            formatted = f"""---
{yaml.dump(frontmatter, default_flow_style=False)}---

# {title}

{content}
"""
            cursor_content.append(formatted)
        
        combined = "\n---\n\n".join(cursor_content)
        
        state["exported_content"]["cursor_ai"] = combined
        state["delivered_formats"].append(ArtifactFormat.MARKDOWN)
        
        return state
    
    async def _export_claude_code_node(
        self,
        state: DeliveryAgentState,
    ) -> DeliveryAgentState:
        """Export for Claude Code with instructions."""
        artifacts = state.get("artifacts", {})
        
        claude_instructions = {
            "project_context": "Agentic Spec Builder Project",
            "specifications": [],
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        for artifact_id, artifact in artifacts.items():
            claude_instructions["specifications"].append({
                "title": getattr(artifact, "title", ""),
                "type": getattr(artifact, "type", ""),
                "content": getattr(artifact, "content", ""),
            })
        
        # Create Claude-specific format with prompts
        claude_prompts = []
        
        for spec in claude_instructions["specifications"]:
            prompt = f"""# Specification: {spec['title']}

## Context
You are working on a project based on the following specification:

{spec['content']}

## Instructions
1. Review this specification carefully
2. Ask clarifying questions if anything is ambiguous
3. Proceed with implementation following best practices
4. Highlight any potential issues or edge cases

---
"""
            claude_prompts.append(prompt)
        
        combined_prompts = "\n".join(claude_prompts)
        
        state["exported_content"]["claude_code"] = combined_prompts
        state["exported_content"]["claude_code_json"] = json.dumps(claude_instructions, indent=2)
        state["delivered_formats"].append(ArtifactFormat.MARKDOWN)
        
        return state
    
    async def _store_artifact_node(
        self,
        state: DeliveryAgentState,
    ) -> DeliveryAgentState:
        """Store exported artifacts."""
        selected_ids = state.get("selected_artifact_ids", [])
        artifacts = state.get("artifacts", {})
        
        stored = []
        
        for artifact_id in selected_ids:
            artifact = artifacts.get(artifact_id)
            if not artifact:
                continue
            
            # Update artifact with exported versions
            if "versions" not in dir(artifact) or not hasattr(artifact, "versions"):
                continue
            
            versions = getattr(artifact, "versions", [])
            versions.append({
                "exported_at": datetime.utcnow().isoformat(),
                "formats": state.get("delivered_formats", []),
            })
            
            stored.append(artifact_id)
        
        state["export_status"] = "completed"
        
        return state
    
    async def _end_node(self, state: DeliveryAgentState) -> DeliveryAgentState:
        """End the delivery process."""
        formats = state.get("delivered_formats", [])
        
        state["messages"].append({
            "role": "system",
            "content": f"Delivery complete. Exported in {len(formats)} format(s): {', '.join(str(f) for f in formats)}.",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return state
    
    # ==================== Routing Functions ====================
    
    def _select_export_format(self, state: DeliveryAgentState) -> str:
        """Select export format based on configuration."""
        export_format = state.get("export_format", "markdown").lower()
        
        format_map = {
            "markdown": "markdown",
            "md": "markdown",
            "json": "json_yaml",
            "yaml": "json_yaml",
            "openapi": "openapi",
            "swagger": "openapi",
            "github": "github_issues",
            "github_issues": "github_issues",
            "cursor": "cursor_ai",
            "cursor_ai": "cursor_ai",
            "claude": "claude_code",
            "claude_code": "claude_code",
        }
        
        return format_map.get(export_format, "markdown")
    
    def _select_parallel_formats(self, state: DeliveryAgentState) -> List[Send]:
        """
        Select multiple formats for parallel export.
        
        Returns a list of Send objects for parallel execution.
        """
        formats = state.get("export_formats", ["markdown"])
        
        send_list = []
        
        for fmt in formats:
            fmt_lower = fmt.lower()
            
            if fmt_lower in ["markdown", "md"]:
                send_list.append(Send(DeliveryNode.EXPORT_MARKDOWN, state.copy()))
            elif fmt_lower in ["json", "yaml"]:
                send_list.append(Send(DeliveryNode.EXPORT_JSON_YAML, state.copy()))
            elif fmt_lower in ["openapi", "swagger"]:
                send_list.append(Send(DeliveryNode.EXPORT_OPENAPI, state.copy()))
            elif fmt_lower in ["github", "github_issues"]:
                send_list.append(Send(DeliveryNode.EXPORT_GITHUB_ISSUES, state.copy()))
            elif fmt_lower in ["cursor", "cursor_ai"]:
                send_list.append(Send(DeliveryNode.EXPORT_CURSOR_AI, state.copy()))
            elif fmt_lower in ["claude", "claude_code"]:
                send_list.append(Send(DeliveryNode.EXPORT_CLAUDE_CODE, state.copy()))
        
        # Default to markdown if no formats specified
        if not send_list:
            send_list.append(Send(DeliveryNode.EXPORT_MARKDOWN, state.copy()))
        
        return send_list
    
    # ==================== Public Interface ====================
    
    async def export(
        self,
        project_id: str,
        artifacts: List[Artifact],
        export_format: str = "markdown",
        thread_id: Optional[str] = None,
    ) -> DeliveryAgentState:
        """
        Export artifacts in specified format.
        
        Args:
            project_id: Project identifier
            artifacts: List of artifacts to export
            export_format: Format to export as
            thread_id: Thread identifier
        
        Returns:
            Delivery state with exported content
        """
        state = create_delivery_state(project_id, thread_id)
        state["artifacts"] = {a.artifact_id: a for a in artifacts}
        state["export_format"] = export_format
        state["selected_artifact_ids"] = [a.artifact_id for a in artifacts]
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def export_all_formats(
        self,
        project_id: str,
        artifacts: List[Artifact],
        thread_id: Optional[str] = None,
    ) -> DeliveryAgentState:
        """
        Export artifacts in all supported formats in parallel.
        
        Args:
            project_id: Project identifier
            artifacts: List of artifacts
            thread_id: Thread identifier
        
        Returns:
            Delivery state with all exported content
        """
        state = create_delivery_state(project_id, thread_id)
        state["artifacts"] = {a.artifact_id: a for a in artifacts}
        state["export_formats"] = [
            "markdown", "json_yaml", "openapi", "github_issues", "cursor_ai", "claude_code"
        ]
        state["export_mode"] = "parallel"
        state["selected_artifact_ids"] = [a.artifact_id for a in artifacts]
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def export_all_formats_content(
        self,
        project_id: str,
        artifacts: List[Artifact],
        thread_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, str]]:
        """
        Export artifacts in all supported formats in parallel and return content.
        
        Args:
            project_id: Project identifier
            artifacts: List of artifacts
            thread_id: Thread identifier
        
        Returns:
            Dictionary of format -> content dictionary
        """
        state = await self.export_all_formats(project_id, artifacts, thread_id)
        return state.get("exported_content", {})
    
    async def export_parallel(
        self,
        project_id: str,
        artifacts: List[Artifact],
        formats: List[str],
        thread_id: Optional[str] = None,
    ) -> DeliveryAgentState:
        """
        Export artifacts in specified formats in parallel.
        
        Args:
            project_id: Project identifier
            artifacts: List of artifacts
            formats: List of formats to export
            thread_id: Thread identifier
        
        Returns:
            Delivery state with exported content
        """
        state = create_delivery_state(project_id, thread_id)
        state["artifacts"] = {a.artifact_id: a for a in artifacts}
        state["export_formats"] = formats
        state["export_mode"] = "parallel"
        state["selected_artifact_ids"] = [a.artifact_id for a in artifacts]
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def export_parallel(
        self,
        project_id: str,
        artifacts: List[Artifact],
        formats: List[str],
        thread_id: Optional[str] = None,
    ) -> DeliveryAgentState:
        """
        Export artifacts in specified formats in parallel.
        
        Args:
            project_id: Project identifier
            artifacts: List of artifacts
            formats: List of formats to export
            thread_id: Thread identifier
        
        Returns:
            Delivery state with exported content
        """
        state = create_delivery_state(project_id, thread_id)
        state["artifacts"] = {a.artifact_id: a for a in artifacts}
        state["export_formats"] = formats
        state["export_mode"] = "parallel"
        state["selected_artifact_ids"] = [a.artifact_id for a in artifacts]
        
        config = {
            "configurable": {
                "project_id": project_id,
                "thread_id": state["thread_id"],
            }
        }
        
        return await self.graph.ainvoke(state, config=config)
    
    async def get_state(self, thread_id: str) -> Optional[DeliveryAgentState]:
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


# ==================== Export Utilities ====================

class ExportFormat:
    """Supported export formats."""
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    OPENAPI = "openapi"
    GITHUB_ISSUES = "github_issues"
    CURSOR_AI = "cursor_ai"
    CLAUDE_CODE = "claude_code"


def format_exported_content(
    content: Dict[str, str],
    format: str = "markdown",
) -> str:
    """
    Format exported content for display/download.
    
    Args:
        content: Dictionary of content by subformat
        format: Main format to extract
    
    Returns:
        Formatted content string
    """
    if format in ["markdown", "cursor_ai", "claude_code", "github_issues"]:
        return content.get(format, content.get("markdown", ""))
    elif format in ["json", "yaml"]:
        return content.get(format, content.get("json", ""))
    elif format == "openapi":
        return content.get("openapi_json", content.get("openapi_yaml", ""))
    return content.get("markdown", "")


# ==================== Factory Function ====================

def create_delivery_agent(
    checkpoint_saver: Optional[CheckpointSaver] = None,
    redis_url: Optional[str] = None,
) -> DeliveryAgent:
    """
    Create a Delivery Agent instance.
    
    Args:
        checkpoint_saver: Optional checkpoint saver
        redis_url: Redis URL for default checkpointing
    
    Returns:
        Configured DeliveryAgent instance
    """
    from ..checkpoint import get_checkpoint_saver
    
    if checkpoint_saver is None and redis_url:
        checkpoint_saver = get_checkpoint_saver(redis_url=redis_url)
    
    return DeliveryAgent(checkpoint_saver=checkpoint_saver)
