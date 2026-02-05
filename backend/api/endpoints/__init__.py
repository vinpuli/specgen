"""
API endpoints module.

This module exports all API routers.
"""

from backend.api.endpoints.auth import router as auth_router
from backend.api.endpoints.workspace import router as workspace_router
from backend.api.endpoints.project import router as project_router
from backend.api.endpoints.artifact import router as artifact_router
from backend.api.endpoints.comment import router as comment_router
from backend.api.endpoints.codebase import router as codebase_router

__all__ = ["auth_router", "workspace_router", "project_router", "artifact_router", "comment_router", "codebase_router"]
