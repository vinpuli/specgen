"""
User model for authentication and user management.

This model handles:
- User registration and authentication
- OAuth provider associations
- Two-factor authentication (TOTP)
- Session management
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from backend.db.base import Base
from backend.db.meta import metadata


class User(Base):
    """
    User model for authentication and profile management.

    Attributes:
        id: Unique identifier (UUID primary key)
        email: User's email address (unique, indexed)
        password_hash: Bcrypt hashed password
        full_name: User's display name
        avatar_url: URL to user's avatar image
        is_active: Whether the account is active
        is_verified: Whether email is verified
        two_factor_enabled: Whether 2FA is enabled
        two_factor_secret: TOTP secret (encrypted)
        oauth_providers: List of connected OAuth providers
        last_login_at: Timestamp of last login
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email"),
        {"schema": "public"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=Text("gen_random_uuid()"),
    )

    # Authentication fields
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="User's email address (unique identifier)",
    )
    password_hash = Column(
        String(255),
        nullable=True,  # Nullable for OAuth-only users
        doc="Bcrypt hashed password",
    )

    # Profile fields
    full_name = Column(
        String(255),
        nullable=True,
        doc="User's display name",
    )
    avatar_url = Column(
        String(512),
        nullable=True,
        doc="URL to user's avatar image",
    )

    # Status flags
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the account is active",
    )
    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether email is verified",
    )

    # Two-factor authentication
    two_factor_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether 2FA is enabled",
    )
    two_factor_secret = Column(
        String(255),
        nullable=True,
        doc="TOTP secret (encrypted at rest)",
    )

    # OAuth providers
    oauth_providers = Column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
        doc="List of connected OAuth providers (google, github, microsoft)",
    )

    # Timestamps
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of last successful login",
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
    workspace_members = relationship(
        "WorkspaceMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    owned_workspaces = relationship(
        "Workspace",
        back_populates="owner",
        foreign_keys="Workspace.owner_id",
    )
    projects = relationship(
        "Project",
        back_populates="creator",
        foreign_keys="Project.created_by",
    )
    comments = relationship(
        "Comment",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, name={self.full_name})>"

    @property
    def is_oauth_only(self) -> bool:
        """Check if user is OAuth-only (no password)."""
        return self.password_hash is None

    @property
    def has_2fa(self) -> bool:
        """Check if user has 2FA enabled."""
        return self.two_factor_enabled

    def get_primary_provider(self) -> Optional[str]:
        """Get the primary OAuth provider if any."""
        return self.oauth_providers[0] if self.oauth_providers else None


# Import for relationship setup (avoid circular import)
from backend.db.models.workspace import WorkspaceMember  # noqa: E402
