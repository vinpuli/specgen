"""
Project and Branch models for specification projects.

These models handle:
- Project creation and management
- Greenfield vs brownfield project types
- Branch management for version control
- Project settings and metadata
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


class ProjectType(str, enum.Enum):
    """Project type for specification generation."""

    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"


class ProjectStatus(str, enum.Enum):
    """Project status for lifecycle tracking."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class BranchStatus(str, enum.Enum):
    """Branch status for version control."""

    ACTIVE = "active"
    MERGED = "merged"
    CLOSED = "closed"


class Project(Base):
    """
    Project model for specification generation.

    Attributes:
        id: Unique identifier (UUID primary key)
        workspace_id: Reference to parent Workspace
        name: Project display name
        description: Project description
        type: Greenfield or brownfield project
        status: Current project status
        settings: JSONB for project-specific settings
        created_by: Reference to User who created the project
        default_branch: Default branch name
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_workspace_id", "workspace_id"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_created_by", "created_by"),
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
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who created the project",
    )

    # Core fields
    name = Column(
        String(255),
        nullable=False,
        doc="Project display name",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Project description",
    )
    project_type = Column(
        Enum(ProjectType),
        nullable=False,
        doc="Greenfield or brownfield project",
    )
    status = Column(
        Enum(ProjectStatus),
        default=ProjectStatus.DRAFT,
        nullable=False,
        doc="Current project status",
    )

    # Brownfield-specific fields
    repository_url = Column(
        String(512),
        nullable=True,
        doc="Repository URL for brownfield projects",
    )
    repository_provider = Column(
        String(50),
        nullable=True,
        doc="Repository provider (github, gitlab)",
    )
    default_branch = Column(
        String(100),
        default="main",
        nullable=False,
        doc="Default branch name",
    )

    # Settings storage
    settings = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Project-specific settings",
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
    workspace = relationship(
        "Workspace",
        back_populates="projects",
    )
    creator = relationship(
        "User",
        back_populates="projects",
        foreign_keys=[created_by],
    )
    branches = relationship(
        "Branch",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    decisions = relationship(
        "Decision",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    artifacts = relationship(
        "Artifact",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    comments = relationship(
        "Comment",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    codebase_analyses = relationship(
        "CodebaseAnalysis",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, type={self.project_type})>"

    @property
    def is_brownfield(self) -> bool:
        """Check if this is a brownfield project."""
        return self.project_type == ProjectType.BROWNFIELD

    @property
    def is_greenfield(self) -> bool:
        """Check if this is a greenfield project."""
        return self.project_type == ProjectType.GREENFIELD

    @property
    def active_branches(self) -> List["Branch"]:
        """Get all active branches."""
        return [b for b in self.branches if b.status == BranchStatus.ACTIVE]

    @property
    def main_branch(self) -> Optional["Branch"]:
        """Get the main/default branch."""
        return next((b for b in self.branches if b.name == self.default_branch), None)


class Branch(Base):
    """
    Branch model for version control within projects.

    Attributes:
        id: Unique identifier (UUID primary key)
        project_id: Reference to parent Project
        name: Branch name
        description: Branch description
        parent_branch_id: Reference to parent Branch for branching
        status: Current branch status
        is_protected: Whether branch protection is enabled
        mergeable: Whether the branch can be merged
        created_by: Reference to User who created the branch
        merged_at: Timestamp when branch was merged
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "branches"
    __table_args__ = (
        Index("ix_branches_project_id", "project_id"),
        Index("ix_branches_status", "status"),
        Index("ix_branches_name", "name"),
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
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        doc="Project ID",
    )
    parent_branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        doc="Parent branch ID for branching",
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who created the branch",
    )

    # Core fields
    name = Column(
        String(100),
        nullable=False,
        doc="Branch name",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Branch description",
    )
    status = Column(
        Enum(BranchStatus),
        default=BranchStatus.ACTIVE,
        nullable=False,
        doc="Current branch status",
    )

    # Branch protection
    is_protected = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether branch protection is enabled",
    )

    # Merge tracking
    mergeable = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the branch can be merged",
    )
    merged_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when branch was merged",
    )
    merge_conflicts = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="List of merge conflicts if any",
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
    project = relationship(
        "Project",
        back_populates="branches",
    )
    parent_branch = relationship(
        "Branch",
        remote_side=[id],
        back_populates="child_branches",
    )
    child_branches = relationship(
        "Branch",
        remote_side=[parent_branch_id],
        back_populates="parent_branch",
    )
    decisions = relationship(
        "Decision",
        back_populates="branch",
        cascade="all, delete-orphan",
    )
    artifacts = relationship(
        "Artifact",
        back_populates="branch",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Branch(id={self.id}, name={self.name}, project_id={self.project_id})>"

    def is_main(self) -> bool:
        """Check if this is the main branch."""
        return self.project and self.name == self.project.default_branch


# Import for relationship setup (avoid circular import)
from backend.db.models.decision import Decision  # noqa: E402
from backend.db.models.artifact import Artifact  # noqa: E402
from backend.db.models.comment import Comment  # noqa: E402
from backend.db.models.codebase import CodebaseAnalysis  # noqa: E402
