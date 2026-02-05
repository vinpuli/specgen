"""
Permission service for role-based access control.

This module provides:
- Permission checking for workspace resources
- Role validation
- Access control enforcement
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.workspace import Workspace, WorkspaceMember, WorkspaceRole

logger = logging.getLogger(__name__)


class PermissionError(Exception):
    """Base exception for permission errors."""

    pass


class InsufficientPermissionError(PermissionError):
    """Raised when user lacks required permission."""

    pass


class NotWorkspaceMemberError(PermissionError):
    """Raised when user is not a workspace member."""

    pass


class WorkspaceNotFoundError(PermissionError):
    """Raised when workspace is not found."""

    pass


class PermissionService:
    """
    Permission service for role-based access control.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize permission service.

        Args:
            session: Async database session.
        """
        self.session = session

    async def get_workspace_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> Optional[WorkspaceMember]:
        """
        Get user's membership in a workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.

        Returns:
            WorkspaceMember if found, None otherwise.
        """
        result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_workspace(self, workspace_id: UUID) -> Optional[Workspace]:
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

    async def check_workspace_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember:
        """
        Check if user is a member of workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.

        Returns:
            WorkspaceMember if user is a member.

        Raises:
            NotWorkspaceMemberError: If user is not a member.
        """
        membership = await self.get_workspace_membership(workspace_id, user_id)
        if not membership:
            raise NotWorkspaceMemberError(
                f"User {user_id} is not a member of workspace {workspace_id}"
            )
        return membership

    async def check_permission(
        self,
        workspace_id: UUID,
        user_id: UUID,
        required_roles: list[WorkspaceRole],
    ) -> WorkspaceMember:
        """
        Check if user has required permission.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.
            required_roles: List of roles that grant access.

        Returns:
            WorkspaceMember if user has permission.

        Raises:
            NotWorkspaceMemberError: If user is not a member.
            InsufficientPermissionError: If user lacks required permission.
        """
        membership = await self.check_workspace_membership(workspace_id, user_id)

        if membership.role not in required_roles:
            raise InsufficientPermissionError(
                f"User requires one of roles: {[r.value for r in required_roles]}, "
                f"has: {membership.role.value}"
            )

        return membership

    async def can_view(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember:
        """
        Check if user can view workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.

        Returns:
            WorkspaceMember if user can view.

        Raises:
            NotWorkspaceMemberError: If user is not a member.
        """
        return await self.check_permission(
            workspace_id, user_id, [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR, WorkspaceRole.VIEWER]
        )

    async def can_edit(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember:
        """
        Check if user can edit workspace content.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.

        Returns:
            WorkspaceMember if user can edit.

        Raises:
            NotWorkspaceMemberError: If user is not a member.
            InsufficientPermissionError: If user cannot edit.
        """
        return await self.check_permission(
            workspace_id, user_id, [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR]
        )

    async def can_admin(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember:
        """
        Check if user has admin privileges.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.

        Returns:
            WorkspaceMember if user is admin.

        Raises:
            NotWorkspaceMemberError: If user is not a member.
            InsufficientPermissionError: If user is not admin.
        """
        return await self.check_permission(
            workspace_id, user_id, [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]
        )

    async def is_owner(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember:
        """
        Check if user is workspace owner.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID.

        Returns:
            WorkspaceMember if user is owner.

        Raises:
            NotWorkspaceMemberError: If user is not a member.
            InsufficientPermissionError: If user is not owner.
        """
        # First check if user is owner via ownership
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")

        if workspace.owner_id == user_id:
            # Return a membership with owner role
            membership = await self.check_workspace_membership(workspace_id, user_id)
            return membership

        return await self.check_permission(workspace_id, user_id, [WorkspaceRole.OWNER])

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
            InsufficientPermissionError: If inviter cannot invite.
        """
        # Check if inviter can invite
        inviter = await self.check_permission(
            workspace_id, invited_by, [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]
        )

        # Check if user is already a member
        existing = await self.get_workspace_membership(workspace_id, user_id)
        if existing:
            # Update role if already member
            existing.role = role
            await self.session.commit()
            await self.session.refresh(existing)
            logger.info(
                f"Updated role for user {user_id} to {role.value} in workspace {workspace_id}"
            )
            return existing

        # Create new membership
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
            is_active=True,
            joined_at=datetime.now(timezone.utc),
        )

        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)

        logger.info(
            f"Added user {user_id} as {role.value} to workspace {workspace_id}"
        )
        return membership

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
            True if removed successfully.

        Raises:
            InsufficientPermissionError: If remover cannot remove members.
        """
        # Check if remover can remove members
        remover = await self.check_permission(
            workspace_id, removed_by, [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]
        )

        # Get membership to remove
        membership = await self.get_workspace_membership(workspace_id, user_id)
        if not membership:
            raise NotWorkspaceMemberError(
                f"User {user_id} is not a member of workspace {workspace_id}"
            )

        # Owner cannot be removed
        if membership.role == WorkspaceRole.OWNER:
            raise InsufficientPermissionError("Cannot remove workspace owner")

        # Cannot remove yourself
        if user_id == removed_by:
            raise InsufficientPermissionError("Cannot remove yourself from workspace")

        membership.is_active = False
        await self.session.commit()

        logger.info(
            f"Removed user {user_id} from workspace {workspace_id} by {removed_by}"
        )
        return True

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
            InsufficientPermissionError: If updater cannot change roles.
        """
        # Only owner can change roles
        owner = await self.is_owner(workspace_id, updated_by)

        # Get membership to update
        membership = await self.get_workspace_membership(workspace_id, user_id)
        if not membership:
            raise NotWorkspaceMemberError(
                f"User {user_id} is not a member of workspace {workspace_id}"
            )

        # Cannot change owner's role
        if membership.role == WorkspaceRole.OWNER:
            raise InsufficientPermissionError("Cannot change owner's role")

        # Cannot change your own role
        if user_id == updated_by:
            raise InsufficientPermissionError("Cannot change your own role")

        membership.role = new_role
        await self.session.commit()
        await self.session.refresh(membership)

        logger.info(
            f"Updated role for user {user_id} to {new_role.value} in workspace {workspace_id} by {updated_by}"
        )
        return membership

    async def get_workspace_members(
        self, workspace_id: UUID, user_id: UUID
    ) -> list[WorkspaceMember]:
        """
        Get all active members of workspace.

        Args:
            workspace_id: Workspace UUID.
            user_id: User UUID requesting (must be member).

        Returns:
            List of active workspace members.
        """
        await self.check_workspace_membership(workspace_id, user_id)

        result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.is_active == True,
            )
        )
        return list(result.scalars().all())
