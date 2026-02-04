"""
Pydantic schemas for API request/response validation.

This module provides:
- Base schemas with common configurations
- Entity schemas for all database models
- Request/Response schemas for API endpoints
"""

from backend.api.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    UserRegister,
    UserInDB,
)
from backend.api.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceMemberResponse,
)
from backend.api.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    BranchCreate,
    BranchUpdate,
    BranchResponse,
)
from backend.api.schemas.decision import (
    DecisionCreate,
    DecisionUpdate,
    DecisionResponse,
    DecisionDependencyCreate,
)
from backend.api.schemas.artifact import (
    ArtifactCreate,
    ArtifactUpdate,
    ArtifactResponse,
    ArtifactVersionResponse,
)
from backend.api.schemas.comment import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    ConversationTurnCreate,
    ConversationTurnResponse,
)
from backend.api.schemas.common import (
    PaginationParams,
    SearchParams,
    SuccessResponse,
    ErrorResponse,
    HealthResponse,
)

__all__ = [
    # User schemas
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "UserRegister",
    "UserInDB",
    # Workspace schemas
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "WorkspaceResponse",
    "WorkspaceMemberCreate",
    "WorkspaceMemberUpdate",
    "WorkspaceMemberResponse",
    # Project schemas
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "BranchCreate",
    "BranchUpdate",
    "BranchResponse",
    # Decision schemas
    "DecisionCreate",
    "DecisionUpdate",
    "DecisionResponse",
    "DecisionDependencyCreate",
    # Artifact schemas
    "ArtifactCreate",
    "ArtifactUpdate",
    "ArtifactResponse",
    "ArtifactVersionResponse",
    # Comment schemas
    "CommentCreate",
    "CommentUpdate",
    "CommentResponse",
    "ConversationTurnCreate",
    "ConversationTurnResponse",
    # Common schemas
    "PaginationParams",
    "SearchParams",
    "SuccessResponse",
    "ErrorResponse",
    "HealthResponse",
]
