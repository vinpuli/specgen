"""
Workspace service for workspace and membership management.

This module provides:
- Workspace CRUD operations
- Membership management
- Role-based access control
"""

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceRole,
)
from backend.db.models.user import User
from backend.db.models.workspace import Workspace, WorkspaceMember
from backend.services.permission_service import (
    PermissionService,
    PermissionError,
    NotWorkspaceMemberError,
)

logger = logging.getLogger(__name__)


class WorkspaceServiceError(Exception):
    """Base exception for workspace service errors."""

    pass


class WorkspaceNotFoundError(WorkspaceServiceError):
    """Raised when workspace is not found."""

    pass


class WorkspaceSlugExistsError(WorkspaceServiceError):
    """Raised when workspace slug already exists."""

    pass


class DuplicateMemberError(WorkspaceServiceError):
    """Raised when user is already a member."""

    pass


class WorkspaceService:
    """
    Workspace service for workspace and membership management.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize workspace service.

        Args:
            session: Async database session.
        """
        self.session = session
        self.permission_service = PermissionService(session)

    async def create_workspace(
        self, user_id: UUID, data: WorkspaceCreate
    ) -> tuple[Workspace, WorkspaceMember]:
        """
        Create a new workspace with the user as owner.

        Args:
            user_id: Owner's user ID.
            data: Workspace creation data.

        Returns:
            Tuple of (Workspace, WorkspaceMember).

        Raises:
            WorkspaceSlugExistsError: If slug already exists.
        """
        # Check if slug exists
        existing = await self.get_by_slug(data.slug)
        if existing:
            raise WorkspaceSlugExistsError(f"Workspace with slug '{data.slug}' already exists")

        # Create workspace
        workspace = Workspace(
            name=data.name,
            slug=data.slug,
            description=data.description,
            owner_id=user_id,
            plan_tier="free",  # Default to free tier
            settings={},
            is_active=True,
        )

        self.session.add(workspace)
        await self.session.commit()
        await self.session.refresh(workspace)

        # Create owner membership
        membership = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
            invited_by=user_id,
            is_active=True,
            joined_at=datetime.now(timezone.utc),
        )

        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)

        logger.info(f"Workspace created: {workspace.slug} by user {user_id}")
        return workspace, membership

    async def get_by_id(self, workspace_id: UUID) -> Optional[Workspace]:
        """
        Get workspace by ID.

        Args:
            workspace_id: Workspace UUID.

        Returns:
            Workspace if found, None otherwise.
        """
        result = await self.session.execute(
            select(Workspace).where(
                Workspace.id == workspace_id,
                Workspace.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Workspace]:
        """
        Get workspace by slug.

        Args:
            slug: Workspace slug.

        Returns:
            Workspace if found, None otherwise.
        """
        result = await self.session.execute(
            select(Workspace).where(
                Workspace.slug == slug,
                Workspace.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def update_workspace(
        self, workspace_id: UUID, user_id: UUID, data: WorkspaceUpdate
    ) -> Workspace:
        """
        Update workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User ID making the update.
            data: Update data.

        Returns:
            Updated Workspace.

        Raises:
            WorkspaceNotFoundError: If workspace not found.
            PermissionError: If user lacks permission.
        """
        workspace = await self.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")

        # Check permission
        await self.permission_service.can_admin(workspace_id, user_id)

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(workspace, field, value)

        await self.session.commit()
        await self.session.refresh(workspace)

        logger.info(f"Workspace updated: {workspace.slug} by user {user_id}")
        return workspace

    async def delete_workspace(self, workspace_id: UUID, user_id: UUID) -> bool:
        """
        Delete (deactivate) workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User ID making the request.

        Returns:
            True if deleted.

        Raises:
            WorkspaceNotFoundError: If workspace not found.
            PermissionError: If user lacks permission.
        """
        workspace = await self.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")

        # Only owner can delete
        await self.permission_service.is_owner(workspace_id, user_id)

        workspace.is_active = False
        await self.session.commit()

        logger.info(f"Workspace deleted: {workspace.slug} by user {user_id}")
        return True

    async def get_user_workspaces(self, user_id: UUID) -> list[Workspace]:
        """
        Get all workspaces user is a member of.

        Args:
            user_id: User UUID.

        Returns:
            List of workspaces.
        """
        result = await self.session.execute(
            select(Workspace).join(
                WorkspaceMember,
                Workspace.id == WorkspaceMember.workspace_id,
            ).where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_active == True,
                Workspace.is_active == True,
            )
        )
        return list(result.scalars().unique().all())

    async def add_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceRole,
        invited_by: UUID,
    ) -> WorkspaceMember:
        """
        Add a member to workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID to add.
            role: Role to assign.
            invited_by: User ID of inviter.

        Returns:
            Created WorkspaceMember.

        Raises:
            PermissionError: If inviter cannot invite.
        """
        return await self.permission_service.add_member(
            workspace_id, user_id, role, invited_by
        )

    async def remove_member(
        self, workspace_id: UUID, user_id: UUID, removed_by: UUID
    ) -> bool:
        """
        Remove a member from workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID to remove.
            removed_by: User ID of person removing.

        Returns:
            True if removed.

        Raises:
            PermissionError: If remover cannot remove members.
        """
        return await self.permission_service.remove_member(
            workspace_id, user_id, removed_by
        )

    async def update_member_role(
        self,
        workspace_id: UUID,
        user_id: UUID,
        new_role: WorkspaceRole,
        updated_by: UUID,
    ) -> WorkspaceMember:
        """
        Update member's role.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID to update.
            new_role: New role to assign.
            updated_by: User ID of person updating.

        Returns:
            Updated WorkspaceMember.

        Raises:
            PermissionError: If updater cannot change roles.
        """
        return await self.permission_service.update_member_role(
            workspace_id, user_id, new_role, updated_by
        )

    async def get_members(self, workspace_id: UUID, user_id: UUID) -> list[WorkspaceMember]:
        """
        Get all active members of workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID requesting.

        Returns:
            List of active workspace members.
        """
        return await self.permission_service.get_workspace_members(workspace_id, user_id)

    async def get_member(
        self, workspace_id: UUID, user_id: UUID
    ) -> Optional[WorkspaceMember]:
        """
        Get user's membership in workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.

        Returns:
            WorkspaceMember if found, None otherwise.
        """
        return await self.permission_service.get_workspace_membership(workspace_id, user_id)

    async def to_response(self, workspace: Workspace) -> dict:
        """
        Convert workspace to response dict.

        Args:
            workspace: Workspace model.

        Returns:
            Response dict.
        """
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
            "owner_id": workspace.owner_id,
            "plan_tier": workspace.plan_tier.value if workspace.plan_tier else "free",
            "settings": workspace.settings or {},
            "is_active": workspace.is_active,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
            "member_count": len(workspace.members) + 1 if workspace.members else 1,
        }

    async def member_to_response(
        self, membership: WorkspaceMember, include_user_info: bool = True
    ) -> dict:
        """
        Convert membership to response dict.

        Args:
            membership: WorkspaceMember model.
            include_user_info: Whether to include user info.

        Returns:
            Response dict.
        """
        response = {
            "id": membership.id,
            "workspace_id": membership.workspace_id,
            "user_id": membership.user_id,
            "role": membership.role.value,
            "is_active": membership.is_active,
            "joined_at": membership.joined_at,
            "invited_by": membership.invited_by,
            "created_at": membership.created_at,
            "updated_at": membership.updated_at,
            "can_edit": membership.can_edit(),
            "can_admin": membership.can_admin(),
            "can_delete": membership.can_delete(),
            "can_invite": membership.can_invite(),
            "can_remove_member": membership.can_remove_member(),
            "can_change_role": membership.can_change_role(),
        }

        if include_user_info:
            # Get user info
            result = await self.session.execute(
                select(User).where(User.id == membership.user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                response["email"] = user.email
                response["full_name"] = user.full_name
                response["avatar_url"] = user.avatar_url

        return response
