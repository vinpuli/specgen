"""
LangGraph visualization utilities for development workflows.

This module provides a lightweight visualizer for compiled LangGraph graphs,
including Mermaid and ASCII rendering plus file export helpers.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ..langsmith import get_tracer, is_langsmith_configured


class VisualizationFormat(str, Enum):
    """Supported graph visualization output formats."""

    MERMAID = "mermaid"
    ASCII = "ascii"


@dataclass
class GraphVisualizationArtifact:
    """A generated visualization artifact."""

    graph_name: str
    format: VisualizationFormat
    content: str
    generated_at: str
    output_path: Optional[str] = None


@dataclass
class GraphStructureNode:
    """Serializable graph node representation."""

    id: str
    name: str
    metadata: Dict[str, Any]


@dataclass
class GraphStructureEdge:
    """Serializable graph edge representation."""

    source: str
    target: str
    metadata: Dict[str, Any]


@dataclass
class GraphStructure:
    """Serializable graph structure output."""

    graph_name: str
    nodes: List[GraphStructureNode]
    edges: List[GraphStructureEdge]
    metadata: Dict[str, Any]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert structure to dictionary."""
        return {
            "graph_name": self.graph_name,
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "metadata": node.metadata,
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "metadata": edge.metadata,
                }
                for edge in self.edges
            ],
            "metadata": self.metadata,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert structure to JSON."""
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class GraphStructureDiff:
    """Graph structure diff between two graph versions."""

    base_graph_name: str
    target_graph_name: str
    added_nodes: List[GraphStructureNode]
    removed_nodes: List[GraphStructureNode]
    common_nodes: List[GraphStructureNode]
    added_edges: List[GraphStructureEdge]
    removed_edges: List[GraphStructureEdge]
    common_edges: List[GraphStructureEdge]
    summary: Dict[str, Any]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_graph_name": self.base_graph_name,
            "target_graph_name": self.target_graph_name,
            "added_nodes": [
                {"id": node.id, "name": node.name, "metadata": node.metadata}
                for node in self.added_nodes
            ],
            "removed_nodes": [
                {"id": node.id, "name": node.name, "metadata": node.metadata}
                for node in self.removed_nodes
            ],
            "common_nodes": [
                {"id": node.id, "name": node.name, "metadata": node.metadata}
                for node in self.common_nodes
            ],
            "added_edges": [
                {"source": edge.source, "target": edge.target, "metadata": edge.metadata}
                for edge in self.added_edges
            ],
            "removed_edges": [
                {"source": edge.source, "target": edge.target, "metadata": edge.metadata}
                for edge in self.removed_edges
            ],
            "common_edges": [
                {"source": edge.source, "target": edge.target, "metadata": edge.metadata}
                for edge in self.common_edges
            ],
            "summary": self.summary,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class CheckpointStateSummary:
    """Serializable summary for checkpoint state inspection."""

    checkpoint_id: str
    keys: List[str]
    value_types: Dict[str, str]
    sizes: Dict[str, int]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "keys": self.keys,
            "value_types": self.value_types,
            "sizes": self.sizes,
            "metadata": self.metadata,
        }


@dataclass
class CheckpointHistoryVisualization:
    """Checkpoint history visualization payload."""

    thread_id: str
    checkpoint_count: int
    summaries: List[CheckpointStateSummary]
    timeline_mermaid: str
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "checkpoint_count": self.checkpoint_count,
            "summaries": [summary.to_dict() for summary in self.summaries],
            "timeline_mermaid": self.timeline_mermaid,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class ExecutionTraceStep:
    """Single step in an execution trace with timing details."""

    step_index: int
    event_type: str
    run_id: Optional[str]
    parent_run_id: Optional[str]
    node_name: Optional[str]
    started_at: Optional[str]
    ended_at: Optional[str]
    duration_ms: Optional[float]
    status: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "node_name": self.node_name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionTraceView:
    """Execution trace viewer payload with timing summaries and timeline."""

    trace_name: str
    total_steps: int
    total_duration_ms: Optional[float]
    average_step_duration_ms: Optional[float]
    longest_step_duration_ms: Optional[float]
    timeline_mermaid: str
    steps: List[ExecutionTraceStep]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_name": self.trace_name,
            "total_steps": self.total_steps,
            "total_duration_ms": self.total_duration_ms,
            "average_step_duration_ms": self.average_step_duration_ms,
            "longest_step_duration_ms": self.longest_step_duration_ms,
            "timeline_mermaid": self.timeline_mermaid,
            "steps": [step.to_dict() for step in self.steps],
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class LangSmithDebugView:
    """LangSmith-backed production debugging payload."""

    run_id: str
    project: Optional[str]
    trace_view: ExecutionTraceView
    run_summary: Dict[str, Any]
    raw_trace: Dict[str, Any]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project": self.project,
            "trace_view": self.trace_view.to_dict(),
            "run_summary": self.run_summary,
            "raw_trace": self.raw_trace,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class LangGraphVisualizer:
    """
    Visualizer for compiled LangGraph graphs.

    Designed for development/debug usage where engineers need quick graph
    visualization in terminal-friendly or markdown-friendly form.
    """

    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        self.output_dir = Path(output_dir) if output_dir else None

    def render(
        self,
        graph: Any,
        format: VisualizationFormat = VisualizationFormat.MERMAID,
        xray: bool = False,
    ) -> str:
        """
        Render a compiled graph to the specified format.

        Args:
            graph: Compiled LangGraph graph (must support get_graph())
            format: Desired visualization format
            xray: Enable xray/introspection mode when supported

        Returns:
            Rendered graph text
        """
        drawable = self._get_drawable_graph(graph, xray=xray)

        if format == VisualizationFormat.MERMAID:
            if hasattr(drawable, "draw_mermaid"):
                return drawable.draw_mermaid()
            if hasattr(drawable, "to_mermaid"):
                return drawable.to_mermaid()
            raise ValueError("Graph object does not support Mermaid rendering")

        if format == VisualizationFormat.ASCII:
            if hasattr(drawable, "draw_ascii"):
                try:
                    return drawable.draw_ascii()
                except Exception as exc:
                    return (
                        "ASCII visualization unavailable. Install optional graph layout "
                        f"dependencies (original error: {exc})."
                    )
            raise ValueError("Graph object does not support ASCII rendering")

        raise ValueError(f"Unsupported visualization format: {format}")

    def save(
        self,
        graph: Any,
        graph_name: str,
        format: VisualizationFormat = VisualizationFormat.MERMAID,
        xray: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> GraphVisualizationArtifact:
        """
        Render and save a graph visualization artifact.

        Args:
            graph: Compiled LangGraph graph
            graph_name: Artifact base name
            format: Output format
            xray: Enable xray/introspection mode when supported
            output_dir: Optional output directory override

        Returns:
            Generated artifact metadata
        """
        content = self.render(graph=graph, format=format, xray=xray)
        target_dir = Path(output_dir) if output_dir else self.output_dir or Path("tmp/graph_visualizations")
        target_dir.mkdir(parents=True, exist_ok=True)

        extension = "mmd" if format == VisualizationFormat.MERMAID else "txt"
        output_path = target_dir / f"{graph_name}.{extension}"
        output_path.write_text(content, encoding="utf-8")

        return GraphVisualizationArtifact(
            graph_name=graph_name,
            format=format,
            content=content,
            generated_at=datetime.utcnow().isoformat(),
            output_path=str(output_path),
        )

    def visualize_agent(
        self,
        agent: Any,
        graph_name: str,
        formats: Optional[Sequence[VisualizationFormat]] = None,
        xray: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> List[GraphVisualizationArtifact]:
        """
        Visualize a single agent instance by using its compiled graph.

        Args:
            agent: Agent object exposing `graph` or `create_workflow(...)`
            graph_name: Base name for artifacts
            formats: Desired output formats (default Mermaid)
            xray: Enable xray mode when supported
            output_dir: Optional output directory override

        Returns:
            List of generated visualization artifacts
        """
        compiled_graph = self.extract_graph(agent)
        requested_formats = list(formats) if formats else [VisualizationFormat.MERMAID]

        artifacts: List[GraphVisualizationArtifact] = []
        for format in requested_formats:
            artifacts.append(
                self.save(
                    graph=compiled_graph,
                    graph_name=f"{graph_name}_{format.value}",
                    format=format,
                    xray=xray,
                    output_dir=output_dir,
                )
            )
        return artifacts

    def visualize_agents(
        self,
        agents: Dict[str, Any],
        formats: Optional[Sequence[VisualizationFormat]] = None,
        xray: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, List[GraphVisualizationArtifact]]:
        """
        Visualize multiple agent graphs in one call.

        Args:
            agents: Mapping of graph_name -> agent instance
            formats: Desired output formats
            xray: Enable xray mode when supported
            output_dir: Optional output directory override

        Returns:
            Mapping of graph_name -> generated artifacts
        """
        results: Dict[str, List[GraphVisualizationArtifact]] = {}
        for graph_name, agent in agents.items():
            results[graph_name] = self.visualize_agent(
                agent=agent,
                graph_name=graph_name,
                formats=formats,
                xray=xray,
                output_dir=output_dir,
            )
        return results

    def serialize_graph_structure(
        self,
        graph: Any,
        graph_name: str,
        xray: bool = False,
    ) -> GraphStructure:
        """
        Serialize graph nodes/edges into a stable JSON-friendly structure.

        Args:
            graph: Compiled LangGraph graph
            graph_name: Logical graph name for metadata
            xray: Enable xray mode when supported

        Returns:
            GraphStructure
        """
        drawable = self._get_drawable_graph(graph, xray=xray)
        nodes, edges = self._extract_nodes_and_edges(drawable)

        return GraphStructure(
            graph_name=graph_name,
            nodes=nodes,
            edges=edges,
            metadata={
                "node_count": len(nodes),
                "edge_count": len(edges),
                "xray": xray,
            },
            generated_at=datetime.utcnow().isoformat(),
        )

    def serialize_agent_structure(
        self,
        agent: Any,
        graph_name: str,
        xray: bool = False,
    ) -> GraphStructure:
        """
        Serialize graph structure for an agent instance.

        Args:
            agent: Agent object exposing `graph` or `create_workflow(...)`
            graph_name: Logical graph name for output
            xray: Enable xray mode when supported

        Returns:
            GraphStructure
        """
        compiled_graph = self.extract_graph(agent)
        return self.serialize_graph_structure(
            graph=compiled_graph,
            graph_name=graph_name,
            xray=xray,
        )

    def save_graph_structure(
        self,
        graph: Any,
        graph_name: str,
        xray: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Serialize and save graph structure as JSON.

        Returns:
            Output file path
        """
        structure = self.serialize_graph_structure(
            graph=graph,
            graph_name=graph_name,
            xray=xray,
        )
        target_dir = Path(output_dir) if output_dir else self.output_dir or Path("tmp/graph_visualizations")
        target_dir.mkdir(parents=True, exist_ok=True)

        output_path = target_dir / f"{graph_name}_structure.json"
        output_path.write_text(structure.to_json(indent=2), encoding="utf-8")
        return str(output_path)

    def compare_graph_structures(
        self,
        base_structure: GraphStructure,
        target_structure: GraphStructure,
    ) -> GraphStructureDiff:
        """
        Compare two serialized graph structures and produce a version diff.

        Args:
            base_structure: Baseline graph structure
            target_structure: Target graph structure to compare against baseline

        Returns:
            GraphStructureDiff with added/removed/common nodes and edges
        """
        base_node_map = {node.id: node for node in base_structure.nodes}
        target_node_map = {node.id: node for node in target_structure.nodes}

        base_edge_map = {(edge.source, edge.target): edge for edge in base_structure.edges}
        target_edge_map = {(edge.source, edge.target): edge for edge in target_structure.edges}

        added_node_ids = sorted(set(target_node_map.keys()) - set(base_node_map.keys()))
        removed_node_ids = sorted(set(base_node_map.keys()) - set(target_node_map.keys()))
        common_node_ids = sorted(set(base_node_map.keys()) & set(target_node_map.keys()))

        added_edges_keys = sorted(set(target_edge_map.keys()) - set(base_edge_map.keys()))
        removed_edges_keys = sorted(set(base_edge_map.keys()) - set(target_edge_map.keys()))
        common_edges_keys = sorted(set(base_edge_map.keys()) & set(target_edge_map.keys()))

        added_nodes = [target_node_map[node_id] for node_id in added_node_ids]
        removed_nodes = [base_node_map[node_id] for node_id in removed_node_ids]
        common_nodes = [target_node_map[node_id] for node_id in common_node_ids]

        added_edges = [target_edge_map[key] for key in added_edges_keys]
        removed_edges = [base_edge_map[key] for key in removed_edges_keys]
        common_edges = [target_edge_map[key] for key in common_edges_keys]

        summary = {
            "node_count_base": len(base_structure.nodes),
            "node_count_target": len(target_structure.nodes),
            "edge_count_base": len(base_structure.edges),
            "edge_count_target": len(target_structure.edges),
            "nodes_added": len(added_nodes),
            "nodes_removed": len(removed_nodes),
            "nodes_unchanged": len(common_nodes),
            "edges_added": len(added_edges),
            "edges_removed": len(removed_edges),
            "edges_unchanged": len(common_edges),
            "is_identical": len(added_nodes) == 0 and len(removed_nodes) == 0 and len(added_edges) == 0 and len(removed_edges) == 0,
        }

        return GraphStructureDiff(
            base_graph_name=base_structure.graph_name,
            target_graph_name=target_structure.graph_name,
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            common_nodes=common_nodes,
            added_edges=added_edges,
            removed_edges=removed_edges,
            common_edges=common_edges,
            summary=summary,
            generated_at=datetime.utcnow().isoformat(),
        )

    def compare_graphs(
        self,
        base_graph: Any,
        target_graph: Any,
        base_name: str = "base",
        target_name: str = "target",
        xray: bool = False,
    ) -> GraphStructureDiff:
        """
        Compare two compiled graphs by serializing both and diffing structures.
        """
        base_structure = self.serialize_graph_structure(
            graph=base_graph,
            graph_name=base_name,
            xray=xray,
        )
        target_structure = self.serialize_graph_structure(
            graph=target_graph,
            graph_name=target_name,
            xray=xray,
        )
        return self.compare_graph_structures(base_structure, target_structure)

    def save_graph_diff(
        self,
        diff: GraphStructureDiff,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> str:
        """Save graph diff output as JSON."""
        target_dir = Path(output_dir) if output_dir else self.output_dir or Path("tmp/graph_visualizations")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{diff.base_graph_name}_vs_{diff.target_graph_name}_diff.json"
        output_path.write_text(diff.to_json(indent=2), encoding="utf-8")
        return str(output_path)

    def render_graph_diff_summary(self, diff: GraphStructureDiff) -> str:
        """Render a concise human-readable diff summary."""
        summary = diff.summary
        lines = [
            f"Graph Diff: {diff.base_graph_name} -> {diff.target_graph_name}",
            f"Nodes: +{summary.get('nodes_added', 0)} / -{summary.get('nodes_removed', 0)} / ={summary.get('nodes_unchanged', 0)}",
            f"Edges: +{summary.get('edges_added', 0)} / -{summary.get('edges_removed', 0)} / ={summary.get('edges_unchanged', 0)}",
            f"Identical: {summary.get('is_identical', False)}",
        ]

        if diff.added_nodes:
            lines.append("Added Nodes: " + ", ".join(node.id for node in diff.added_nodes))
        if diff.removed_nodes:
            lines.append("Removed Nodes: " + ", ".join(node.id for node in diff.removed_nodes))
        if diff.added_edges:
            lines.append(
                "Added Edges: " + ", ".join(f"{edge.source}->{edge.target}" for edge in diff.added_edges)
            )
        if diff.removed_edges:
            lines.append(
                "Removed Edges: " + ", ".join(f"{edge.source}->{edge.target}" for edge in diff.removed_edges)
            )

        return "\n".join(lines)

    def summarize_checkpoint_state(self, checkpoint: Dict[str, Any]) -> CheckpointStateSummary:
        """
        Build a compact checkpoint summary for state inspection.

        Args:
            checkpoint: Raw checkpoint dictionary

        Returns:
            CheckpointStateSummary
        """
        checkpoint_id = str(
            checkpoint.get("id")
            or checkpoint.get("checkpoint_id")
            or checkpoint.get("ts")
            or "unknown"
        )

        keys = sorted([str(key) for key in checkpoint.keys()])
        value_types = {
            str(key): type(value).__name__
            for key, value in checkpoint.items()
        }
        sizes = {
            str(key): self._estimate_size(value)
            for key, value in checkpoint.items()
        }

        metadata = {
            "timestamp": checkpoint.get("ts"),
            "version_count": len(checkpoint.get("versions", {}) or {}),
            "channel_value_count": len(checkpoint.get("channel_values", {}) or {}),
            "next_count": len(checkpoint.get("next", []) or []),
        }

        return CheckpointStateSummary(
            checkpoint_id=checkpoint_id,
            keys=keys,
            value_types=value_types,
            sizes=sizes,
            metadata=metadata,
        )

    def visualize_checkpoint_history(
        self,
        checkpoints: List[Dict[str, Any]],
        thread_id: str = "unknown-thread",
    ) -> CheckpointHistoryVisualization:
        """
        Visualize checkpoint history for development state inspection.

        Produces:
        - Structured checkpoint summaries
        - Mermaid timeline representation
        """
        ordered = sorted(
            checkpoints,
            key=lambda checkpoint: str(
                checkpoint.get("ts")
                or checkpoint.get("id")
                or checkpoint.get("checkpoint_id")
                or ""
            ),
        )

        summaries = [self.summarize_checkpoint_state(checkpoint) for checkpoint in ordered]
        timeline_mermaid = self._build_checkpoint_timeline_mermaid(summaries)

        return CheckpointHistoryVisualization(
            thread_id=thread_id,
            checkpoint_count=len(summaries),
            summaries=summaries,
            timeline_mermaid=timeline_mermaid,
            generated_at=datetime.utcnow().isoformat(),
        )

    async def visualize_checkpoints_for_thread(
        self,
        checkpoint_manager: Any,
        thread_id: str,
        limit: int = 50,
    ) -> CheckpointHistoryVisualization:
        """
        Load checkpoints from manager and create a visualization payload.

        Args:
            checkpoint_manager: Object implementing `list_checkpoints(thread_id, limit)`
            thread_id: Thread identifier to inspect
            limit: Maximum checkpoint history items

        Returns:
            CheckpointHistoryVisualization
        """
        checkpoints = await checkpoint_manager.list_checkpoints(thread_id=thread_id, limit=limit)
        normalized = [checkpoint if isinstance(checkpoint, dict) else dict(checkpoint) for checkpoint in checkpoints]
        return self.visualize_checkpoint_history(normalized, thread_id=thread_id)

    def save_checkpoint_visualization(
        self,
        visualization: CheckpointHistoryVisualization,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Save checkpoint visualization payload as JSON for inspection.

        Returns:
            Output path
        """
        target_dir = Path(output_dir) if output_dir else self.output_dir or Path("tmp/graph_visualizations")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{visualization.thread_id}_checkpoints.json"
        output_path.write_text(visualization.to_json(indent=2), encoding="utf-8")
        return str(output_path)

    def create_execution_trace_view(
        self,
        log_entries: List[Dict[str, Any]],
        trace_name: str = "execution-trace",
    ) -> ExecutionTraceView:
        """
        Build an execution trace viewer payload from stream_log entries.

        Args:
            log_entries: Formatted entries from `StreamingManager.stream_log`
            trace_name: Name for the trace artifact

        Returns:
            ExecutionTraceView with timing information and timeline
        """
        ordered = sorted(
            log_entries,
            key=lambda entry: str(entry.get("timestamp", "")),
        )
        steps = self._extract_trace_steps(ordered)

        durations = [step.duration_ms for step in steps if step.duration_ms is not None]
        total_duration_ms = sum(durations) if durations else None
        average_step_duration_ms = (
            (sum(durations) / len(durations)) if durations else None
        )
        longest_step_duration_ms = max(durations) if durations else None

        timeline_mermaid = self._build_execution_trace_timeline_mermaid(steps)
        return ExecutionTraceView(
            trace_name=trace_name,
            total_steps=len(steps),
            total_duration_ms=total_duration_ms,
            average_step_duration_ms=average_step_duration_ms,
            longest_step_duration_ms=longest_step_duration_ms,
            timeline_mermaid=timeline_mermaid,
            steps=steps,
            generated_at=datetime.utcnow().isoformat(),
        )

    async def capture_execution_trace(
        self,
        streaming_manager: Any,
        graph: Any,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        include_outputs: bool = True,
        auto_refresh: bool = True,
        trace_name: str = "execution-trace",
    ) -> ExecutionTraceView:
        """
        Capture and build an execution trace directly from a running graph.

        Args:
            streaming_manager: Streaming manager exposing `stream_log(...)`
            graph: Compiled LangGraph graph
            input_data: Input state for execution
            config: Optional runtime config
            include_outputs: Forwarded to `stream_log`
            auto_refresh: Forwarded to `stream_log`
            trace_name: Name for the trace artifact
        """
        log_entries: List[Dict[str, Any]] = []
        async for entry in streaming_manager.stream_log(
            graph=graph,
            input_data=input_data,
            config=config,
            include_outputs=include_outputs,
            auto_refresh=auto_refresh,
        ):
            log_entries.append(entry)

        return self.create_execution_trace_view(log_entries, trace_name=trace_name)

    def save_execution_trace(
        self,
        trace_view: ExecutionTraceView,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> str:
        """Save execution trace payload as JSON."""
        target_dir = Path(output_dir) if output_dir else self.output_dir or Path("tmp/graph_visualizations")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{trace_view.trace_name}_trace.json"
        output_path.write_text(trace_view.to_json(indent=2), encoding="utf-8")
        return str(output_path)

    def render_execution_trace_table(self, trace_view: ExecutionTraceView) -> str:
        """Render a compact ASCII table for quick timing inspection."""
        headers = ["idx", "event", "node", "status", "duration_ms"]
        lines = [" | ".join(headers), "-" * 72]

        for step in trace_view.steps:
            duration_text = (
                f"{step.duration_ms:.2f}" if isinstance(step.duration_ms, (int, float)) else "n/a"
            )
            lines.append(
                " | ".join(
                    [
                        str(step.step_index),
                        step.event_type,
                        step.node_name or "-",
                        step.status,
                        duration_text,
                    ]
                )
            )

        return "\n".join(lines)

    def create_langsmith_debug_view(
        self,
        run_id: str,
        project: Optional[str] = None,
        trace_name: Optional[str] = None,
    ) -> LangSmithDebugView:
        """
        Build production debugging view from LangSmith trace data.

        Args:
            run_id: LangSmith run identifier
            project: Optional project override
            trace_name: Optional output trace name override

        Returns:
            LangSmithDebugView
        """
        if not is_langsmith_configured():
            raise ValueError("LangSmith is not configured (missing LANGCHAIN_API_KEY)")

        tracer = get_tracer(project=project)
        raw_trace = tracer.export_traces(run_id)
        normalized = self._normalize_langsmith_export(raw_trace)

        log_entries = self._convert_langsmith_to_log_entries(normalized)
        effective_trace_name = trace_name or f"langsmith-{run_id}"
        trace_view = self.create_execution_trace_view(
            log_entries=log_entries,
            trace_name=effective_trace_name,
        )

        run_data = normalized.get("run", {})
        run_summary = {
            "name": run_data.get("name"),
            "run_type": run_data.get("run_type"),
            "status": run_data.get("status"),
            "error": run_data.get("error"),
            "start_time": run_data.get("start_time"),
            "end_time": run_data.get("end_time"),
            "child_count": len(normalized.get("children", [])),
        }

        return LangSmithDebugView(
            run_id=run_id,
            project=project,
            trace_view=trace_view,
            run_summary=run_summary,
            raw_trace=normalized,
            generated_at=datetime.utcnow().isoformat(),
        )

    def save_langsmith_debug_view(
        self,
        debug_view: LangSmithDebugView,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> str:
        """Save LangSmith debugging payload as JSON."""
        target_dir = Path(output_dir) if output_dir else self.output_dir or Path("tmp/graph_visualizations")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{debug_view.run_id}_langsmith_debug.json"
        output_path.write_text(debug_view.to_json(indent=2), encoding="utf-8")
        return str(output_path)

    @staticmethod
    def extract_graph(agent: Any) -> Any:
        """
        Extract compiled graph from an agent-like object.

        Supports:
        - `agent.graph` attribute when present
        - `agent.create_workflow(...)` fallback for supervisor-style objects
        """
        graph = getattr(agent, "graph", None)
        if graph is not None:
            return graph

        if hasattr(agent, "create_workflow"):
            # Minimal safe defaults for development graph extraction.
            return agent.create_workflow(project_id="dev-graph-visualizer")

        raise ValueError(
            f"Unable to extract graph from agent type {type(agent).__name__}. "
            "Expected `graph` attribute or `create_workflow(...)` method."
        )

    @staticmethod
    def _get_drawable_graph(graph: Any, xray: bool = False) -> Any:
        """Get drawable graph representation from compiled graph."""
        if not hasattr(graph, "get_graph"):
            raise ValueError("Provided graph does not implement get_graph()")

        try:
            return graph.get_graph(xray=xray)
        except TypeError:
            return graph.get_graph()

    @staticmethod
    def _extract_nodes_and_edges(drawable: Any) -> tuple[List[GraphStructureNode], List[GraphStructureEdge]]:
        """Extract nodes and edges from drawable graph with Mermaid fallback."""
        nodes: List[GraphStructureNode] = []
        edges: List[GraphStructureEdge] = []

        drawable_nodes = getattr(drawable, "nodes", None)
        if isinstance(drawable_nodes, dict):
            for node_id, node_obj in drawable_nodes.items():
                node_name = (
                    getattr(node_obj, "name", None)
                    or str(node_id)
                )
                metadata = {
                    "class_name": type(node_obj).__name__,
                }
                if hasattr(node_obj, "__dict__"):
                    metadata["attributes"] = {
                        k: str(v) for k, v in node_obj.__dict__.items()
                    }
                nodes.append(
                    GraphStructureNode(
                        id=str(node_id),
                        name=str(node_name),
                        metadata=metadata,
                    )
                )

        drawable_edges = getattr(drawable, "edges", None)
        if isinstance(drawable_edges, list):
            for edge_obj in drawable_edges:
                source = getattr(edge_obj, "source", None) or getattr(edge_obj, "from_", None)
                target = getattr(edge_obj, "target", None) or getattr(edge_obj, "to", None)
                if source is None or target is None:
                    continue
                metadata = {"class_name": type(edge_obj).__name__}
                if hasattr(edge_obj, "__dict__"):
                    metadata["attributes"] = {
                        k: str(v) for k, v in edge_obj.__dict__.items()
                    }
                edges.append(
                    GraphStructureEdge(
                        source=str(source),
                        target=str(target),
                        metadata=metadata,
                    )
                )

        if nodes and edges:
            return nodes, edges

        mermaid = None
        if hasattr(drawable, "draw_mermaid"):
            try:
                mermaid = drawable.draw_mermaid()
            except Exception:
                mermaid = None

        if mermaid:
            return LangGraphVisualizer._parse_mermaid_to_structure(mermaid)

        return nodes, edges

    @staticmethod
    def _parse_mermaid_to_structure(mermaid: str) -> tuple[List[GraphStructureNode], List[GraphStructureEdge]]:
        """Parse Mermaid graph text into structure data."""
        node_map: Dict[str, GraphStructureNode] = {}
        edges: List[GraphStructureEdge] = []

        for raw_line in mermaid.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("%%") or line.startswith("graph"):
                continue

            match = re.match(r"([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)", line)
            if not match:
                continue

            source = match.group(1)
            target = match.group(2)
            if source not in node_map:
                node_map[source] = GraphStructureNode(
                    id=source,
                    name=source,
                    metadata={"source": "mermaid"},
                )
            if target not in node_map:
                node_map[target] = GraphStructureNode(
                    id=target,
                    name=target,
                    metadata={"source": "mermaid"},
                )

            edges.append(
                GraphStructureEdge(
                    source=source,
                    target=target,
                    metadata={"source": "mermaid"},
                )
            )

        return list(node_map.values()), edges

    @staticmethod
    def _estimate_size(value: Any) -> int:
        """Estimate logical size of a value for checkpoint inspection."""
        if value is None:
            return 0
        if isinstance(value, (str, bytes, list, tuple, dict, set)):
            return len(value)
        return 1

    @staticmethod
    def _build_checkpoint_timeline_mermaid(summaries: List[CheckpointStateSummary]) -> str:
        """Build a Mermaid timeline for checkpoint progression."""
        lines = ["graph LR"]
        if not summaries:
            lines.append("  empty[No checkpoints]")
            return "\n".join(lines)

        for index, summary in enumerate(summaries):
            node_id = f"cp{index}"
            label = f"{summary.checkpoint_id}"
            lines.append(f"  {node_id}[\"{label}\"]")
            if index > 0:
                previous_id = f"cp{index - 1}"
                lines.append(f"  {previous_id} --> {node_id}")

        return "\n".join(lines)

    @staticmethod
    def _extract_trace_steps(log_entries: List[Dict[str, Any]]) -> List[ExecutionTraceStep]:
        """Extract timed steps by pairing *_start and *_end events when possible."""
        steps: List[ExecutionTraceStep] = []
        open_steps: Dict[Tuple[Optional[str], str], Dict[str, Any]] = {}
        index = 0

        for entry in log_entries:
            event_type = str(entry.get("event_type", "unknown"))
            run_id = entry.get("run_id")
            parent_run_id = entry.get("parent_run_id")
            node_name = (
                (entry.get("node") or {}).get("name")
                if isinstance(entry.get("node"), dict)
                else entry.get("node")
            )
            timestamp = entry.get("timestamp")

            if event_type.endswith("_start"):
                base_event = event_type[:-6]
                open_steps[(run_id, base_event)] = entry
                continue

            if event_type.endswith("_end"):
                base_event = event_type[:-4]
                start_entry = open_steps.pop((run_id, base_event), None)
                start_timestamp = start_entry.get("timestamp") if start_entry else None
                duration_ms = LangGraphVisualizer._duration_ms(start_timestamp, timestamp)
                metadata = entry.get("metadata", {}) or {}
                if duration_ms is None and "timing" in entry and isinstance(entry["timing"], dict):
                    latent = entry["timing"].get("latent")
                    if isinstance(latent, (int, float)):
                        duration_ms = float(latent)

                steps.append(
                    ExecutionTraceStep(
                        step_index=index,
                        event_type=base_event,
                        run_id=run_id,
                        parent_run_id=parent_run_id,
                        node_name=node_name,
                        started_at=start_timestamp,
                        ended_at=timestamp,
                        duration_ms=duration_ms,
                        status="completed",
                        metadata=metadata,
                    )
                )
                index += 1
                continue

            duration_ms = None
            timing = entry.get("timing")
            if isinstance(timing, dict):
                latent = timing.get("latent")
                if isinstance(latent, (int, float)):
                    duration_ms = float(latent)

            steps.append(
                ExecutionTraceStep(
                    step_index=index,
                    event_type=event_type,
                    run_id=run_id,
                    parent_run_id=parent_run_id,
                    node_name=node_name,
                    started_at=timestamp,
                    ended_at=timestamp,
                    duration_ms=duration_ms,
                    status="instant",
                    metadata=entry.get("metadata", {}) or {},
                )
            )
            index += 1

        for (run_id, base_event), start_entry in open_steps.items():
            node_name = (
                (start_entry.get("node") or {}).get("name")
                if isinstance(start_entry.get("node"), dict)
                else start_entry.get("node")
            )
            steps.append(
                ExecutionTraceStep(
                    step_index=index,
                    event_type=base_event,
                    run_id=run_id,
                    parent_run_id=start_entry.get("parent_run_id"),
                    node_name=node_name,
                    started_at=start_entry.get("timestamp"),
                    ended_at=None,
                    duration_ms=None,
                    status="open",
                    metadata=start_entry.get("metadata", {}) or {},
                )
            )
            index += 1

        return steps

    @staticmethod
    def _duration_ms(started_at: Optional[str], ended_at: Optional[str]) -> Optional[float]:
        """Compute duration in milliseconds from ISO timestamps."""
        if not started_at or not ended_at:
            return None
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(ended_at)
            return max(0.0, (end - start).total_seconds() * 1000)
        except Exception:
            return None

    @staticmethod
    def _build_execution_trace_timeline_mermaid(steps: List[ExecutionTraceStep]) -> str:
        """Build Mermaid flow timeline for execution trace steps."""
        lines = ["graph TD"]
        if not steps:
            lines.append("  t0[No execution steps]")
            return "\n".join(lines)

        for step in steps:
            node_id = f"s{step.step_index}"
            duration_text = (
                f"{step.duration_ms:.2f}ms" if isinstance(step.duration_ms, (int, float)) else "n/a"
            )
            label = f"{step.step_index}: {step.event_type}\\n{duration_text}"
            lines.append(f"  {node_id}[\"{label}\"]")
            if step.step_index > 0:
                lines.append(f"  s{step.step_index - 1} --> {node_id}")

        return "\n".join(lines)

    @staticmethod
    def _normalize_langsmith_export(trace_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize LangSmith export objects into plain dictionaries."""
        run = LangGraphVisualizer._object_to_dict(trace_data.get("run", {}))
        children = [
            LangGraphVisualizer._object_to_dict(child)
            for child in (trace_data.get("children", []) or [])
        ]
        structure = LangGraphVisualizer._object_to_dict(trace_data.get("structure", {}))
        return {
            "run": run,
            "children": children,
            "structure": structure,
        }

    @staticmethod
    def _object_to_dict(obj: Any) -> Dict[str, Any]:
        """Convert common LangSmith/Pydantic objects to dictionary."""
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump()
            except Exception:
                pass
        if hasattr(obj, "dict"):
            try:
                return obj.dict()
            except Exception:
                pass
        if hasattr(obj, "__dict__"):
            return {
                key: value
                for key, value in obj.__dict__.items()
                if not key.startswith("_")
            }
        return {"value": str(obj)}

    @staticmethod
    def _convert_langsmith_to_log_entries(trace_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert normalized LangSmith run tree into stream_log-like entries."""
        entries: List[Dict[str, Any]] = []

        run = trace_data.get("run", {})
        children = trace_data.get("children", [])
        all_runs = [run] + list(children)

        for item in all_runs:
            if not item:
                continue
            run_type = str(item.get("run_type", "run"))
            status = str(item.get("status", "unknown"))
            start_time = item.get("start_time")
            end_time = item.get("end_time")
            run_id = item.get("id")
            parent_run_id = item.get("parent_run_id")
            name = item.get("name")

            entries.append(
                {
                    "timestamp": str(start_time or datetime.utcnow().isoformat()),
                    "event_type": f"{run_type}_start",
                    "run_id": run_id,
                    "parent_run_id": parent_run_id,
                    "node": {"name": name, "id": run_id},
                    "metadata": {
                        "status": status,
                        "source": "langsmith",
                    },
                }
            )
            entries.append(
                {
                    "timestamp": str(end_time or start_time or datetime.utcnow().isoformat()),
                    "event_type": f"{run_type}_end",
                    "run_id": run_id,
                    "parent_run_id": parent_run_id,
                    "node": {"name": name, "id": run_id},
                    "metadata": {
                        "status": status,
                        "error": item.get("error"),
                        "source": "langsmith",
                    },
                }
            )

        return entries


def create_langgraph_visualizer(
    output_dir: Optional[Union[str, Path]] = None,
) -> LangGraphVisualizer:
    """Factory for LangGraphVisualizer."""
    return LangGraphVisualizer(output_dir=output_dir)
