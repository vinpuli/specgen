"""
Comment and ConversationTurn models for collaboration.

These models handle:
- Threaded comments on artifacts
- Conversation history for decisions (audit trail)
- Real-time comment updates
- Agent re-questioning triggers
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
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.base import Base
from backend.db.meta import metadata


class CommentType(str, enum.Enum):
    """Types of comments for categorization."""

    QUESTION = "question"
    SUGGESTION = "suggestion"
    ISSUE = "issue"
    PRAISE = "praise"
    CLARIFICATION = "clarification"
    CONTRADICTION = "contradiction"
    AI_REVIEW = "ai_review"


class CommentStatus(str, enum.Enum):
    """Status for comment lifecycle."""

    OPEN = "open"
    RESOLVED = "resolved"
    WONTFIX = "wontfix"
    ARCHIVED = "archived"


class Comment(Base):
    """
    Comment model for threaded discussions on artifacts.

    Attributes:
        id: Unique identifier (UUID primary key)
        project_id: Reference to parent Project
        artifact_id: Reference to Artifact (optional)
        decision_id: Reference to Decision (optional)
        parent_comment_id: Reference to parent Comment for threads
        author_id: Reference to User who wrote the comment
        type: Type of comment
        content: Comment text content
        status: Current comment status
        is_ai_generated: Whether the comment was AI-generated
        resolve_requested: Whether resolution is requested
        re_question_triggered: Whether agent re-questioning was triggered
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
        resolved_at: Timestamp when comment was resolved
    """

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_project_id", "project_id"),
        Index("ix_comments_artifact_id", "artifact_id"),
        Index("ix_comments_decision_id", "decision_id"),
        Index("ix_comments_parent_id", "parent_comment_id"),
        Index("ix_comments_author_id", "author_id"),
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
    artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=True,
        doc="Artifact ID (optional)",
    )
    decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=True,
        doc="Decision ID (optional)",
    )
    parent_comment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        doc="Parent comment ID for threading",
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who wrote the comment",
    )

    # Comment content
    comment_type = Column(
        Enum(CommentType),
        default=CommentType.SUGGESTION,
        nullable=False,
        doc="Type of comment",
    )
    content = Column(
        Text,
        nullable=False,
        doc="Comment text content",
    )

    # Status
    status = Column(
        Enum(CommentStatus),
        default=CommentStatus.OPEN,
        nullable=False,
        doc="Current comment status",
    )

    # AI and resolution flags
    is_ai_generated = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the comment was AI-generated",
    )
    resolve_requested = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether resolution is requested",
    )
    re_question_triggered = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether agent re-questioning was triggered",
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
    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when comment was resolved",
    )
    resolved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who resolved the comment",
    )

    # Relationships
    project = relationship(
        "Project",
        back_populates="comments",
    )
    artifact = relationship(
        "Artifact",
        back_populates="comments",
    )
    decision = relationship(
        "Comment",
        remote_side=[id],
    )
    parent = relationship(
        "Comment",
        remote_side=[id],
        back_populates="replies",
    )
    replies = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )
    author = relationship(
        "User",
        back_populates="comments",
        foreign_keys=[author_id],
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, type={self.comment_type}, status={self.status})>"

    @property
    def is_thread(self) -> bool:
        """Check if this comment has replies (is a thread parent)."""
        return len(self.replies) > 0

    @property
    def reply_count(self) -> int:
        """Get number of replies."""
        return len(self.replies)

    def is_owned_by(self, user_id: uuid.UUID) -> bool:
        """Check if comment is owned by given user."""
        return self.author_id == user_id


class ConversationTurn(Base):
    """
    Conversation turn model for audit trail of questions and answers.

    Attributes:
        id: Unique identifier (UUID primary key)
        decision_id: Reference to parent Decision
        turn_number: Order of the turn in conversation
        role: Role of the speaker (user, ai, system)
        content: Turn content (question, answer, or reasoning)
        is_ai_generated: Whether content was AI-generated
        metadata: Additional turn metadata
        created_at: Record creation timestamp
    """

    __tablename__ = "conversation_turns"
    __table_args__ = (
        Index("ix_conversation_turns_decision_id", "decision_id"),
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
    decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
        doc="Parent decision ID",
    )

    # Turn content
    turn_number = Column(
        Integer,
        nullable=False,
        doc="Order of the turn in conversation",
    )
    role = Column(
        String(20),
        nullable=False,
        doc="Role of the speaker (user, ai, system)",
    )
    content = Column(
        Text,
        nullable=False,
        doc="Turn content",
    )

    # AI flags
    is_ai_generated = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether content was AI-generated",
    )
    model_name = Column(
        String(100),
        nullable=True,
        doc="AI model used for generation",
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
        doc="Additional turn metadata",
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
    decision = relationship(
        "Decision",
        back_populates="conversation_turns",
    )

    def __repr__(self) -> str:
        return f"<ConversationTurn(id={self.id}, decision_id={self.decision_id}, role={self.role})>"


# Import for relationship setup (avoid circular import)
from backend.db.models.project import Project  # noqa: E402
from backend.db.models.artifact import Artifact  # noqa: E402
from backend.db.models.decision import Decision  # noqa: E402
from backend.db.models.user import User  # noqa: E402
