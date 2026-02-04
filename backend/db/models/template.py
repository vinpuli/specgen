"""
Template model for reusable project templates.

This model handles:
- Storing reusable project templates
- Template categories and metadata
- Versioning of templates
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


class TemplateCategory(str, enum.Enum):
    """Categories for project templates."""

    WEB_APPLICATION = "web_application"
    API_SERVICE = "api_service"
    MICROSERVICE = "microservice"
    MOBILE_APP = "mobile_app"
    CLI_TOOL = "cli_tool"
    LIBRARY = "library"
    FULL_STACK = "full_stack"
    DATA_PIPELINE = "data_pipeline"
    MACHINE_LEARNING = "machine_learning"
    CUSTOM = "custom"


class Template(Base):
    """
    Template model for reusable project templates.

    Attributes:
        id: Unique identifier (UUID primary key)
        workspace_id: Reference to Workspace (null for global templates)
        name: Template display name
        description: Template description
        category: Template category
        content: Template content (JSONB for flexibility)
        default_decisions: Pre-defined decisions for the template
        tags: Tags for filtering
        is_public: Whether template is publicly available
        is_featured: Whether template is featured
        usage_count: Number of times template was used
        version: Template version number
        created_by: User who created the template
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "templates"
    __table_args__ = (
        Index("ix_templates_workspace_id", "workspace_id"),
        Index("ix_templates_category", "category"),
        Index("ix_templates_name", "name"),
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
        nullable=True,
        doc="Workspace ID (null for global templates)",
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who created the template",
    )

    # Template content
    name = Column(
        String(255),
        nullable=False,
        doc="Template display name",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Template description",
    )
    category = Column(
        Enum(TemplateCategory),
        default=TemplateCategory.CUSTOM,
        nullable=False,
        doc="Template category",
    )
    content = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Template content (flexible JSONB storage)",
    )
    default_decisions = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Pre-defined decisions for the template",
    )

    # Metadata
    tags = Column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
        doc="Tags for filtering",
    )
    technologies = Column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
        doc="Technologies used in the template",
    )

    # Visibility and status
    is_public = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether template is publicly available",
    )
    is_featured = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether template is featured",
    )

    # Usage statistics
    usage_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of times template was used",
    )
    rating = Column(
        Integer,  # 1-5
        nullable=True,
        doc="Average user rating",
    )

    # Versioning
    version = Column(
        Integer,
        default=1,
        nullable=False,
        doc="Template version number",
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
        back_populates="templates",
    )

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, name={self.name}, category={self.category})>"


# Import for relationship setup (avoid circular import)
from backend.db.models.workspace import Workspace  # noqa: E402
