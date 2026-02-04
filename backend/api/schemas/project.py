"""
Project and Branch Pydantic schemas.

This module provides:
- Project creation, update, and response schemas
- Branch schemas for version control
- Project type enums
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin
from backend.api.schemas.workspace import WorkspaceResponse


# ======================
# Enums
# ======================


class ProjectType(str, Enum):
    """Project type enum."""

    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"


class ProjectStatus(str, Enum):
    """Project status enum."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class BranchStatus(str, Enum):
    """Branch status enum."""

    ACTIVE = "active"
    MERGED = "merged"
    ARCHIVED = "archived"


# ======================
# Project Schemas
# ======================


class ProjectCreate(BaseSchema):
    """Project creation request schema."""

    workspace_id: UUID = Field(..., description="Workspace ID")
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(default=None, description="Project description")
    project_type: str = Field(default="greenfield", description="Project type")
    spec_template_id: Optional[UUID] = Field(default=None, description="Optional template ID")

    @field_validator("project_type")
    @classmethod
    def validate_project_type(cls, v: str) -> str:
        """Validate project type."""
        if v not in [pt.value for pt in ProjectType]:
            raise ValueError(f"Invalid project type: {v}")
        return v


class ProjectUpdate(BaseSchema):
    """Project update request schema."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[dict[str, Any]] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate project status."""
        if v is None:
            return v
        if v not in [ps.value for ps in ProjectStatus]:
            raise ValueError(f"Invalid status: {v}")
        return v


class ProjectResponse(UUIDMixin, TimestampSchema):
    """Project response schema."""

    workspace_id: UUID
    name: str
    description: Optional[str] = None
    project_type: str
    status: str
    settings: dict[str, Any]
    created_by: Optional[UUID] = None
    branch_count: Optional[int] = None
    decision_count: Optional[int] = None


class ProjectWithWorkspace(ProjectResponse):
    """Project response with workspace info."""

    workspace: WorkspaceResponse


class ProjectListResponse(BaseModel):
    """Project list response with pagination."""

    projects: List[ProjectResponse]
    total: int
    page: int
    page_size: int


class ProjectSettingsUpdate(BaseSchema):
    """Project settings update schema."""

    settings: dict[str, Any] = Field(..., description="Settings to update")


# ======================
# Branch Schemas
# ======================


class BranchCreate(BaseSchema):
    """Branch creation request schema."""

    project_id: UUID = Field(..., description="Project ID")
    name: str = Field(..., min_length=1, max_length=255, description="Branch name")
    parent_branch_id: Optional[UUID] = Field(default=None, description="Parent branch ID")
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate branch name format."""
        if not v.replace("-", "_").replace("_", "").isalnum():
            raise ValueError("Branch name must contain only letters, numbers, hyphens, and underscores")
        return v.lower().replace("_", "-")


class BranchUpdate(BaseSchema):
    """Branch update request schema."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate branch status."""
        if v is None:
            return v
        if v not in [bs.value for bs in BranchStatus]:
            raise ValueError(f"Invalid status: {v}")
        return v


class BranchResponse(UUIDMixin, TimestampSchema):
    """Branch response schema."""

    project_id: UUID
    name: str
    parent_branch_id: Optional[UUID] = None
    description: Optional[str] = None
    status: str
    merged_at: Optional[datetime] = None
    merged_by: Optional[UUID] = None
    commit_count: Optional[int] = None


class BranchWithParent(BranchResponse):
    """Branch response with parent branch info."""

    parent_branch: Optional[BranchResponse] = None


class BranchMergeRequest(BaseSchema):
    """Branch merge request schema."""

    target_branch_id: UUID = Field(..., description="Target branch to merge into")
    source_branch_id: UUID = Field(..., description="Source branch to merge from")
    commit_message: Optional[str] = None


class BranchMergeResponse(BaseSchema):
    """Branch merge response schema."""

    success: bool
    source_branch: BranchResponse
    target_branch: BranchResponse
    merged_at: Optional[datetime] = None
    conflicts: Optional[List[dict[str, Any]]] = None


class BranchDiff(BaseSchema):
    """Branch diff response schema."""

    source_branch_id: UUID
    target_branch_id: UUID
    additions: int
    deletions: int
    modifications: List[dict[str, Any]]


# ======================
# Project Statistics
# ======================


class ProjectStats(BaseSchema):
    """Project statistics response schema."""

    project_id: UUID
    total_branches: int
    total_decisions: int
    total_artifacts: int
    completed_artifacts: int
    contributors: int
    last_activity: Optional[datetime] = None


class BranchStats(BaseSchema):
    """Branch statistics response schema."""

    branch_id: UUID
    total_decisions: int
    completed_decisions: int
    total_artifacts: int
    merged_decisions: int
    created_by: Optional[UUID] = None
    created_at: datetime
    last_activity: Optional[datetime] = None


# ======================
# Project Template Schemas
# ======================


class TemplateCreate(BaseSchema):
    """Template creation request schema."""

    workspace_id: UUID = Field(..., description="Workspace ID")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    questions: List[dict[str, Any]] = Field(default_factory=list)
    decisions: List[dict[str, Any]] = Field(default_factory=list)
    is_public: bool = Field(default=False)


class TemplateUpdate(BaseSchema):
    """Template update request schema."""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    questions: Optional[List[dict[str, Any]]] = None
    decisions: Optional[List[dict[str, Any]]] = None
    is_public: Optional[bool] = None


class TemplateResponse(UUIDMixin, TimestampSchema):
    """Template response schema."""

    workspace_id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    questions: List[dict[str, Any]]
    decisions: List[dict[str, Any]]
    is_public: bool
    usage_count: Optional[int] = None


class TemplateListResponse(BaseModel):
    """Template list response."""

    templates: List[TemplateResponse]
    total: int
    page: int
    page_size: int


class CreateProjectFromTemplate(BaseSchema):
    """Create project from template request."""

    template_id: UUID = Field(..., description="Template ID")
    project_name: str = Field(..., description="Name for the new project")
    project_description: Optional[str] = None
    branch_name: str = Field(default="main", description="Initial branch name")


# Update forward references
BranchWithParent.model_rebuild()
