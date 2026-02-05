"""
Workspace Pydantic schemas for API requests and responses.

This module provides:
- Workspace creation, update, and response schemas
- Workspace membership schemas
- Role-based access control schemas
"""

import enum
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin


class WorkspaceRole(str, enum.Enum):
    """Workspace membership roles."""

    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class PlanTier(str, enum.Enum):
    """Workspace subscription plan tiers."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# ======================
# Request Schemas
# ======================


class WorkspaceCreate(BaseModel):
    """Workspace creation request schema."""

    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-friendly identifier")
    description: Optional[str] = Field(default=None, description="Workspace description")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format."""
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Slug must be alphanumeric with hyphens or underscores")
        return v.lower()


class WorkspaceUpdate(BaseModel):
    """Workspace update request schema."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    settings: Optional[dict] = Field(default=None)


class WorkspaceSettingsUpdate(BaseModel):
    """Workspace settings update request schema."""

    settings: dict = Field(..., description="Settings to update")


class WorkspaceMemberInvite(BaseModel):
    """Workspace member invitation request schema."""

    email: str = Field(..., description="Email of user to invite")
    role: WorkspaceRole = Field(..., description="Role to assign")


class WorkspaceMemberUpdate(BaseModel):
    """Workspace member role update request schema."""

    role: WorkspaceRole = Field(..., description="New role to assign")


# ======================
# Response Schemas
# ======================


class WorkspaceResponse(UUIDMixin, TimestampSchema):
    """Workspace response schema."""

    name: str
    slug: str
    description: Optional[str] = None
    owner_id: UUID
    plan_tier: PlanTier
    settings: dict
    is_active: bool
    member_count: Optional[int] = None


class WorkspaceDetailResponse(WorkspaceResponse):
    """Detailed workspace response with members."""

    members: List["WorkspaceMemberResponse"] = Field(default_factory=list)


class WorkspaceMemberResponse(UUIDMixin):
    """Workspace member response schema."""

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    is_active: bool
    joined_at: datetime
    invited_by: Optional[UUID] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class WorkspaceMemberWithPermissions(WorkspaceMemberResponse):
    """Workspace member response with permission flags."""

    can_edit: bool
    can_admin: bool
    can_delete: bool
    can_invite: bool
    can_remove_member: bool
    can_change_role: bool


class WorkspaceInviteResponse(BaseModel):
    """Workspace invite response schema."""

    message: str
    membership: WorkspaceMemberResponse


class WorkspaceRoleResponse(BaseModel):
    """Workspace role info response schema."""

    role: WorkspaceRole
    description: str
    permissions: list[str]


# ======================
# Permission Schemas
# ======================


class PermissionCheck(BaseModel):
    """Permission check request schema."""

    action: str = Field(..., description="Action to check (view, edit, admin, invite, etc.)")


class PermissionCheckResponse(BaseModel):
    """Permission check response schema."""

    allowed: bool
    reason: Optional[str] = None


# Update forward references
WorkspaceMemberResponse.model_rebuild()
