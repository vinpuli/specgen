"""
Artifact and ArtifactVersion Pydantic schemas.

This module provides:
- Artifact creation, update, and response schemas
- Artifact version schemas
- Artifact type enums
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin
from backend.api.schemas.decision import DecisionResponse


# ======================
# Enums
# ======================


class ArtifactType(str, Enum):
    """Artifact type enum."""

    PRD = "prd"
    ARCHITECTURE = "architecture"
    API_SPEC = "api_spec"
    DATABASE_SCHEMA = "database_schema"
    USER_STORY = "user_story"
    REQUIREMENTS = "requirements"
    TECHNICAL_DOC = "technical_doc"
    README = "readme"
    DIAGRAM = "diagram"
    OTHER = "other"


class ArtifactFormat(str, Enum):
    """Artifact format enum."""

    MARKDOWN = "markdown"
    YAML = "yaml"
    JSON = "json"
    TEXT = "text"
    HTML = "html"
    PLANTUML = "plantuml"
    MERMAID = "mermaid"


class ArtifactStatus(str, Enum):
    """Artifact status enum."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


# ======================
# Artifact Schemas
# ======================


class ArtifactCreate(BaseSchema):
    """Artifact creation request schema."""

    branch_id: UUID = Field(..., description="Branch ID")
    name: str = Field(..., min_length=1, max_length=255, description="Artifact name")
    artifact_type: str = Field(..., description="Artifact type")
    format: str = Field(default="markdown", description="Content format")
    content: str = Field(..., description="Artifact content")
    based_on_decisions: Optional[List[UUID]] = Field(
        default=None, description="IDs of decisions this artifact is based on"
    )
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Additional metadata")

    @field_validator("artifact_type")
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        """Validate artifact type."""
        if v not in [at.value for at in ArtifactType]:
            raise ValueError(f"Invalid artifact type: {v}")
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate artifact format."""
        if v not in [af.value for af in ArtifactFormat]:
            raise ValueError(f"Invalid format: {v}")
        return v


class ArtifactUpdate(BaseSchema):
    """Artifact update request schema."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate artifact status."""
        if v is None:
            return v
        if v not in [s.value for s in ArtifactStatus]:
            raise ValueError(f"Invalid status: {v}")
        return v


class ArtifactResponse(UUIDMixin, TimestampSchema):
    """Artifact response schema."""

    branch_id: UUID
    name: str
    artifact_type: str
    format: str
    status: str
    metadata: Optional[dict[str, Any]] = None
    created_by: Optional[UUID] = None
    current_version: int = 1
    based_on_decisions: Optional[List[UUID]] = None


class ArtifactDetail(ArtifactResponse):
    """Artifact detail response with full content."""

    content: str
    versions: Optional[List["ArtifactVersionResponse"]] = None
    decisions: Optional[List[DecisionResponse]] = None


class ArtifactListResponse(BaseModel):
    """Artifact list response with pagination."""

    artifacts: List[ArtifactResponse]
    total: int
    page: int
    page_size: int


class ArtifactFilter(BaseModel):
    """Artifact filter parameters."""

    branch_id: Optional[UUID] = None
    artifact_type: Optional[str] = None
    status: Optional[str] = None
    created_by: Optional[UUID] = None
    search: Optional[str] = None


# ======================
# Artifact Version Schemas
# ======================


class ArtifactVersionCreate(BaseSchema):
    """Artifact version creation request schema."""

    content: str = Field(..., description="New version content")
    version_message: Optional[str] = Field(
        default=None, description="Description of changes in this version"
    )


class ArtifactVersionResponse(BaseSchema):
    """Artifact version response schema."""

    id: UUID
    artifact_id: UUID
    version: int
    content: str
    version_message: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime


class ArtifactVersionDetail(ArtifactVersionResponse):
    """Artifact version with full info."""

    diff_from_previous: Optional[str] = None


class ArtifactVersionListResponse(BaseModel):
    """Artifact version list response with pagination."""

    versions: List[ArtifactVersionResponse]
    total: int
    page: int
    page_size: int


# ======================
# Artifact Generation
# ======================


class GenerateArtifactRequest(BaseSchema):
    """Request to generate an artifact using AI."""

    branch_id: UUID = Field(..., description="Branch ID")
    artifact_type: str = Field(..., description="Type of artifact to generate")
    format: str = Field(default="markdown", description="Output format")
    context: Optional[str] = Field(default=None, description="Additional context for generation")
    decisions: Optional[List[UUID]] = Field(
        default=None, description="Decision IDs to base artifact on"
    )
    template_id: Optional[UUID] = Field(default=None, description="Template to use")


class GenerateArtifactResponse(BaseSchema):
    """Response with AI-generated artifact."""

    name: str
    artifact_type: str
    format: str
    content: str
    metadata: Optional[dict[str, Any]] = None
    confidence_score: float


# ======================
# Artifact Export
# ======================


class ExportArtifactRequest(BaseSchema):
    """Export artifact request schema."""

    artifact_id: UUID = Field(..., description="Artifact to export")
    format: str = Field(default="markdown", description="Export format")
    include_metadata: bool = Field(default=False, description="Include metadata in export")


class ExportArtifactResponse(BaseSchema):
    """Export artifact response schema."""

    content: str
    format: str
    filename: str
    content_type: str


# ======================
# Artifact Collaboration
# ======================


class ArtifactCommentCreate(BaseSchema):
    """Add comment to artifact request schema."""

    content: str = Field(..., min_length=1, description="Comment content")
    line_reference: Optional[str] = Field(
        default=None, description="Line or section reference"
    )


class ArtifactCommentResponse(BaseSchema):
    """Artifact comment response schema."""

    id: UUID
    artifact_id: UUID
    user_id: UUID
    content: str
    line_reference: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Update forward references
ArtifactDetail.model_rebuild()
