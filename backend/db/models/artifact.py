"""
Artifact and ArtifactVersion models for generated specifications.

These models handle:
- Storing generated artifacts (PRD, API specs, etc.)
- Version control for artifacts
- Tracking artifacts based on decisions
- Export and regeneration management
"""

import enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSONB,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.base import Base
from backend.db.meta import metadata


class ArtifactType(str, enum.Enum):
    """Types of artifacts that can be generated."""

    PRD = "prd"
    API_SPEC = "api_spec"
    DATABASE_SCHEMA = "database_schema"
    ARCHITECTURE = "architecture"
    TICKETS = "tickets"
    TESTS = "tests"
    DEPLOYMENT = "deployment"
    OPENAPI = "openapi"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    CUSTOM = "custom"


class ArtifactFormat(str, enum.Enum):
    """Export formats for artifacts."""

    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    HTML = "html"
    PDF = "pdf"
    PLAINTEXT = "plaintext"
    OPENAPI_JSON = "openapi_json"
    OPENAPI_YAML = "openapi_yaml"


class ArtifactStatus(str, enum.Enum):
    """Status for artifact generation lifecycle."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    REGENERATING = "regenerating"


class Artifact(Base):
    """
    Artifact model for generated specifications.

    Attributes:
        id: Unique identifier (UUID primary key)
        project_id: Reference to parent Project
        branch_id: Reference to Branch (optional)
        type: Type of artifact (PRD, API spec, etc.)
        title: Artifact display title
        description: Artifact description
        content: The artifact content (JSONB for flexible storage)
        format: Export format (markdown, json, yaml, etc.)
        status: Current generation status
        version: Current version number
        is_latest: Whether this is the latest version
        generated_by: User or AI that generated the artifact
        file_size: Size of the content in bytes
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "artifacts"
    __table_args__ = (
        Index("ix_artifacts_project_id", "project_id"),
        Index("ix_artifacts_type", "type"),
        Index("ix_artifacts_status", "status"),
        Index("ix_artifacts_branch_id", "branch_id"),
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
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=True,
        doc="Branch ID for branched projects",
    )
    generated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User or AI that generated the artifact",
    )

    # Artifact content
    artifact_type = Column(
        Enum(ArtifactType),
        nullable=False,
        doc="Type of artifact",
    )
    title = Column(
        String(255),
        nullable=False,
        doc="Artifact display title",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Artifact description",
    )
    content = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="The artifact content (flexible JSONB storage)",
    )
    format = Column(
        Enum(ArtifactFormat),
        default=ArtifactFormat.MARKDOWN,
        nullable=False,
        doc="Export format",
    )

    # Status and versioning
    status = Column(
        Enum(ArtifactStatus),
        default=ArtifactStatus.PENDING,
        nullable=False,
        doc="Current generation status",
    )
    version = Column(
        Integer,
        default=1,
        nullable=False,
        doc="Current version number",
    )
    is_latest = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether this is the latest version",
    )

    # Metadata
    file_size = Column(
        Integer,
        nullable=True,
        doc="Size of the content in bytes",
    )
    checksum = Column(
        String(64),
        nullable=True,
        doc="SHA-256 checksum of content",
    )
    metadata = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Additional artifact metadata",
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
    generated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when generation completed",
    )

    # Relationships
    project = relationship(
        "Project",
        back_populates="artifacts",
    )
    branch = relationship(
        "Branch",
        back_populates="artifacts",
    )
    versions = relationship(
        "ArtifactVersion",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )
    comments = relationship(
        "Comment",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )
    related_decisions = relationship(
        "Decision",
        secondary="decision_artifacts",
        back_populates="based_on_artifacts",
    )

    def __repr__(self) -> str:
        return f"<Artifact(id={self.id}, type={self.artifact_type}, version={self.version})>"

    @property
    def content_text(self) -> str:
        """Get content as formatted text."""
        import json

        if self.format in (ArtifactFormat.JSON, ArtifactFormat.YAML):
            return json.dumps(self.content, indent=2)
        return str(self.content)


class ArtifactVersion(Base):
    """
    Artifact version model for version control.

    Attributes:
        id: Unique identifier (UUID primary key)
        artifact_id: Reference to parent Artifact
        version: Version number
        content: Previous version content (JSONB)
        changelog: Description of changes from previous version
        created_by: User who created this version
        created_at: Record creation timestamp
    """

    __tablename__ = "artifact_versions"
    __table_args__ = (
        Index("ix_artifact_versions_artifact_id", "artifact_id"),
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
    artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        doc="Parent artifact ID",
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who created this version",
    )

    # Version content
    version = Column(
        Integer,
        nullable=False,
        doc="Version number",
    )
    content = Column(
        JSONB,
        nullable=False,
        doc="Previous version content",
    )
    changelog = Column(
        Text,
        nullable=True,
        doc="Description of changes from previous version",
    )

    # Timestamp
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        server_default="NOW()",
        doc="Record creation timestamp",
    )

    # Relationships
    artifact = relationship(
        "Artifact",
        back_populates="versions",
    )

    def __repr__(self) -> str:
        return f"<ArtifactVersion(id={self.id}, artifact_id={self.artifact_id}, version={self.version})>"


# Import for relationship setup (avoid circular import)
from backend.db.models.decision import decision_artifacts  # noqa: E402
from backend.db.models.comment import Comment  # noqa: E402
