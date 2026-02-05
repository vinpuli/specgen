"""
Core module for security and utility functions.

This module provides:
- Security utilities (password hashing, JWT tokens)
- Common exceptions
- Configuration helpers
"""

from backend.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
    generate_secure_token,
    generate_verification_code,
    create_email_verification_token,
    verify_email_token,
    create_password_reset_token,
    verify_password_reset_token,
    create_session_token,
    validate_session_token,
)

__all__ = [
    # Password functions
    "hash_password",
    "verify_password",
    "validate_password_strength",
    # JWT functions
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token_type",
    # Token generation
    "generate_secure_token",
    "generate_verification_code",
    # Email verification
    "create_email_verification_token",
    "verify_email_token",
    # Password reset
    "create_password_reset_token",
    "verify_password_reset_token",
    # Session
    "create_session_token",
    "validate_session_token",
]
