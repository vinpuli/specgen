"""
Workspace API endpoints.

This module provides:
- Workspace CRUD operations
- Workspace membership management
- Role-based access control
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceWithOwner,
    WorkspaceListResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceMemberResponse,
    WorkspaceMemberWithUser,
    WorkspaceMemberInviteResponse,
    WorkspaceMemberRemove,
    BulkInviteRequest,
    BulkInviteResponse,
    PermissionCheck,
    PermissionResponse,
)
from backend.api.schemas.common import SuccessResponse, ErrorResponse, PaginationParams
from backend.db.connection import get_db
from backend.services.user_service import UserService
from backend.api.endpoints.auth import CurrentUser, get_current_user
from backend.services.workspace_service import (
    WorkspaceService,
    WorkspaceServiceError,
    WorkspaceNotFoundError,
    WorkspaceMemberNotFoundError,
    InsufficientPermissionsError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

# Permission constants
CAN_VIEW = ["owner", "admin", "editor", "viewer"]
CAN_EDIT = ["owner", "admin", "editor"]
CAN_ADMIN = ["owner", "admin"]
CAN_DELETE = ["owner"]


# ======================
# Workspace CRUD
# ======================


@router.post(
    "",
    response_model=WorkspaceWithOwner,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": WorkspaceWithOwner, "description": "Workspace created"},
        400: {"model": ErrorResponse, "description": "Creation failed"},
    },
    summary="Create workspace",
    description="Create a new workspace.",
)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceWithOwner:
    """
    Create a new workspace.
    """
    workspace_service = WorkspaceService(session)

    try:
        workspace = await workspace_service.create_workspace(
            name=workspace_data.name,
            slug=workspace_data.slug,
            description=workspace_data.description,
            settings=workspace_data.settings,
            owner_id=str(current_user.id),
        )
        return workspace_service.to_response_with_owner(workspace)

    except WorkspaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=WorkspaceListResponse,
    summary="List workspaces",
    description="List all workspaces the current user is a member of.",
)
async def list_workspaces(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: PaginationParams = Depends(),
) -> WorkspaceListResponse:
    """
    List all workspaces for the current user.
    """
    workspace_service = WorkspaceService(session)

    workspaces, total = await workspace_service.list_user_workspaces(
        user_id=str(current_user.id),
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return WorkspaceListResponse(
        workspaces=[
            workspace_service.to_response(ws) for ws in workspaces
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceWithOwner,
    responses={
        200: {"model": WorkspaceWithOwner, "description": "Workspace details"},
        404: {"model": ErrorResponse, "description": "Workspace not found"},
    },
    summary="Get workspace",
    description="Get workspace details by ID.",
)
async def get_workspace(
    workspace_id: UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceWithOwner:
    """
    Get workspace details.
    """
    workspace_service = WorkspaceService(session)

    try:
        workspace = await workspace_service.get_workspace_by_id(
            workspace_id=str(workspace_id),
            user_id=str(current_user.id),
        )
        return workspace_service.to_response_with_owner(workspace)

    except WorkspaceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    responses={
        200: {"model": WorkspaceResponse, "description": "Workspace updated"},
        404: {"model": ErrorResponse, "description": "Workspace not found"},
    },
    summary="Update workspace",
    description="Update workspace details.",
)
async def update_workspace(
    workspace_id: UUID,
    update: WorkspaceUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceResponse:
    """
    Update workspace details.
    """
    workspace_service = WorkspaceService(session)

    try:
        workspace = await workspace_service.update_workspace(
            workspace_id=str(workspace_id),
            user_id=str(current_user.id),
            name=update.name,
            slug=update.slug,
            description=update.description,
            settings=update.settings,
            is_active=update.is_active,
        )
        return workspace_service.to_response(workspace)

    except WorkspaceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.delete(
    "/{workspace_id}",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Workspace deleted"},
        404: {"model": ErrorResponse, "description": "Workspace not found"},
    },
    summary="Delete workspace",
    description="Delete a workspace (owner only).",
)
async def delete_workspace(
    workspace_id: UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Delete a workspace.
    """
    workspace_service = WorkspaceService(session)

    try:
        await workspace_service.delete_workspace(
            workspace_id=str(workspace_id),
            user_id=str(current_user.id),
        )
        return SuccessResponse(success=True, message="Workspace deleted successfully")

    except WorkspaceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ======================
# Workspace Membership
# ======================


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberInviteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": WorkspaceMemberInviteResponse, "description": "Member invited"},
        404: {"model": ErrorResponse, "description": "Workspace not found"},
    },
    summary="Invite member",
    description="Invite a user to join the workspace.",
)
async def invite_member(
    workspace_id: UUID,
    invite: WorkspaceMemberCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceMemberInviteResponse:
    """
    Invite a user to join the workspace.
    """
    workspace_service = WorkspaceService(session)

    try:
        invitation = await workspace_service.invite_member(
            workspace_id=str(workspace_id),
            inviter_id=str(current_user.id),
            email=invite.email,
            role=invite.role,
        )
        return WorkspaceMemberInviteResponse(
            invitation_id=invitation.id,
            email=invite.email,
            role=invite.role,
            status="pending",
            expires_at=invitation.expires_at,
        )

    except WorkspaceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "/{workspace_id}/members/bulk",
    response_model=BulkInviteResponse,
    summary="Bulk invite members",
    description="Invite multiple users to join the workspace.",
)
async def bulk_invite_members(
    workspace_id: UUID,
    invites: BulkInviteRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BulkInviteResponse:
    """
    Invite multiple users at once.
    """
    workspace_service = WorkspaceService(session)

    successful = []
    failed = []

    for invite in invites.invites:
        try:
            invitation = await workspace_service.invite_member(
                workspace_id=str(workspace_id),
                inviter_id=str(current_user.id),
                email=invite.email,
                role=invite.role,
            )
            successful.append(
                WorkspaceMemberInviteResponse(
                    invitation_id=invitation.id,
                    email=invite.email,
                    role=invite.role,
                    status="pending",
                    expires_at=invitation.expires_at,
                )
            )
        except Exception as e:
            failed.append({"email": invite.email, "error": str(e)})

    return BulkInviteResponse(successful=successful, failed=failed)


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberWithUser],
    summary="List members",
    description="List all members of a workspace.",
)
async def list_members(
    workspace_id: UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkspaceMemberWithUser]:
    """
    List all workspace members.
    """
    workspace_service = WorkspaceService(session)

    members = await workspace_service.list_members(
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
    )

    return [
        workspace_service.to_member_with_user(m)
        for m in members
    ]


@router.put(
    "/{workspace_id}/members/{member_id}",
    response_model=WorkspaceMemberResponse,
    responses={
        200: {"model": WorkspaceMemberResponse, "description": "Member updated"},
        404: {"model": ErrorResponse, "description": "Member not found"},
    },
    summary="Update member role",
    description="Update a member's role in the workspace.",
)
async def update_member(
    workspace_id: UUID,
    member_id: UUID,
    update: WorkspaceMemberUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceMemberResponse:
    """
    Update a member's role.
    """
    workspace_service = WorkspaceService(session)

    try:
        member = await workspace_service.update_member_role(
            workspace_id=str(workspace_id),
            member_id=str(member_id),
            updater_id=str(current_user.id),
            new_role=update.role,
        )
        return workspace_service.to_member_response(member)

    except WorkspaceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except WorkspaceMemberNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.delete(
    "/{workspace_id}/members/{member_id}",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Member removed"},
        404: {"model": ErrorResponse, "description": "Member not found"},
    },
    summary="Remove member",
    description="Remove a member from the workspace.",
)
async def remove_member(
    workspace_id: UUID,
    member_id: UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Remove a member from the workspace.
    """
    workspace_service = WorkspaceService(session)

    try:
        await workspace_service.remove_member(
            workspace_id=str(workspace_id),
            member_id=str(member_id),
            remover_id=str(current_user.id),
        )
        return SuccessResponse(success=True, message="Member removed successfully")

    except WorkspaceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except WorkspaceMemberNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "/{workspace_id}/leave",
    response_model=SuccessResponse,
    summary="Leave workspace",
    description="Leave the workspace.",
)
async def leave_workspace(
    workspace_id: UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """
    Leave the workspace.
    """
    workspace_service = WorkspaceService(session)

    try:
        await workspace_service.leave_workspace(
            workspace_id=str(workspace_id),
            user_id=str(current_user.id),
        )
        return SuccessResponse(success=True, message="Left workspace successfully")

    except WorkspaceMemberNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ======================
# Permissions
# ======================


@router.post(
    "/{workspace_id}/check-permission",
    response_model=PermissionResponse,
    summary="Check permission",
    description="Check if current user has permission to perform an action.",
)
async def check_permission(
    workspace_id: UUID,
    permission: PermissionCheck,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PermissionResponse:
    """
    Check user permissions in workspace.
    """
    workspace_service = WorkspaceService(session)

    has_permission = await workspace_service.check_permission(
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        action=permission.action,
        resource=permission.resource,
    )

    return PermissionResponse(
        allowed=has_permission,
        reason=None if has_permission else "Insufficient permissions",
    )
