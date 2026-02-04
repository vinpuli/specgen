"""
AuditLog model for compliance and debugging.

This model handles:
- Comprehensive audit trail of all actions
- User activity tracking
- Security event logging
- Compliance requirements
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
    JSONB,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.base import Base
from backend.db.meta import metadata


class AuditAction(str, enum.Enum):
    """Audit action types for categorization."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    OAUTH_CONNECT = "oauth_connect"
    OAUTH_DISCONNECT = "oauth_disconnect"

    # User Management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_VERIFY = "user_verify"

    # Workspace
    WORKSPACE_CREATE = "workspace_create"
    WORKSPACE_UPDATE = "workspace_update"
    WORKSPACE_DELETE = "workspace_delete"
    WORKSPACE_JOIN = "workspace_join"
    WORKSPACE_LEAVE = "workspace_leave"
    WORKSPACE_INVITE = "workspace_invite"
    WORKSPACE_ROLE_CHANGE = "workspace_role_change"

    # Project
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"
    PROJECT_ARCHIVE = "project_archive"

    # Decision
    DECISION_CREATE = "decision_create"
    DECISION_UPDATE = "decision_update"
    DECISION_ANSWER = "decision_answer"
    DECISION_LOCK = "decision_lock"
    DECISION_UNLOCK = "decision_unlock"
    DECISION_DEPENDENCY_ADD = "decision_dependency_add"
    DECISION_DEPENDENCY_REMOVE = "decision_dependency_remove"

    # Branch
    BRANCH_CREATE = "branch_create"
    BRANCH_MERGE = "branch_merge"
    BRANCH_DELETE = "branch_delete"
    BRANCH_CONFLICT = "branch_conflict"

    # Artifact
    ARTIFACT_GENERATE = "artifact_generate"
    ARTIFACT_UPDATE = "artifact_update"
    ARTIFACT_DELETE = "artifact_delete"
    ARTIFACT_EXPORT = "artifact_export"
    ARTIFACT_VERSION = "artifact_version"
    ARTIFACT_ROLLBACK = "artifact_rollback"

    # Comment
    COMMENT_CREATE = "comment_create"
    COMMENT_UPDATE = "comment_update"
    COMMENT_DELETE = "comment_delete"
    COMMENT_RESOLVE = "comment_resolve"

    # Brownfield
    CODEBASE_ANALYZE = "codebase_analyze"
    IMPACT_ANALYZE = "impact_analyze"
    CHANGE_PLAN_GENERATE = "change_plan_generate"

    # Admin
    ADMIN_ACTION = "admin_action"
    DATA_EXPORT = "data_export"
    DATA_DELETE = "data_delete"


class AuditLog(Base):
    """
    Audit log model for compliance and debugging.

    Attributes:
        id: Unique identifier (UUID primary key)
        user_id: Reference to User who performed the action
        action: Type of action performed
        resource_type: Type of resource affected
        resource_id: ID of the resource affected
        workspace_id: Workspace context (if applicable)
        project_id: Project context (if applicable)
        details: Detailed information about the action
        ip_address: IP address of the request
        user_agent: User agent string
        request_id: Request ID for tracing
        success: Whether the action was successful
        error_message: Error message if action failed
        created_at: Record creation timestamp
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_resource_id", "resource_id"),
        Index("ix_audit_logs_workspace_id", "workspace_id"),
        Index("ix_audit_logs_created_at", "created_at"),
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
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User ID who performed the action",
    )
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        doc="Workspace context",
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        doc="Project context",
    )

    # Action details
    action = Column(
        Enum(AuditAction),
        nullable=False,
        doc="Type of action performed",
    )
    resource_type = Column(
        String(50),
        nullable=True,
        doc="Type of resource affected",
    )
    resource_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        doc="ID of the resource affected",
    )

    # Result
    success = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the action was successful",
    )
    error_message = Column(
        Text,
        nullable=True,
        doc="Error message if action failed",
    )

    # Request context
    ip_address = Column(
        String(45),  # IPv6 max length
        nullable=True,
        doc="IP address of the request",
    )
    user_agent = Column(
        String(512),
        nullable=True,
        doc="User agent string",
    )
    request_id = Column(
        String(100),
        nullable=True,
        doc="Request ID for tracing",
    )
    session_id = Column(
        String(100),
        nullable=True,
        doc="Session ID",
    )

    # Additional details
    details = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Detailed information about the action",
    )
    changes = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Changes made (before/after for updates)",
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
    user = relationship(
        "User",
        back_populates="audit_logs",
    )
    workspace = relationship("Workspace")
    project = relationship("Project")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, resource_type={self.resource_type})>"

    @property
    def is_error(self) -> bool:
        """Check if this log entry represents an error."""
        return not self.success

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action": self.action.value if self.action else None,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "success": self.success,
            "error_message": self.error_message,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "details": self.details,
            "changes": self.changes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Import for relationship setup (avoid circular import)
from backend.db.models.user import User  # noqa: E402
from backend.db.models.workspace import Workspace  # noqa: E402
from backend.db.models.project import Project  # noqa: E402
