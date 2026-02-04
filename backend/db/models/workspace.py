"""
Workspace and WorkspaceMember models for multi-tenant organization.

These models handle:
- Workspace/tenant management
- Role-based access control
- Membership management
- Workspace settings
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSONB,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.base import Base
from backend.db.meta import metadata


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


class Workspace(Base):
    """
    Workspace model for multi-tenant organization.

    Attributes:
        id: Unique identifier (UUID primary key)
        name: Workspace display name
        slug: URL-friendly identifier (unique)
        description: Workspace description
        owner_id: Reference to User who owns the workspace
        plan_tier: Subscription plan tier
        settings: JSONB for flexible settings
        is_active: Whether the workspace is active
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "workspaces"
    __table_args__ = (
        Index("ix_workspaces_slug", "slug"),
        Index("ix_workspaces_owner_id", "owner_id"),
        {"schema": "public"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=Text("gen_random_uuid()"),
    )

    # Core fields
    name = Column(
        String(255),
        nullable=False,
        doc="Workspace display name",
    )
    slug = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        doc="URL-friendly identifier",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Workspace description",
    )

    # Owner reference
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="User ID of workspace owner",
    )

    # Plan and billing
    plan_tier = Column(
        Enum(PlanTier),
        default=PlanTier.FREE,
        nullable=False,
        doc="Subscription plan tier",
    )

    # Flexible settings storage
    settings = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Workspace settings (theme, features, integrations)",
    )

    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the workspace is active",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        server_default="NOW()",
        doc="Record creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        server_default="NOW()",
        doc="Record last update timestamp",
    )

    # Relationships
    owner = relationship(
        "User",
        back_populates="owned_workspaces",
        foreign_keys=[owner_id],
    )
    members = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="WorkspaceMember.joined_at",
    )
    projects = relationship(
        "Project",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    templates = relationship(
        "Template",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name}, slug={self.slug})>"

    @property
    def member_count(self) -> int:
        """Get total number of members including owner."""
        return len(self.members) + 1

    @property
    def is_free_tier(self) -> bool:
        """Check if workspace is on free tier."""
        return self.plan_tier == PlanTier.FREE


class WorkspaceMember(Base):
    """
    Workspace membership model for role-based access control.

    Attributes:
        id: Unique identifier (UUID primary key)
        workspace_id: Reference to Workspace
        user_id: Reference to User
        role: Member's role in the workspace
        invited_by: User who sent the invitation
        is_active: Whether membership is active
        joined_at: Timestamp when user joined
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "workspace_members"
    __table_args__ = (
        Index("ix_workspace_members_workspace_id", "workspace_id"),
        Index("ix_workspace_members_user_id", "user_id"),
        {"schema": "public"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=Text("gen_random_uuid()"),
    )

    # Foreign keys
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        doc="Workspace ID",
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="User ID",
    )
    invited_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User who sent the invitation",
    )

    # Role
    role = Column(
        Enum(WorkspaceRole),
        default=WorkspaceRole.VIEWER,
        nullable=False,
        doc="Member's role in the workspace",
    )

    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the membership is active",
    )

    # Timestamps
    joined_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp when user accepted/joined",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        server_default="NOW()",
        doc="Record creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        server_default="NOW()",
        doc="Record last update timestamp",
    )

    # Relationships
    workspace = relationship(
        "Workspace",
        back_populates="members",
    )
    user = relationship(
        "User",
        back_populates="workspace_members",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return f"<WorkspaceMember(workspace_id={self.workspace_id}, user_id={self.user_id}, role={self.role})>"

    def can_edit(self) -> bool:
        """Check if member can edit workspace content."""
        return self.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR)

    def can_admin(self) -> bool:
        """Check if member has admin privileges."""
        return self.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


# Import for relationship setup (avoid circular import)
from backend.db.models.user import User  # noqa: E402
