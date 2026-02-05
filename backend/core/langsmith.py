"""
LangSmith configuration for agent tracing and debugging.

LangSmith provides observability for LangChain/LangGraph applications,
enabling tracking of agent runs, debugging, and performance monitoring.
"""

import os
from typing import Optional
from functools import lru_cache

from langchain.callbacks.manager import add_langsmith_cb_params
from langchain_core.runnables import RunnableConfig
from langsmith import Client
from langsmith.run_helpers import traceable


# LangSmith Configuration
LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT: Optional[str] = os.getenv("LANGCHAIN_PROJECT", "specgen-agent")
LANGCHAIN_TRACING_V2: Optional[str] = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_ENDPOINT: Optional[str] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")


def is_langsmith_configured() -> bool:
    """Check if LangSmith is properly configured with API key."""
    return LANGCHAIN_API_KEY is not None and len(LANGCHAIN_API_KEY) > 0


def get_langsmith_client() -> Optional[Client]:
    """Get LangSmith client instance if configured."""
    if is_langsmith_configured():
        return Client(
            api_url=LANGCHAIN_ENDPOINT,
            api_key=LANGCHAIN_API_KEY,
        )
    return None


def configure_langsmith():
    """
    Configure LangSmith environment variables and callbacks.
    
    This sets up the environment for LangChain/LangGraph tracing.
    For development, tracing is enabled by default.
    For production, ensure LANGCHAIN_API_KEY is set.
    """
    if is_langsmith_configured():
        print(f"LangSmith configured: project='{LANGCHAIN_PROJECT}', endpoint='{LANGCHAIN_ENDPOINT}'")
    else:
        print("LangSmith not configured: LANGCHAIN_API_KEY not set")
        print("Set LANGCHAIN_API_KEY environment variable to enable tracing")


def get_runnable_config(
    run_name: str,
    metadata: Optional[dict] = None,
    tags: Optional[list] = None,
) -> RunnableConfig:
    """
    Get RunnableConfig with LangSmith parameters.
    
    Args:
        run_name: Name for this run (appears in LangSmith)
        metadata: Additional metadata for the run
        tags: Tags to categorize this run
    
    Returns:
        RunnableConfig with LangSmith callback parameters
    """
    config = RunnableConfig(
        run_name=run_name,
        metadata=metadata or {},
        tags=tags or [],
    )
    
    # Add LangSmith callback parameters
    if is_langsmith_configured():
        config = add_langsmith_cb_params(config)
    
    return config


@traceable(name="agent_run", tags=["agent", "specgen"])
def trace_agent_run(
    func,
    project_name: Optional[str] = None,
):
    """
    Decorator to trace a function as an agent run in LangSmith.
    
    Args:
        func: Function to trace
        project_name: Optional project name override
    
    Usage:
        @trace_agent_run(project_name="interrogation-agent")
        def analyze_decisions(context):
            ...
    """
    project = project_name or LANGCHAIN_PROJECT
    return traceable(name=func.__name__, project_name=project)(func)


def create_traced_node(node_name: str):
    """
    Create a traced version of a node function.
    
    Args:
        node_name: Name of the node
    
    Returns:
        Decorated function that traces execution in LangSmith
    """
    def decorator(func):
        return traceable(
            name=f"node.{node_name}",
            project_name=LANGCHAIN_PROJECT,
            tags=["node", node_name],
        )(func)
    return decorator


class LangSmithTracer:
    """
    Wrapper class for LangSmith tracing operations.
    
    Provides high-level methods for creating traces,
    logging runs, and managing trace data.
    """
    
    def __init__(self, project: Optional[str] = None):
        """
        Initialize LangSmith tracer.
        
        Args:
            project: Project name (defaults to LANGCHAIN_PROJECT env var)
        """
        self.project = project or LANGCHAIN_PROJECT
        self.client = get_langsmith_client()
    
    def start_run(self, run_name: str, inputs: dict) -> Optional[str]:
        """
        Start a new run and return run ID.
        
        Args:
            run_name: Name of the run
            inputs: Input data for the run
        
        Returns:
            Run ID if successful, None otherwise
        """
        if not self.client:
            return None
        
        run = self.client.create_run(
            name=run_name,
            project_name=self.project,
            inputs=inputs,
            run_type="chain",
        )
        return run.id
    
    def end_run(self, run_id: str, outputs: dict, error: Optional[Exception] = None):
        """
        End a run with outputs or error.
        
        Args:
            run_id: ID of the run to end
            outputs: Output data
            error: Optional error that occurred
        """
        if not self.client or not run_id:
            return
        
        if error:
            self.client.update_run(
                run_id=run_id,
                outputs=outputs,
                error=str(error),
                status="failed",
            )
        else:
            self.client.update_run(
                run_id=run_id,
                outputs=outputs,
                status="completed",
            )
    
    def log_event(self, run_id: str, event_name: str, data: dict):
        """
        Log an event within a run.
        
        Args:
            run_id: ID of the parent run
            event_name: Name of the event
            data: Event data
        """
        if not self.client or not run_id:
            return
        
        self.client.create_feedback(
            run_id=run_id,
            key=event_name,
            score=1.0,
            comment=data.get("message", ""),
        )
    
    def get_run_history(self, run_id: str) -> list:
        """
        Get the history of a run (all child runs).
        
        Args:
            run_id: ID of the parent run
        
        Returns:
            List of child runs
        """
        if not self.client:
            return []
        
        return list(self.client.list_examples(filter=f"run_id={run_id}"))
    
    def export_traces(self, run_id: str) -> dict:
        """
        Export traces for a run as a dictionary.
        
        Args:
            run_id: ID of the run
        
        Returns:
            Dictionary containing trace data
        """
        if not self.client:
            return {}
        
        run = self.client.read_run(run_id)
        children = self.get_run_history(run_id)
        
        return {
            "run": run,
            "children": children,
            "structure": self._build_structure(run, children),
        }
    
    def _build_structure(self, run: dict, children: list) -> dict:
        """Build a tree structure from runs and children."""
        structure = {
            "name": run.get("name", "unknown"),
            "type": run.get("run_type", "unknown"),
            "children": [],
        }
        
        for child in children:
            child_structure = {
                "name": child.get("name", "unknown"),
                "type": child.get("run_type", "unknown"),
                "children": [],
            }
            structure["children"].append(child_structure)
        
        return structure


@lru_cache(maxsize=1)
def get_tracer(project: Optional[str] = None) -> LangSmithTracer:
    """
    Get a cached LangSmith tracer instance.
    
    Args:
        project: Optional project name
    
    Returns:
        LangSmithTracer instance
    """
    return LangSmithTracer(project=project)


# Initialize LangSmith on module import
configure_langsmith()
