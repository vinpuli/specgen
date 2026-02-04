"""
Decision and DecisionDependency models for specification decisions.

These models handle:
- Recording architectural and design decisions
- Tracking decision dependencies (prerequisites)
- Decision status and locking mechanism
- Conversation history for audit trail
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


class DecisionCategory(str, enum.Enum):
    """Categories for organizing decisions."""

    ARCHITECTURE = "architecture"
    DATABASE = "database"
    API = "api"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    FRAMEWORK = "framework"
    INTEGRATION = "integration"
    UX_UI = "ux_ui"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    OTHER = "other"


class DecisionStatus(str, enum.Enum):
    """Status for decision lifecycle."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_ANSWER = "awaiting_answer"
    ANSWERED = "answered"
    LOCKED = "locked"
    DEPRECATED = "deprecated"


class DecisionPriority(str, enum.Enum):
    """Priority levels for decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(Base):
    """
    Decision model for recording specification decisions.

    Attributes:
        id: Unique identifier (UUID primary key)
        project_id: Reference to parent Project
        branch_id: Reference to Branch (optional, for branched decisions)
        question_text: The original question posed
        answer_text: The final answer/decision made
        category: Decision category for organization
        status: Current decision status
        priority: Priority level
        is_locked: Whether the decision is locked (immutable)
        locked_by: User who locked the decision
        locked_at: Timestamp when decision was locked
        asked_by: User who asked the question
        answered_by: User who provided the answer
        ai_generated: Whether the answer was AI-generated
        metadata: Additional decision metadata
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_project_id", "project_id"),
        Index("ix_decisions_status", "status"),
        Index("ix_decisions_category", "category"),
        Index("ix_decisions_branch_id", "branch_id"),
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
    asked_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who asked the question",
    )
    answered_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who provided the answer",
    )

    # Decision content
    question_text = Column(
        Text,
        nullable=False,
        doc="The original question posed",
    )
    answer_text = Column(
        Text,
        nullable=True,
        doc="The final answer/decision made",
    )
    reasoning = Column(
        Text,
        nullable=True,
        doc="Reasoning behind the decision",
    )

    # Categorization
    category = Column(
        Enum(DecisionCategory),
        default=DecisionCategory.OTHER,
        nullable=False,
        doc="Decision category",
    )
    tags = Column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
        doc="Tags for filtering and organization",
    )

    # Status
    status = Column(
        Enum(DecisionStatus),
        default=DecisionStatus.PENDING,
        nullable=False,
        doc="Current decision status",
    )
    priority = Column(
        Enum(DecisionPriority),
        default=DecisionPriority.MEDIUM,
        nullable=False,
        doc="Priority level",
    )

    # Locking mechanism
    is_locked = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the decision is locked (immutable)",
    )
    locked_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who locked the decision",
    )
    locked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when decision was locked",
    )

    # AI assistance
    ai_generated = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the answer was AI-generated",
    )
    confidence_score = Column(
        Integer,  # 0-100
        nullable=True,
        doc="AI confidence score if applicable",
    )

    # Metadata
    metadata = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Additional decision metadata",
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
    answered_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when decision was answered",
    )

    # Relationships
    project = relationship(
        "Project",
        back_populates="decisions",
    )
    branch = relationship(
        "Branch",
        back_populates="decisions",
    )
    conversation_turns = relationship(
        "ConversationTurn",
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="ConversationTurn.created_at",
    )
    outgoing_dependencies = relationship(
        "DecisionDependency",
        back_populates="source_decision",
        foreign_keys="DecisionDependency.source_decision_id",
        cascade="all, delete-orphan",
    )
    incoming_dependencies = relationship(
        "DecisionDependency",
        back_populates="target_decision",
        foreign_keys="DecisionDependency.target_decision_id",
        cascade="all, delete-orphan",
    )
    based_on_artifacts = relationship(
        "Artifact",
        secondary="decision_artifacts",  # Association table
        back_populates="related_decisions",
    )

    def __repr__(self) -> str:
        return f"<Decision(id={self.id}, category={self.category}, status={self.status})>"

    @property
    def is_answered(self) -> bool:
        """Check if decision has been answered."""
        return self.status in (DecisionStatus.ANSWERED, DecisionStatus.LOCKED)

    @property
    def is_pending(self) -> bool:
        """Check if decision is still pending."""
        return self.status in (DecisionStatus.PENDING, DecisionStatus.IN_PROGRESS)

    def has_dependency_on(self, other_decision_id: uuid.UUID) -> bool:
        """Check if this decision depends on another decision."""
        return any(
            dep.target_decision_id == other_decision_id
            for dep in self.outgoing_dependencies
        )


class DecisionDependency(Base):
    """
    Decision dependency model for tracking prerequisite relationships.

    Attributes:
        id: Unique identifier (UUID primary key)
        source_decision_id: Decision that has the dependency
        target_decision_id: Decision that is the prerequisite
        dependency_type: Type of dependency (blocks, requires, relates_to)
        description: Description of the dependency relationship
        created_at: Record creation timestamp
    """

    __tablename__ = "decision_dependencies"
    __table_args__ = (
        Index("ix_decision_dependencies_source", "source_decision_id"),
        Index("ix_decision_dependencies_target", "target_decision_id"),
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
    source_decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
        doc="Decision that has the dependency",
    )
    target_decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
        doc="Decision that is the prerequisite",
    )

    # Dependency information
    dependency_type = Column(
        String(50),
        default="requires",
        nullable=False,
        doc="Type of dependency (blocks, requires, relates_to)",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Description of the dependency relationship",
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
    source_decision = relationship(
        "Decision",
        back_populates="outgoing_dependencies",
        foreign_keys=[source_decision_id],
    )
    target_decision = relationship(
        "Decision",
        back_populates="incoming_dependencies",
        foreign_keys=[target_decision_id],
    )

    def __repr__(self) -> str:
        return f"<DecisionDependency(source={self.source_decision_id}, target={self.target_decision_id})>"


# Association table for decision-artifact relationship
decision_artifacts = Table(
    "decision_artifacts",
    metadata,
    Column(
        "decision_id",
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "artifact_id",
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Import for relationship setup (avoid circular import)
from backend.db.models.conversation import ConversationTurn  # noqa: E402
from backend.db.models.artifact import Artifact  # noqa: E402
