"""
Workspace and WorkspaceMember Pydantic schemas.

This module provides:
- Workspace creation, update, and response schemas
- Workspace membership schemas
- Role and permission schemas
"""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin
from backend.api.schemas.user import UserResponse


# ======================
# Enums
# ======================


class WorkspaceRole(str, str):
    """Workspace membership roles."""

    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

    @classmethod
    def can_edit(cls) -> List[str]:
        """Roles that can edit workspace content."""
        return [cls.OWNER, cls.ADMIN, cls.EDITOR]

    @classmethod
    def can_admin(cls) -> List[str]:
        """Roles that have admin privileges."""
        return [cls.OWNER, cls.ADMIN]


class PlanTier(str, str):
    """Workspace subscription plan tiers."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# ======================
# Workspace Schemas
# ======================


class WorkspaceCreate(BaseSchema):
    """Workspace creation request schema."""

    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    slug: str = Field(
        ..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$", description="URL-friendly identifier"
    )
    description: Optional[str] = Field(default=None, description="Workspace description")
    settings: Optional[dict[str, Any]] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format."""
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Slug must contain only lowercase letters, numbers, hyphens, and underscores")
        return v.lower()


class WorkspaceUpdate(BaseSchema):
    """Workspace update request schema."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    settings: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class WorkspaceSettingsUpdate(BaseSchema):
    """Workspace settings update schema."""

    settings: dict[str, Any] = Field(..., description="Settings to update")


class WorkspaceResponse(UUIDMixin, TimestampSchema):
    """Workspace response schema."""

    name: str
    slug: str
    description: Optional[str] = None
    owner_id: UUID
    plan_tier: str
    settings: dict[str, Any]
    is_active: bool
    member_count: Optional[int] = None


class WorkspaceWithOwner(WorkspaceResponse):
    """Workspace response with owner info."""

    owner: UserResponse


class WorkspaceWithMembers(WorkspaceResponse):
    """Workspace response with members list."""

    members: List["WorkspaceMemberResponse"]


class WorkspaceListResponse(BaseModel):
    """Workspace list response with pagination."""

    workspaces: List[WorkspaceResponse]
    total: int
    page: int
    page_size: int


# ======================
# Workspace Member Schemas
# ======================


class WorkspaceMemberCreate(BaseSchema):
    """Workspace member invitation schema."""

    email: str = Field(..., description="Email of user to invite")
    role: str = Field(default="viewer", description="Role to assign")
    invited_by: Optional[UUID] = None  # Set from current user

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role."""
        try:
            WorkspaceRole(v)
        except ValueError:
            raise ValueError(f"Invalid role: {v}. Must be one of: owner, admin, editor, viewer")
        return v


class WorkspaceMemberUpdate(BaseSchema):
    """Workspace member update schema."""

    role: str = Field(..., description="New role for member")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role."""
        try:
            WorkspaceRole(v)
        except ValueError:
            raise ValueError(f"Invalid role: {v}. Must be one of: owner, admin, editor, viewer")
        return v


class WorkspaceMemberResponse(UUIDMixin, TimestampSchema):
    """Workspace member response schema."""

    workspace_id: UUID
    user_id: UUID
    role: str
    is_active: bool
    invited_by: Optional[UUID] = None
    joined_at: datetime


class WorkspaceMemberWithUser(WorkspaceMemberResponse):
    """Workspace member response with user info."""

    user: UserResponse


class WorkspaceMemberInviteResponse(BaseSchema):
    """Invite response schema."""

    invitation_id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime


class WorkspaceMemberRemove(BaseSchema):
    """Remove member request schema."""

    user_id: UUID = Field(..., description="User ID to remove")


class WorkspaceMemberLeave(BaseSchema):
    """Leave workspace request schema."""

    pass


class BulkInviteRequest(BaseSchema):
    """Bulk invite request schema."""

    invites: List[WorkspaceMemberCreate]


class BulkInviteResponse(BaseSchema):
    """Bulk invite response schema."""

    successful: List[WorkspaceMemberInviteResponse]
    failed: List[dict[str, Any]]


# ======================
# Permission Schemas
# ======================


class PermissionCheck(BaseSchema):
    """Permission check request schema."""

    action: str = Field(..., description="Action to check (create, read, update, delete)")
    resource: str = Field(..., description="Resource type (project, artifact, etc.)")
    resource_id: Optional[UUID] = None


class PermissionResponse(BaseSchema):
    """Permission check response schema."""

    allowed: bool
    reason: Optional[str] = None


class RolePermissions(BaseSchema):
    """Role permissions mapping schema."""

    role: str
    permissions: List[str]


# ======================
# Workspace Invitation Schemas
# ======================


class WorkspaceInvitationAccept(BaseSchema):
    """Accept invitation request schema."""

    invitation_token: str = Field(..., description="Invitation token")


class WorkspaceInvitationDecline(BaseSchema):
    """Decline invitation request schema."""

    reason: Optional[str] = None


# ======================
# Update forward references
# ======================

WorkspaceMemberWithUser.model_rebuild()
