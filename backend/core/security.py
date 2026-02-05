"""
Security utilities for password hashing and verification.

This module provides:
- Password hashing with bcrypt
- Password strength validation
- Secure token generation
- Encryption helpers
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from backend.api.schemas.user import TokenPayload


# ======================
# Configuration
# ======================

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password policy
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))
REQUIRE_UPPERCASE = os.getenv("REQUIRE_UPPERCASE", "true").lower() == "true"
REQUIRE_LOWERCASE = os.getenv("REQUIRE_LOWERCASE", "true").lower() == "true"
REQUIRE_DIGIT = os.getenv("REQUIRE_DIGIT", "true").lower() == "true"
REQUIRE_SPECIAL = os.getenv("REQUIRE_SPECIAL", "true").lower() == "true"
SPECIAL_CHARS = os.getenv("SPECIAL_CHARS", "!@#$%^&*()_+-=[]{}|;:,.<>?")

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/oauth/callback")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/oauth/callback")

MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/oauth/callback")

# OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"

MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"

# TOTP Configuration
TOTP_ISSUER = os.getenv("TOTP_ISSUER", "Agentic Spec Builder")
TOTP_DIGITS = int(os.getenv("TOTP_DIGITS", "6"))
TOTP_PERIOD = int(os.getenv("TOTP_PERIOD", "30"))
TOTP_ALGORITHM = os.getenv("TOTP_ALGORITHM", "SHA1")
BACKUP_CODES_COUNT = int(os.getenv("BACKUP_CODES_COUNT", "10"))


# ======================
# Password Hashing
# ======================


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password.

    Returns:
        Hashed password as string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password.
        hashed_password: Stored password hash.

    Returns:
        True if password matches, False otherwise.
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength against policy.

    Args:
        password: Password to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"

    if REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    if REQUIRE_SPECIAL and not any(c in SPECIAL_CHARS for c in password):
        return False, f"Password must contain at least one special character ({SPECIAL_CHARS})"

    return True, ""


# ======================
# JWT Tokens
# ======================


def create_access_token(
    user_id: str,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User ID to encode in token.
        email: Optional email to include.
        expires_delta: Optional custom expiration.
        additional_claims: Optional additional claims.

    Returns:
        Encoded JWT token.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    if email:
        to_encode["email"] = email

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: str) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: User ID to encode in token.

    Returns:
        Encoded refresh token.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": str(uuid4()),  # Unique token ID
    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token to decode.

    Returns:
        TokenPayload with decoded claims.

    Raises:
        JWTError: If token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(
            sub=payload.get("sub"),
            email=payload.get("email"),
            exp=datetime.fromtimestamp(payload.get("exp", 0)) if payload.get("exp") else None,
            iat=datetime.fromtimestamp(payload.get("iat", 0)) if payload.get("iat") else None,
            type=payload.get("type", "access"),
        )
    except JWTError as e:
        raise JWTError(f"Invalid token: {str(e)}")


def verify_token_type(token_payload: TokenPayload, expected_type: str) -> bool:
    """
    Verify token type matches expected.

    Args:
        token_payload: Decoded token payload.
        expected_type: Expected token type.

    Returns:
        True if types match.
    """
    return token_payload.type == expected_type


# ======================
# Secure Token Generation
# ======================


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a secure random token.

    Args:
        length: Token length in bytes.

    Returns:
        Hex-encoded random token.
    """
    return secrets.token_hex(length)


def generate_verification_code(length: int = 6) -> str:
    """
    Generate a numeric verification code.

    Args:
        length: Code length.

    Returns:
        Numeric verification code.
    """
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


# ======================
# Email Verification
# ======================


def create_email_verification_token(user_id: str, email: str) -> str:
    """
    Create an email verification token.

    Args:
        user_id: User ID.
        email: User's email.

    Returns:
        Verification token.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=24)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "email_verification",
    }

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_email_token(token: str) -> Optional[dict]:
    """
    Verify an email verification token.

    Args:
        token: Verification token.

    Returns:
        Decoded payload or None if invalid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "email_verification":
            return None
        return payload
    except JWTError:
        return None


# ======================
# Password Reset
# ======================


def create_password_reset_token(user_id: str) -> tuple[str, datetime]:
    """
    Create a password reset token.

    Args:
        user_id: User ID.

    Returns:
        Tuple of (token, expiration_time).
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=1)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "password_reset",
        "jti": str(uuid4()),
    }

    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token, expire


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token.

    Args:
        token: Reset token.

    Returns:
        User ID if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ======================
# Session Security
# ======================


def create_session_token(user_id: str, session_id: str) -> str:
    """
    Create a session token for remember me functionality.

    Args:
        user_id: User ID.
        session_id: Session ID.

    Returns:
        Session token.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=30)

    to_encode = {
        "sub": str(user_id),
        "sid": session_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "session",
    }

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def validate_session_token(token: str) -> Optional[dict]:
    """
    Validate a session token.

    Args:
        token: Session token.

    Returns:
        Payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "session":
            return None
        return {"user_id": payload.get("sub"), "session_id": payload.get("sid")}
    except JWTError:
        return None


# ======================
# OAuth Helpers
# ======================


def get_oauth_auth_url(provider: str, state: str) -> str:
    """
    Get OAuth authorization URL for a provider.

    Args:
        provider: OAuth provider name (google, github, microsoft).
        state: State parameter for CSRF protection.

    Returns:
        Authorization URL.

    Raises:
        ValueError: If provider is not supported.
    """
    if provider == "google":
        import urllib.parse

        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    elif provider == "github":
        import urllib.parse

        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "response_type": "code",
            "scope": "read:user user:email",
            "state": state,
        }
        return f"{GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"

    elif provider == "microsoft":
        import urllib.parse

        params = {
            "client_id": MICROSOFT_CLIENT_ID,
            "redirect_uri": MICROSOFT_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "response_mode": "query",
        }
        return f"{MICROSOFT_AUTH_URL}?{urllib.parse.urlencode(params)}"

    else:
        raise ValueError(f"Unsupported OAuth provider: {provider}")


def validate_oauth_state(state: str, stored_state: str) -> bool:
    """
    Validate OAuth state parameter for CSRF protection.

    Args:
        state: State from OAuth callback.
        stored_state: State stored during auth URL generation.

    Returns:
        True if valid.
    """
    return state == stored_state


# ======================
# TOTP Two-Factor Authentication
# ======================


def generate_totp_secret() -> str:
    """
    Generate a new TOTP secret.

    Returns:
        Base32-encoded TOTP secret.
    """
    import base64

    secret_bytes = secrets.token_bytes(20)  # 160 bits = 32 base32 chars
    return base64.b32encode(secret_bytes).decode("utf-8").rstrip("=")


def get_totp_uri(secret: str, email: str) -> str:
    """
    Get TOTP URI for authenticator apps.

    Args:
        secret: TOTP secret.
        email: User's email.

    Returns:
        TOTP URI for QR code.
    """
    import urllib.parse

    params = {
        "secret": secret,
        "issuer": TOTP_ISSUER,
        "algorithm": TOTP_ALGORITHM,
        "digits": str(TOTP_DIGITS),
        "period": str(TOTP_PERIOD),
    }
    return f"otpauth://totp/{urllib.parse.quote(email)}?{urllib.parse.urlencode(params)}"


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a TOTP code.

    Args:
        secret: TOTP secret.
        code: 6-digit code to verify.

    Returns:
        True if code is valid.
    """
    import pyotp

    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)  # Allow 1 period tolerance
    except Exception:
        return False


def generate_backup_codes(count: int = 10) -> list[str]:
    """
    Generate backup codes.

    Args:
        count: Number of codes to generate.

    Returns:
        List of backup codes.
    """
    codes = []
    for _ in range(count):
        code = "".join(str(secrets.randbelow(10)) for _ in range(8))
        codes.append(code)
    return codes


def hash_backup_code(code: str) -> str:
    """
    Hash a backup code for storage.

    Args:
        code: Backup code to hash.

    Returns:
        Hashed code.
    """
    return hash_password(code)


def verify_backup_code(plain_code: str, hashed_codes: list[str]) -> bool:
    """
    Verify a backup code against stored hashes.

    Args:
        plain_code: Backup code to verify.
        hashed_codes: List of hashed backup codes.

    Returns:
        True if code is valid and unused.
    """
    for hashed_code in hashed_codes:
        if verify_password(plain_code, hashed_code):
            return True
    return False
