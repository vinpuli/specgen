"""
Authentication API endpoints.

This module provides:
- User registration endpoint
- User login endpoint
- Token refresh endpoint
- Logout endpoints
- Profile management endpoints
- Password management endpoints
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserUpdate,
    ChangePassword,
    Token,
    RefreshTokenRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    MagicLinkRequest,
    MagicLinkVerify,
    OAuthProviderEnum,
    OAuthCallback,
    Enable2FARequest,
    Enable2FAResponse,
    Verify2FASetupRequest,
    Disable2FARequest,
    RegenerateBackupCodesRequest,
    RegenerateBackupCodesResponse,
)
from backend.api.schemas.common import SuccessResponse, ErrorResponse, ActiveSessions
from backend.db.connection import get_db
from backend.services.user_service import (
    UserService,
    UserServiceError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserNotFoundError,
    WeakPasswordError,
    InactiveUserError,
)
from backend.services.session_service import (
    TokenBlacklistService,
    get_token_blacklist_service,
)
from backend.core.security import decode_token, verify_token_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials.
        session: Database session.

    Returns:
        UserResponse for the authenticated user.

    Raises:
        HTTPException: If authentication fails.
    """
    try:
        token = credentials.credentials

        # Check if token is blacklisted
        blacklist_service = await get_token_blacklist_service()
        if await blacklist_service.is_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = decode_token(token)

        if not verify_token_type(payload, "access"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_service = UserService(session)
        user = await user_service.get_by_id(payload.sub)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user_service.to_response(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer(auto_error=False))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[UserResponse]:
    """
    Get current user if authenticated, otherwise return None.

    Args:
        credentials: HTTP Bearer credentials.
        session: Database session.

    Returns:
        UserResponse if authenticated, None otherwise.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials, session)
    except HTTPException:
        return None


CurrentUser = Annotated[UserResponse, Depends(get_current_user)]
OptionalUser = Annotated[Optional[UserResponse], Depends(get_optional_user)]


# ======================
# Registration & Login
# ======================


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": Token, "description": "Successfully registered"},
        400: {"model": ErrorResponse, "description": "Registration failed"},
        409: {"model": ErrorResponse, "description": "User already exists"},
    },
    summary="Register a new user",
    description="Register a new user with email and password.",
)
async def register(
    registration: UserRegister,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Register a new user.

    - **email**: Valid email address
    - **password**: At least 8 characters with uppercase, lowercase, and digit
    - **full_name**: Optional display name
    """
    user_service = UserService(session)

    try:
        user, token = await user_service.register(registration)

        # Register session
        blacklist_service = await get_token_blacklist_service()
        # Note: We don't have refresh token here yet, so just track access token
        await blacklist_service.add_active_session(
            user_id=str(user.id),
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
        )

        logger.info(f"User registered successfully: {user.email}")
        return token

    except UserAlreadyExistsError as e:
        logger.warning(f"Registration failed - user exists: {registration.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    except WeakPasswordError as e:
        logger.warning(f"Registration failed - weak password: {registration.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except UserServiceError as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=Token,
    responses={
        200: {"model": Token, "description": "Successfully logged in"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    },
    summary="Login with email and password",
    description="Authenticate user and return JWT tokens.",
)
async def login(
    login_data: UserLogin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Login with email and password.

    - **email**: User's email address
    - **password**: User's password
    - **two_factor_code**: Optional 2FA code
    """
    user_service = UserService(session)

    try:
        user, token = await user_service.authenticate(
            email=login_data.email,
            password=login_data.password,
            require_verified=False,
        )

        # Register session
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.add_active_session(
            user_id=str(user.id),
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
        )

        logger.info(f"User logged in: {user.email}")
        return token

    except InvalidCredentialsError as e:
        logger.warning(f"Login failed - invalid credentials: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except InactiveUserError as e:
        logger.warning(f"Login failed - inactive account: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ======================
# Magic Link Authentication
# ======================


@router.post(
    "/magic-link",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Magic link sent"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Request magic link",
    description="Request a magic link for passwordless login via email.",
)
async def request_magic_link(
    request: MagicLinkRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Request a magic link for passwordless login.

    This will send a magic link to the user's email if the account exists.
    For security, we always return success to prevent email enumeration.
    """
    user_service = UserService(session)

    try:
        token, expire = await user_service.request_magic_link(request.email)

        if token:
            # TODO: Send magic link email
            # In production, integrate with email service
            logger.info(f"Magic link generated for: {request.email}")
            logger.debug(f"Token (for dev): {token[:20]}...")

        # Always return success to prevent email enumeration
        return SuccessResponse(
            success=True,
            message="If an account exists with that email, a magic link has been sent.",
        )

    except Exception as e:
        logger.error(f"Magic link request failed: {str(e)}")
        return SuccessResponse(
            success=True,
            message="If an account exists with that email, a magic link has been sent.",
        )


@router.post(
    "/magic-link/verify",
    response_model=Token,
    responses={
        200: {"model": Token, "description": "Login successful"},
        401: {"model": ErrorResponse, "description": "Invalid or expired magic link"},
    },
    summary="Verify magic link",
    description="Verify the magic link and return JWT tokens for login.",
)
async def verify_magic_link(
    verify: MagicLinkVerify,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Verify magic link token and log the user in.

    - **token**: Magic link token from email

    Returns JWT access and refresh tokens upon successful verification.
    """
    user_service = UserService(session)

    try:
        user, token = await user_service.verify_magic_link(verify.token)

        # Register session
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.add_active_session(
            user_id=str(user.id),
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
        )

        logger.info(f"Magic link login successful: {user.email}")
        return token

    except InvalidCredentialsError as e:
        logger.warning(f"Magic link verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except InactiveUserError as e:
        logger.warning(f"Magic link login failed - inactive account")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ======================
# Logout
# ======================


@router.post(
    "/logout",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Successfully logged out"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Logout current session",
    description="Logout the current session and invalidate the access token.",
)
async def logout(
    current_user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> SuccessResponse:
    """
    Logout current session.

    This blacklists the current access token.
    """
    blacklist_service = await get_token_blacklist_service()

    # Blacklist the current token
    await blacklist_service.add_to_blacklist(credentials.credentials)

    # Also remove from active sessions
    await blacklist_service.remove_active_session(
        user_id=str(current_user.id),
        access_token=credentials.credentials,
        refresh_token="",
    )

    logger.info(f"User logged out: {current_user.email}")
    return SuccessResponse(
        success=True,
        message="Successfully logged out",
    )


@router.post(
    "/logout-all",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "All sessions logged out"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Logout all sessions",
    description="Logout from all devices by blacklisting all active tokens.",
)
async def logout_all(
    current_user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> SuccessResponse:
    """
    Logout from all devices.

    This blacklists all active tokens for the user.
    """
    blacklist_service = await get_token_blacklist_service()

    # Blacklist all user tokens
    count = await blacklist_service.blacklist_all_user_tokens(str(current_user.id))

    logger.info(f"User logged out from all devices: {current_user.email} ({count} sessions)")
    return SuccessResponse(
        success=True,
        message=f"Successfully logged out from {count} sessions",
    )


@router.post(
    "/logout-other",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Other sessions logged out"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Logout other sessions",
    description="Logout from all other devices except the current one.",
)
async def logout_other_sessions(
    current_user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> SuccessResponse:
    """
    Logout from all other devices except the current one.
    """
    blacklist_service = await get_token_blacklist_service()

    # Get all active sessions
    all_sessions = await blacklist_service.get_active_sessions(str(current_user.id))

    # Blacklist all except current
    count = 0
    for token in all_sessions:
        if token != credentials.credentials:
            await blacklist_service.add_to_blacklist(token)
            count += 1

    logger.info(f"User logged out other devices: {current_user.email} ({count} sessions)")
    return SuccessResponse(
        success=True,
        message=f"Successfully logged out from {count} other sessions",
    )


@router.get(
    "/sessions",
    response_model=ActiveSessions,
    responses={
        200: {"model": ActiveSessions, "description": "Active sessions list"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get active sessions",
    description="Get list of all active sessions for the current user.",
)
async def get_active_sessions(
    current_user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> ActiveSessions:
    """
    Get all active sessions for the current user.
    """
    blacklist_service = await get_token_blacklist_service()

    sessions = await blacklist_service.get_active_sessions(str(current_user.id))
    count = await blacklist_service.get_active_session_count(str(current_user.id))

    # For security, don't return actual tokens, just count
    return ActiveSessions(
        sessions=[],  # Don't expose tokens
        total=count,
        current_session_id=credentials.credentials[:20] + "..." if credentials else None,
    )


# ======================
# Token Refresh
# ======================


@router.post(
    "/refresh",
    response_model=Token,
    responses={
        200: {"model": Token, "description": "Token refreshed"},
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
    summary="Refresh access token",
    description="Use refresh token to get new access token.",
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Refresh access token using refresh token.
    """
    blacklist_service = await get_token_blacklist_service()

    # Check if refresh token is already blacklisted
    if await blacklist_service.is_blacklisted(refresh_data.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_service = UserService(session)

    try:
        # Blacklist the old refresh token
        await blacklist_service.add_to_blacklist(refresh_data.refresh_token)

        # Get new tokens
        new_token = await user_service.refresh_token(refresh_data.refresh_token)

        # Get user from decoded token
        payload = decode_token(refresh_data.refresh_token)
        user_id = payload.sub

        # Register new session
        await blacklist_service.add_active_session(
            user_id=user_id,
            access_token=new_token.access_token,
            refresh_token=new_token.refresh_token or "",
        )

        return new_token

    except InvalidCredentialsError as e:
        logger.warning("Token refresh failed - invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except InactiveUserError as e:
        logger.warning("Token refresh failed - inactive user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ======================
# Profile Management
# ======================


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        200: {"model": UserResponse, "description": "Current user profile"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get current user profile",
    description="Get the profile of the currently authenticated user.",
)
async def get_current_user_profile(
    current_user: CurrentUser,
) -> UserResponse:
    """
    Get current authenticated user's profile.
    """
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    responses={
        200: {"model": UserResponse, "description": "Profile updated"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Update current user profile",
    description="Update the profile of the currently authenticated user.",
)
async def update_current_user_profile(
    update: UserUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Update current user's profile.
    """
    user_service = UserService(session)

    try:
        user = await user_service.update_profile(
            user_id=current_user.id,
            update=update,
        )
        return user_service.to_response(user)

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ======================
# Password Management
# ======================


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Password changed"},
        400: {"model": ErrorResponse, "description": "Password change failed"},
        401: {"model": ErrorResponse, "description": "Not authenticated or wrong password"},
    },
    summary="Change password",
    description="Change the password of the currently authenticated user.",
)
async def change_password(
    change: ChangePassword,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Change current user's password.
    """
    user_service = UserService(session)

    try:
        await user_service.change_password(
            user_id=current_user.id,
            change=change,
        )

        # Logout from all devices after password change
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_all_user_tokens(str(current_user.id))

        return SuccessResponse(
            success=True,
            message="Password changed successfully. Please login again on all devices.",
        )

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    except WeakPasswordError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ======================
# Password Reset
# ======================


@router.post(
    "/password-reset/request",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Password reset email sent"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Request password reset",
    description="Request a password reset email for the given email address.",
)
async def request_password_reset(
    request: PasswordResetRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Request a password reset for an email address.

    This will send a password reset email if the user exists.
    For security, we always return success to prevent email enumeration.
    """
    user_service = UserService(session)

    try:
        token, expire = await user_service.request_password_reset(request.email)

        if token:
            # TODO: Send password reset email
            # In production, integrate with email service
            logger.info(f"Password reset token generated for: {request.email}")
            logger.debug(f"Token (for dev): {token[:20]}... (expires: {expire})")

        # Always return success to prevent email enumeration
        return SuccessResponse(
            success=True,
            message="If an account exists with that email, a password reset link has been sent.",
        )

    except Exception as e:
        logger.error(f"Password reset request failed: {str(e)}")
        # Still return success for security
        return SuccessResponse(
            success=True,
            message="If an account exists with that email, a password reset link has been sent.",
        )


@router.post(
    "/password-reset/confirm",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Password reset successful"},
        400: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
    summary="Confirm password reset",
    description="Reset the password using the token sent to the user's email.",
)
async def confirm_password_reset(
    confirm: PasswordResetConfirm,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Confirm password reset with new password.

    - **token**: Password reset token from email
    - **new_password**: New password (min 8 chars, uppercase, lowercase, digit)
    - **confirm_password**: Must match new_password
    """
    # Validate passwords match
    if confirm.new_password != confirm.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    user_service = UserService(session)

    try:
        await user_service.reset_password(confirm.token, confirm.new_password)

        return SuccessResponse(
            success=True,
            message="Password has been reset successfully. You can now login with your new password.",
        )

    except InvalidCredentialsError as e:
        logger.warning(f"Password reset failed - invalid token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except WeakPasswordError as e:
        logger.warning(f"Password reset failed - weak password")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ======================
# Account Management
# ======================


@router.post(
    "/deactivate",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Account deactivated"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Deactivate account",
    description="Deactivate the currently authenticated user's account.",
)
async def deactivate_account(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Deactivate current user's account.
    """
    user_service = UserService(session)

    # Blacklist all tokens first
    blacklist_service = await get_token_blacklist_service()
    await blacklist_service.blacklist_all_user_tokens(str(current_user.id))

    try:
        await user_service.deactivate_user(user_id=current_user.id)
        return SuccessResponse(
            success=True,
            message="Account deactivated successfully",
        )

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/reactivate",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Account reactivated"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Reactivate account",
    description="Reactivate a previously deactivated account.",
)
async def reactivate_account(
    email: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Reactivate a deactivated user's account.
    """
    user_service = UserService(session)

    user = await user_service.get_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await user_service.reactivate_user(user_id=user.id)
    return SuccessResponse(
        success=True,
        message="Account reactivated successfully",
    )


# ======================
# OAuth 2.0 Authentication
# ======================


@router.get(
    "/oauth/{provider}",
    responses={
        302: {"description": "Redirect to OAuth provider"},
        400: {"model": ErrorResponse, "description": "Invalid provider"},
    },
    summary="Initiate OAuth login",
    description="Redirect to OAuth provider for authentication.",
)
async def initiate_oauth(
    provider: OAuthProviderEnum,
    redirect_uri: str,
    state: str,
) -> RedirectResponse:
    """
    Initiate OAuth login with the specified provider.

    This redirects the user to the OAuth provider's authorization page.
    After authentication, the user will be redirected back to the callback endpoint.
    """
    from backend.core.security import get_oauth_auth_url

    auth_url = get_oauth_auth_url(provider.value, redirect_uri, state)

    logger.info(f"Initiating OAuth flow for provider: {provider.value}")
    return RedirectResponse(url=auth_url)


@router.get(
    "/oauth/{provider}/callback",
    response_model=Token,
    responses={
        200: {"model": Token, "description": "OAuth login successful"},
        401: {"model": ErrorResponse, "description": "OAuth failed"},
    },
    summary="OAuth callback",
    description="Handle OAuth callback from provider and return JWT tokens.",
)
async def oauth_callback(
    provider: OAuthProviderEnum,
    code: str,
    state: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    redirect_uri: str = "http://localhost:3000/api/v1/auth/oauth/callback",
) -> Token:
    """
    Handle OAuth callback from the provider.

    This endpoint receives the authorization code from the OAuth provider
    and exchanges it for tokens, then creates/updates the user and returns
    JWT tokens.
    """
    from backend.core.security import validate_oauth_state

    # Validate state (in production, store state in session/redis for CSRF protection)
    if not validate_oauth_state(state):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OAuth state",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_service = UserService(session)

    try:
        user, token = await user_service.handle_oauth_callback(
            provider=provider.value,
            code=code,
            redirect_uri=redirect_uri,
        )

        # Register session
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.add_active_session(
            user_id=str(user.id),
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
        )

        logger.info(f"OAuth login successful for user: {user.email} via {provider.value}")
        return token

    except InvalidCredentialsError as e:
        logger.warning(f"OAuth callback failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except InactiveUserError as e:
        logger.warning(f"OAuth login failed - inactive account")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ======================
# Two-Factor Authentication
# ======================


@router.post(
    "/2fa/setup",
    responses={
        200: {"model": Enable2FAResponse, "description": "2FA setup initiated"},
        401: {"model": ErrorResponse, "description": "Not authenticated or invalid password"},
    },
    summary="Set up 2FA",
    description="Set up two-factor authentication for the current user.",
)
async def setup_2fa(
    request: Enable2FARequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Enable2FAResponse:
    """
    Set up 2FA for the current user.

    This initiates 2FA setup and returns the TOTP secret and QR code URI.
    The user must verify with a valid code to complete setup.
    """
    user_service = UserService(session)

    try:
        secret, qr_code_uri, backup_codes = await user_service.setup_2fa(
            user_id=current_user.id,
            password=request.password,
        )

        logger.info(f"2FA setup initiated for user: {current_user.email}")
        return Enable2FAResponse(
            secret=secret,
            qr_code_uri=qr_code_uri,
            backup_codes=backup_codes,
        )

    except InvalidCredentialsError as e:
        logger.warning(f"2FA setup failed - invalid password: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/2fa/verify-setup",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "2FA enabled"},
        401: {"model": ErrorResponse, "description": "Not authenticated or invalid code"},
    },
    summary="Verify 2FA setup",
    description="Verify 2FA setup with a valid TOTP code to enable 2FA.",
)
async def verify_2fa_setup(
    request: Verify2FASetupRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Verify 2FA setup with a valid TOTP code.

    This completes the 2FA setup and enables 2FA for the user.
    """
    user_service = UserService(session)

    try:
        await user_service.verify_2fa_setup(
            user_id=current_user.id,
            code=request.code,
        )

        logger.info(f"2FA enabled for user: {current_user.email}")
        return SuccessResponse(
            success=True,
            message="Two-factor authentication has been enabled successfully.",
        )

    except InvalidCredentialsError as e:
        logger.warning(f"2FA verification failed: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/2fa/disable",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "2FA disabled"},
        401: {"model": ErrorResponse, "description": "Not authenticated or invalid credentials"},
    },
    summary="Disable 2FA",
    description="Disable two-factor authentication for the current user.",
)
async def disable_2fa(
    request: Disable2FARequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Disable 2FA for the current user.

    Requires password and 2FA code or backup code for verification.
    """
    user_service = UserService(session)

    try:
        await user_service.disable_2fa(
            user_id=current_user.id,
            password=request.password,
            code=request.code,
        )

        logger.info(f"2FA disabled for user: {current_user.email}")
        return SuccessResponse(
            success=True,
            message="Two-factor authentication has been disabled.",
        )

    except InvalidCredentialsError as e:
        logger.warning(f"2FA disable failed: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get(
    "/2fa/status",
    responses={
        200: {"description": "2FA status"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get 2FA status",
    description="Get the 2FA status for the current user.",
)
async def get_2fa_status(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Get the 2FA status for the current user.
    """
    user_service = UserService(session)
    user = await user_service.get_by_id(current_user.id)

    return {
        "two_factor_enabled": user.two_factor_enabled if user else False,
        "backup_codes_count": user.backup_codes_count if user else 0,
    }


@router.post(
    "/2fa/regenerate-backup-codes",
    response_model=RegenerateBackupCodesResponse,
    responses={
        200: {"model": RegenerateBackupCodesResponse, "description": "Backup codes regenerated"},
        401: {"model": ErrorResponse, "description": "Not authenticated or invalid credentials"},
    },
    summary="Regenerate backup codes",
    description="Generate new backup codes for 2FA.",
)
async def regenerate_backup_codes(
    request: RegenerateBackupCodesRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegenerateBackupCodesResponse:
    """
    Regenerate backup codes for 2FA.

    Requires password and 2FA code for verification.
    Old backup codes will be invalidated.
    """
    user_service = UserService(session)

    try:
        backup_codes = await user_service.regenerate_backup_codes(
            user_id=current_user.id,
            password=request.password,
            code=request.code,
        )

        logger.info(f"Backup codes regenerated for user: {current_user.email}")
        return RegenerateBackupCodesResponse(
            backup_codes=backup_codes,
            message="Backup codes regenerated successfully. Store these codes safely.",
        )

    except InvalidCredentialsError as e:
        logger.warning(f"Backup code regeneration failed: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
