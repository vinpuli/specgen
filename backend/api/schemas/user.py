"""
User Pydantic schemas for authentication and profile management.

This module provides:
- User creation, update, and response schemas
- Login and registration request schemas
- User profile schemas for API responses
"""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
import enum

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin


# ======================
# Request Schemas
# ======================


class UserLogin(BaseModel):
    """User login request schema."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    two_factor_code: Optional[str] = Field(
        default=None, min_length=6, max_length=6, description="2FA code if enabled"
    )


class UserRegister(BaseModel):
    """User registration request schema."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="Strong password")
    full_name: Optional[str] = Field(
        default=None, max_length=255, description="User's display name"
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserCreate(BaseModel):
    """User creation request (admin/internal use)."""

    email: EmailStr = Field(..., description="User's email address")
    password: Optional[str] = Field(
        default=None, min_length=8, description="Optional password for non-OAuth users"
    )
    full_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    oauth_providers: List[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """User update request schema."""

    full_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    is_active: Optional[bool] = None
    two_factor_enabled: Optional[bool] = None


class ChangePassword(BaseModel):
    """Password change request schema."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class Enable2FA(BaseModel):
    """Enable 2FA request schema."""

    password: str = Field(..., description="Current password for verification")


class Verify2FA(BaseModel):
    """Verify 2FA setup/code schema."""

    code: str = Field(..., min_length=6, max_length=6, description="2FA code")


class Disable2FA(BaseModel):
    """Disable 2FA request schema."""

    password: str = Field(..., description="Current password for verification")
    code: str = Field(..., min_length=6, max_length=6, description="2FA code")


# ======================
# Password Reset Schemas
# ======================


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""

    email: EmailStr = Field(..., description="User's email address")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ======================
# Magic Link Schemas
# ======================


class MagicLinkRequest(BaseModel):
    """Magic link request schema."""

    email: EmailStr = Field(..., description="User's email address")


class MagicLinkVerify(BaseModel):
    """Magic link verification schema."""

    token: str = Field(..., description="Magic link token")


# ======================
# OAuth Schemas
# ======================


class OAuthProviderEnum(str, enum.Enum):
    """OAuth provider enumeration."""

    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"


class OAuthTokenRequest(BaseModel):
    """OAuth token exchange request schema."""

    provider: OAuthProviderEnum = Field(..., description="OAuth provider")
    code: str = Field(..., description="Authorization code from OAuth provider")
    redirect_uri: str = Field(..., description="OAuth callback redirect URI")


class OAuthCallback(BaseModel):
    """OAuth callback data schema."""

    code: str = Field(..., description="Authorization code from OAuth provider")
    state: Optional[str] = Field(default=None, description="State parameter")
    provider: OAuthProviderEnum = Field(..., description="OAuth provider name")


class OAuthUserInfo(BaseModel):
    """OAuth user information schema."""

    email: str = Field(..., description="User's email")
    name: Optional[str] = Field(default=None, description="User's name")
    picture: Optional[str] = Field(default=None, description="User's avatar URL")
    provider_id: str = Field(..., description="Provider's user ID")


# ======================
# Response Schemas
# ======================


class UserResponse(UUIDMixin, TimestampSchema):
    """User response schema for public API."""

    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    two_factor_enabled: bool
    oauth_providers: List[str]
    last_login_at: Optional[datetime] = None


class UserProfile(UserResponse):
    """Full user profile response (includes private info)."""

    workspace_members: List[Any] = Field(default_factory=list)


class UserInDB(UserResponse):
    """User schema for internal use (includes sensitive data)."""

    password_hash: Optional[str] = None
    two_factor_secret: Optional[str] = None


class UserWithWorkspaces(UserResponse):
    """User response with workspace membership info."""

    workspaces: List[Any] = Field(default_factory=list)


# ======================
# Token Schemas
# ======================


class Token(BaseModel):
    """JWT token response schema."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    refresh_token: Optional[str] = Field(
        default=None, description="JWT refresh token"
    )


class TokenPayload(BaseModel):
    """JWT token payload schema."""

    sub: str = Field(..., description="User ID")
    email: Optional[str] = None
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    type: str = Field(default="access", description="Token type")


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str = Field(..., description="Refresh token")

# ======================
# Session Schemas
# ======================


class SessionResponse(BaseModel):
    """Session info response schema."""

    session_id: str
    user_id: UUID
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class RevokeSession(BaseModel):
    """Session revocation request schema."""

    session_id: str = Field(..., description="Session ID to revoke")


class ActiveSessions(BaseModel):
    """Active sessions response schema."""

    sessions: List[SessionResponse]
    current_session_id: str


# ======================
# Two-Factor Authentication Schemas
# ======================


class Enable2FARequest(BaseModel):
    """Enable 2FA request schema."""

    password: str = Field(..., description="Current password for verification")


class Enable2FAResponse(BaseModel):
    """Enable 2FA response with QR code and backup codes."""

    secret: str = Field(..., description="TOTP secret for authenticator app")
    qr_code_uri: str = Field(..., description="URI for QR code generation")
    backup_codes: List[str] = Field(..., description="One-time backup codes (store safely)")


class Verify2FASetupRequest(BaseModel):
    """Verify 2FA setup request schema."""

    code: str = Field(..., min_length=6, max_length=6, description="2FA code from authenticator")


class Disable2FARequest(BaseModel):
    """Disable 2FA request schema."""

    password: str = Field(..., description="Current password for verification")
    code: str = Field(..., min_length=6, max_length=6, description="2FA code or backup code")


class LoginWith2FARequest(BaseModel):
    """Login with 2FA code request schema."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    two_factor_code: Optional[str] = Field(
        default=None, min_length=6, max_length=6, description="2FA code from authenticator"
    )
    backup_code: Optional[str] = Field(
        default=None, min_length=8, max_length=8, description="Backup code if no 2FA device"
    )


class VerifyBackupCodeRequest(BaseModel):
    """Verify backup code request schema."""

    code: str = Field(..., min_length=8, max_length=8, description="Backup code")


class RegenerateBackupCodesRequest(BaseModel):
    """Regenerate backup codes request schema."""

    password: str = Field(..., description="Current password for verification")
    code: str = Field(..., min_length=6, max_length=6, description="2FA code from authenticator")


class RegenerateBackupCodesResponse(BaseModel):
    """Regenerate backup codes response schema."""

    backup_codes: List[str] = Field(..., description="New backup codes (store safely)")
    message: str = Field(default="Backup codes regenerated successfully")
