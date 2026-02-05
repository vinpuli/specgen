"""
User service for authentication and user management.

This module provides:
- User registration
- User authentication
- Profile management
- Session management
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.schemas.user import (
    UserCreate,
    UserRegister,
    UserUpdate,
    ChangePassword,
    UserResponse,
    UserInDB,
    Token,
)
from backend.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    create_password_reset_token,
    verify_password_reset_token,
    create_email_verification_token,
    verify_email_token,
)
from backend.db.models.user import User

logger = logging.getLogger(__name__)


class UserServiceError(Exception):
    """Base exception for user service errors."""

    pass


class UserAlreadyExistsError(UserServiceError):
    """Raised when user already exists."""

    pass


class InvalidCredentialsError(UserServiceError):
    """Raised when credentials are invalid."""

    pass


class UserNotFoundError(UserServiceError):
    """Raised when user is not found."""

    pass


class WeakPasswordError(UserServiceError):
    """Raised when password doesn't meet requirements."""

    pass


class InactiveUserError(UserServiceError):
    """Raised when user account is inactive."""

    pass


class UserService:
    """
    User service for authentication and user management.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize user service.

        Args:
            session: Async database session.
        """
        self.session = session

    async def register(self, registration: UserRegister) -> tuple[User, Token]:
        """
        Register a new user.

        Args:
            registration: User registration data.

        Returns:
            Tuple of (User, Token).

        Raises:
            UserAlreadyExistsError: If email already registered.
            WeakPasswordError: If password doesn't meet requirements.
        """
        # Check if user already exists
        existing = await self.get_by_email(registration.email)
        if existing:
            raise UserAlreadyExistsError(f"User with email {registration.email} already exists")

        # Validate password strength
        is_valid, error_msg = validate_password_strength(registration.password)
        if not is_valid:
            raise WeakPasswordError(error_msg)

        # Create user
        password_hash = hash_password(registration.password)

        user = User(
            email=registration.email,
            password_hash=password_hash,
            full_name=registration.full_name,
            is_active=True,
            is_verified=False,
            oauth_providers=[],
        )

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        # Generate tokens
        token = self._create_tokens_for_user(user)

        logger.info(f"User registered: {user.email}")
        return user, token

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User's email.

        Returns:
            User if found, None otherwise.
        """
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User's UUID.

        Returns:
            User if found, None otherwise.
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def authenticate(
        self, email: str, password: str, require_verified: bool = False
    ) -> tuple[User, Token]:
        """
        Authenticate user with email and password.

        Args:
            email: User's email.
            password: Plain text password.
            require_verified: Whether to require email verification.

        Returns:
            Tuple of (User, Token).

        Raises:
            InvalidCredentialsError: If credentials are invalid.
            InactiveUserError: If account is inactive.
        """
        user = await self.get_by_email(email)
        if not user:
            raise InvalidCredentialsError("Invalid email or password")

        if not user.is_active:
            raise InactiveUserError("Account is inactive")

        if require_verified and not user.is_verified:
            raise InvalidCredentialsError("Email not verified")

        if user.password_hash is None:
            raise InvalidCredentialsError("User must login via OAuth")

        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.commit()

        # Generate tokens
        token = self._create_tokens_for_user(user)

        logger.info(f"User authenticated: {user.email}")
        return user, token

    async def update_profile(self, user_id: UUID, update: UserUpdate) -> User:
        """
        Update user profile.

        Args:
            user_id: User's UUID.
            update: Profile update data.

        Returns:
            Updated User.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        update_data = update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await self.session.commit()
        await self.session.refresh(user)

        logger.info(f"User profile updated: {user.email}")
        return user

    async def change_password(
        self, user_id: UUID, change: ChangePassword
    ) -> bool:
        """
        Change user password.

        Args:
            user_id: User's UUID.
            change: Password change data.

        Returns:
            True if successful.

        Raises:
            UserNotFoundError: If user not found.
            InvalidCredentialsError: If current password is wrong.
            WeakPasswordError: If new password doesn't meet requirements.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        if user.password_hash is None:
            raise InvalidCredentialsError("OAuth-only users cannot change password")

        if not verify_password(change.current_password, user.password_hash):
            raise InvalidCredentialsError("Current password is incorrect")

        is_valid, error_msg = validate_password_strength(change.new_password)
        if not is_valid:
            raise WeakPasswordError(error_msg)

        if change.new_password != change.confirm_password:
            raise InvalidCredentialsError("Passwords do not match")

        user.password_hash = hash_password(change.new_password)
        await self.session.commit()

        logger.info(f"Password changed for user: {user.email}")
        return True

    async def deactivate_user(self, user_id: UUID) -> bool:
        """
        Deactivate user account.

        Args:
            user_id: User's UUID.

        Returns:
            True if successful.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        user.is_active = False
        await self.session.commit()

        logger.info(f"User deactivated: {user.email}")
        return True

    async def reactivate_user(self, user_id: UUID) -> bool:
        """
        Reactivate user account.

        Args:
            user_id: User's UUID.

        Returns:
            True if successful.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        user.is_active = True
        await self.session.commit()

        logger.info(f"User reactivated: {user.email}")
        return True

    async def refresh_token(self, refresh_token: str) -> Token:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token string.

        Returns:
            New Token.

        Raises:
            InvalidCredentialsError: If refresh token is invalid.
        """
        from backend.core.security import decode_token, verify_token_type

        try:
            payload = decode_token(refresh_token)
            if not verify_token_type(payload, "refresh"):
                raise InvalidCredentialsError("Invalid token type")

            user_id = payload.sub
            user = await self.get_by_id(user_id)
            if not user:
                raise InvalidCredentialsError("User not found")

            if not user.is_active:
                raise InactiveUserError("Account is inactive")

            return self._create_tokens_for_user(user)

        except Exception as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            raise InvalidCredentialsError("Invalid refresh token")

    async def request_password_reset(self, email: str) -> tuple[str, datetime]:
        """
        Request a password reset for a user.

        Args:
            email: User's email address.

        Returns:
            Tuple of (reset_token, expiration_time).

        Raises:
            UserNotFoundError: If user not found.
        """
        user = await self.get_by_email(email)
        if not user:
            # Don't reveal if user exists
            logger.info(f"Password reset requested for non-existent email: {email}")
            return "", datetime.now(timezone.utc)

        # Create reset token
        token, expire = create_password_reset_token(str(user.id))

        logger.info(f"Password reset requested for user: {user.email}")
        return token, expire

    async def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset user's password using reset token.

        Args:
            token: Password reset token.
            new_password: New password.

        Returns:
            True if successful.

        Raises:
            InvalidCredentialsError: If token is invalid or expired.
            WeakPasswordError: If new password doesn't meet requirements.
        """
        user_id = verify_password_reset_token(token)
        if not user_id:
            raise InvalidCredentialsError("Invalid or expired reset token")

        user = await self.get_by_id(user_id)
        if not user:
            raise InvalidCredentialsError("User not found")

        # Validate new password
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise WeakPasswordError(error_msg)

        # Update password
        user.password_hash = hash_password(new_password)
        await self.session.commit()

        logger.info(f"Password reset completed for user: {user.email}")
        return True

    async def request_magic_link(self, email: str) -> tuple[str, datetime]:
        """
        Request a magic link for passwordless login.

        Args:
            email: User's email address.

        Returns:
            Tuple of (magic_link_token, expiration_time).

        Note:
            Returns empty tuple if user doesn't exist (prevents enumeration).
        """
        user = await self.get_by_email(email)
        if not user:
            # Don't reveal if user exists
            logger.info(f"Magic link requested for non-existent email: {email}")
            return "", datetime.now(timezone.utc)

        # Create magic link token with type 'magic_link'
        from backend.core.security import create_access_token

        expire = datetime.now(timezone.utc)
        token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            additional_claims={"type": "magic_link"},
        )

        logger.info(f"Magic link generated for user: {user.email}")
        return token, expire

    async def verify_magic_link(self, token: str) -> tuple[User, Token]:
        """
        Verify magic link token and return user with login tokens.

        Args:
            token: Magic link token.

        Returns:
            Tuple of (User, Token).

        Raises:
            InvalidCredentialsError: If token is invalid.
            InactiveUserError: If account is inactive.
        """
        from backend.core.security import decode_token

        try:
            payload = decode_token(token)

            # Verify it's a magic link token
            if payload.type != "magic_link":
                raise InvalidCredentialsError("Invalid token type")

            user_id = payload.sub
            user = await self.get_by_id(user_id)
            if not user:
                raise InvalidCredentialsError("User not found")

            if not user.is_active:
                raise InactiveUserError("Account is inactive")

            # Update last login
            user.last_login_at = datetime.now(timezone.utc)
            await self.session.commit()

            # Generate login tokens
            login_token = self._create_tokens_for_user(user)

            logger.info(f"Magic link login successful for user: {user.email}")
            return user, login_token

        except Exception as e:
            logger.warning(f"Magic link verification failed: {str(e)}")
            raise InvalidCredentialsError("Invalid or expired magic link")

    async def handle_oauth_callback(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
    ) -> tuple[User, Token]:
        """
        Handle OAuth callback and create/login user.

        Args:
            provider: OAuth provider name (google, github, microsoft).
            code: Authorization code from OAuth provider.
            redirect_uri: Redirect URI used in authorization request.

        Returns:
            Tuple of (User, Token).

        Raises:
            InvalidCredentialsError: If OAuth fails.
        """
        import httpx

        # Exchange code for tokens
        if provider == "google":
            from backend.core.security import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN_URL

            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )
                token_data = token_response.json()

                if "access_token" not in token_data:
                    raise InvalidCredentialsError("Failed to get access token from Google")

                # Get user info
                user_response = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                )
                user_info = user_response.json()

                email = user_info.get("email")
                name = user_info.get("name")
                picture = user_info.get("picture")
                provider_id = user_info.get("sub")

        elif provider == "github":
            from backend.core.security import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_TOKEN_URL, GITHUB_USERINFO_URL

            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    GITHUB_TOKEN_URL,
                    data={
                        "client_id": GITHUB_CLIENT_ID,
                        "client_secret": GITHUB_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": redirect_uri,
                    },
                    headers={"Accept": "application/json"},
                )
                token_data = token_response.json()

                if "access_token" not in token_data:
                    raise InvalidCredentialsError("Failed to get access token from GitHub")

                # Get user info
                user_response = await client.get(
                    GITHUB_USERINFO_URL,
                    headers={"Authorization": f"Bearer {token_data['access_token']}", "Accept": "application/json"},
                )
                user_info = user_response.json()

                email = user_info.get("email")
                name = user_info.get("name")
                avatar_url = user_info.get("avatar_url")
                provider_id = str(user_info.get("id"))

        elif provider == "microsoft":
            from backend.core.security import MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TOKEN_URL, MICROSOFT_USERINFO_URL

            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    MICROSOFT_TOKEN_URL,
                    data={
                        "client_id": MICROSOFT_CLIENT_ID,
                        "client_secret": MICROSOFT_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )
                token_data = token_response.json()

                if "access_token" not in token_data:
                    raise InvalidCredentialsError("Failed to get access token from Microsoft")

                # Get user info
                user_response = await client.get(
                    MICROSOFT_USERINFO_URL,
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                )
                user_info = user_response.json()

                email = user_info.get("mail") or user_info.get("userPrincipalName")
                name = user_info.get("displayName")
                avatar_url = None  # Microsoft Graph API doesn't return avatar in /me endpoint
                provider_id = user_info.get("id")

        else:
            raise InvalidCredentialsError(f"Unsupported OAuth provider: {provider}")

        if not email:
            raise InvalidCredentialsError("Could not get email from OAuth provider")

        # Find or create user
        user = await self.get_by_email(email)
        if not user:
            # Create new user
            user = User(
                email=email,
                password_hash=None,  # OAuth users don't have password
                full_name=name,
                avatar_url=picture or avatar_url,
                is_active=True,
                is_verified=True,  # OAuth email is verified
                oauth_providers=[provider],
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            logger.info(f"New user created via OAuth: {user.email}")
        else:
            # Update existing user
            if provider not in (user.oauth_providers or []):
                providers = set(user.oauth_providers or [])
                providers.add(provider)
                user.oauth_providers = list(providers)
                await self.session.commit()

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.commit()

        # Generate tokens
        token = self._create_tokens_for_user(user)

        logger.info(f"OAuth login successful for user: {user.email}")
        return user, token

    # ======================
    # Two-Factor Authentication
    # ======================

    async def setup_2fa(self, user_id: UUID, password: str) -> tuple[str, str, list[str]]:
        """
        Set up 2FA for a user.

        Args:
            user_id: User's UUID.
            password: Current password for verification.

        Returns:
            Tuple of (secret, qr_code_uri, backup_codes).

        Raises:
            UserNotFoundError: If user not found.
            InvalidCredentialsError: If password is wrong.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        # Verify password
        if user.password_hash and not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid password")

        # Generate TOTP secret
        from backend.core.security import generate_totp_secret, get_totp_uri, generate_backup_codes, hash_backup_code

        secret = generate_totp_secret()
        qr_code_uri = get_totp_uri(secret, user.email)

        # Generate and hash backup codes
        backup_codes_plain = generate_backup_codes(10)
        backup_codes_hashed = [hash_backup_code(code) for code in backup_codes_plain]

        # Store secret and backup codes (don't enable yet - needs verification)
        user.two_factor_secret = secret
        user.backup_codes = backup_codes_hashed
        user.backup_codes_count = len(backup_codes_plain)
        await self.session.commit()

        logger.info(f"2FA setup initiated for user: {user.email}")
        return secret, qr_code_uri, backup_codes_plain

    async def verify_2fa_setup(self, user_id: UUID, code: str) -> bool:
        """
        Verify 2FA setup and enable 2FA.

        Args:
            user_id: User's UUID.
            code: TOTP code from authenticator app.

        Returns:
            True if 2FA is now enabled.

        Raises:
            UserNotFoundError: If user not found.
            InvalidCredentialsError: If code is invalid.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        if not user.two_factor_secret:
            raise InvalidCredentialsError("2FA setup not initiated")

        from backend.core.security import verify_totp_code

        if not verify_totp_code(user.two_factor_secret, code):
            raise InvalidCredentialsError("Invalid 2FA code")

        # Enable 2FA
        user.two_factor_enabled = True
        await self.session.commit()

        logger.info(f"2FA enabled for user: {user.email}")
        return True

    async def disable_2fa(self, user_id: UUID, password: str, code: str) -> bool:
        """
        Disable 2FA for a user.

        Args:
            user_id: User's UUID.
            password: Current password for verification.
            code: 2FA code or backup code.

        Returns:
            True if 2FA is now disabled.

        Raises:
            UserNotFoundError: If user not found.
            InvalidCredentialsError: If credentials are wrong.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        # Verify password
        if user.password_hash and not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid password")

        # Verify 2FA code or backup code
        from backend.core.security import verify_totp_code, verify_backup_code

        code_valid = False
        if user.two_factor_enabled and user.two_factor_secret:
            code_valid = verify_totp_code(user.two_factor_secret, code)

        if not code_valid and user.backup_codes:
            code_valid = verify_backup_code(code, user.backup_codes)

        if not code_valid:
            raise InvalidCredentialsError("Invalid 2FA code or backup code")

        # Disable 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.backup_codes = []
        user.backup_codes_count = 0
        await self.session.commit()

        logger.info(f"2FA disabled for user: {user.email}")
        return True

    async def verify_2fa_login(self, user_id: UUID, code: str) -> bool:
        """
        Verify 2FA code during login.

        Args:
            user_id: User's UUID.
            code: 2FA code or backup code.

        Returns:
            True if code is valid.

        Raises:
            InvalidCredentialsError: If code is invalid.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        if not user.two_factor_enabled or not user.two_factor_secret:
            raise InvalidCredentialsError("2FA not enabled for this user")

        from backend.core.security import verify_totp_code, verify_backup_code

        # Try TOTP first
        if verify_totp_code(user.two_factor_secret, code):
            return True

        # Try backup code
        if user.backup_codes and verify_backup_code(code, user.backup_codes):
            # Remove used backup code
            user.backup_codes_count = max(0, (user.backup_codes_count or 0) - 1)
            await self.session.commit()
            logger.info(f"Backup code used for user: {user.email}, remaining: {user.backup_codes_count}")
            return True

        raise InvalidCredentialsError("Invalid 2FA code or backup code")

    async def regenerate_backup_codes(self, user_id: UUID, password: str, code: str) -> list[str]:
        """
        Regenerate backup codes for a user.

        Args:
            user_id: User's UUID.
            password: Current password for verification.
            code: 2FA code from authenticator.

        Returns:
            List of new backup codes.

        Raises:
            UserNotFoundError: If user not found.
            InvalidCredentialsError: If credentials are wrong.
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        # Verify password
        if user.password_hash and not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid password")

        # Verify 2FA code
        from backend.core.security import verify_totp_code

        if not verify_totp_code(user.two_factor_secret or "", code):
            raise InvalidCredentialsError("Invalid 2FA code")

        # Generate new backup codes
        from backend.core.security import generate_backup_codes, hash_backup_code

        backup_codes_plain = generate_backup_codes(10)
        backup_codes_hashed = [hash_backup_code(code) for code in backup_codes_plain]

        user.backup_codes = backup_codes_hashed
        user.backup_codes_count = len(backup_codes_plain)
        await self.session.commit()

        logger.info(f"Backup codes regenerated for user: {user.email}")
        return backup_codes_plain

    def _create_tokens_for_user(self, user: User) -> Token:
        """
        Create access and refresh tokens for user.

        Args:
            user: User object.

        Returns:
            Token with access and refresh tokens.
        """
        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
        )

        refresh_token = create_refresh_token(user_id=str(user.id))

        from backend.core.security import ACCESS_TOKEN_EXPIRE_MINUTES

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token,
        )

    def to_response(self, user: User) -> UserResponse:
        """
        Convert User model to response schema.

        Args:
            user: User model.

        Returns:
            UserResponse schema.
        """
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_verified=user.is_verified,
            two_factor_enabled=user.two_factor_enabled,
            oauth_providers=user.oauth_providers or [],
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def to_in_db_response(self, user: User) -> UserInDB:
        """
        Convert User model to in-db response (includes sensitive data).

        Args:
            user: User model.

        Returns:
            UserInDB schema.
        """
        return UserInDB(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_verified=user.is_verified,
            two_factor_enabled=user.two_factor_enabled,
            two_factor_secret=user.two_factor_secret,
            oauth_providers=user.oauth_providers or [],
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
