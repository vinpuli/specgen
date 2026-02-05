"""
Workspace repository for workspace data access operations.

This module implements the repository pattern for Workspace and WorkspaceMember models,
providing data access methods for multi-tenant workspace management.
"""

import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from backend.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    """
    Repository for Workspace data access operations.

    Provides methods for:
    - Workspace CRUD operations
    - Workspace membership management
    - Role-based access control
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the WorkspaceRepository.

        Args:
            session: The async database session.
        """
        super().__init__(Workspace, session)

    async def get_by_slug(self, slug: str) -> Optional[Workspace]:
        """
        Get a workspace by its slug.

        Args:
            slug: The workspace slug.

        Returns:
            The workspace if found, None otherwise.
        """
        query = select(Workspace).where(Workspace.slug == slug)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_owner(self, owner_id: uuid.UUID) -> List[Workspace]:
        """
        Get all workspaces owned by a user.

        Args:
            owner_id: The owner's user ID.

        Returns:
            List of workspaces.
        """
        query = (
            select(Workspace)
            .where(Workspace.owner_id == owner_id)
            .order_by(Workspace.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_workspaces(
        self, skip: int = 0, limit: int = 100
    ) -> List[Workspace]:
        """
        Get all active workspaces with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of active workspaces.
        """
        query = (
            select(Workspace)
            .where(Workspace.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(Workspace.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_workspace_with_members(
        self, workspace_id: uuid.UUID
    ) -> Optional[Workspace]:
        """
        Get a workspace with all members loaded.

        Args:
            workspace_id: The workspace ID.

        Returns:
            The workspace with members loaded.
        """
        query = (
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(
                selectinload(Workspace.members).selectinload(
                    WorkspaceMember.user
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_workspace_with_details(
        self, workspace_id: uuid.UUID
    ) -> Optional[Workspace]:
        """
        Get a workspace with members, projects, and templates loaded.

        Args:
            workspace_id: The workspace ID.

        Returns:
            The workspace with all relationships loaded.
        """
        query = (
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(
                selectinload(Workspace.members).selectinload(
                    WorkspaceMember.user
                ),
                selectinload(Workspace.projects),
                selectinload(Workspace.templates),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def search_workspaces(
        self, query: str, limit: int = 50
    ) -> List[Workspace]:
        """
        Search workspaces by name (case-insensitive partial match).

        Args:
            query: The search query.
            limit: Maximum number of results.

        Returns:
            List of matching workspaces.
        """
        search_query = (
            select(Workspace)
            .where(
                and_(
                    Workspace.is_active == True,
                    or_(
                        Workspace.name.ilike(f"%{query}%"),
                        Workspace.description.ilike(f"%{query}%"),
                    ),
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(search_query)
        return list(result.scalars().all())

    async def deactivate(self, workspace_id: uuid.UUID) -> Optional[Workspace]:
        """
        Deactivate a workspace.

        Args:
            workspace_id: The workspace ID.

        Returns:
            The deactivated workspace if found.
        """
        return await self.update(workspace_id, is_active=False)

    async def activate(self, workspace_id: uuid.UUID) -> Optional[Workspace]:
        """
        Activate a workspace.

        Args:
            workspace_id: The workspace ID.

        Returns:
            The activated workspace if found.
        """
        return await self.update(workspace_id, is_active=True)

    async def update_settings(
        self, workspace_id: uuid.UUID, settings: dict
    ) -> Optional[Workspace]:
        """
        Update workspace settings.

        Args:
            workspace_id: The workspace ID.
            settings: New settings dictionary.

        Returns:
            The updated workspace if found.
        """
        return await self.update(workspace_id, settings=settings)


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    """
    Repository for WorkspaceMember data access operations.

    Provides methods for:
    - Membership CRUD operations
    - Role management
    - Membership queries
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the WorkspaceMemberRepository.

        Args:
            session: The async database session.
        """
        super().__init__(WorkspaceMember, session)

    async def get_by_workspace_and_user(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[WorkspaceMember]:
        """
        Get a membership by workspace and user.

        Args:
            workspace_id: The workspace ID.
            user_id: The user ID.

        Returns:
            The membership if found, None otherwise.
        """
        query = select(WorkspaceMember).where(
            and_(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_workspace_members(
        self, workspace_id: uuid.UUID, role: Optional[WorkspaceRole] = None
    ) -> List[WorkspaceMember]:
        """
        Get all members of a workspace.

        Args:
            workspace_id: The workspace ID.
            role: Optional role filter.

        Returns:
            List of workspace members.
        """
        query = (
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .options(selectinload(WorkspaceMember.user))
        )

        if role:
            query = query.where(WorkspaceMember.role == role)

        query = query.order_by(WorkspaceMember.joined_at)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_workspaces(self, user_id: uuid.UUID) -> List[WorkspaceMember]:
        """
        Get all workspaces a user is a member of.

        Args:
            user_id: The user ID.

        Returns:
            List of workspace memberships.
        """
        query = (
            select(WorkspaceMember)
            .where(
                and_(
                    WorkspaceMember.user_id == user_id,
                    WorkspaceMember.is_active == True,
                )
            )
            .options(selectinload(WorkspaceMember.workspace))
            .order_by(WorkspaceMember.joined_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_admin_members(self, workspace_id: uuid.UUID) -> List[WorkspaceMember]:
        """
        Get all admin members of a workspace.

        Args:
            workspace_id: The workspace ID.

        Returns:
            List of admin members.
        """
        return await self.get_workspace_members(
            workspace_id, role=WorkspaceRole.ADMIN
        )

    async def get_editor_members(self, workspace_id: uuid.UUID) -> List[WorkspaceMember]:
        """
        Get all editor members of a workspace.

        Args:
            workspace_id: The workspace ID.

        Returns:
            List of editor members.
        """
        return await self.get_workspace_members(
            workspace_id, role=WorkspaceRole.EDITOR
        )

    async def is_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """
        Check if a user is a member of a workspace.

        Args:
            workspace_id: The workspace ID.
            user_id: The user ID.

        Returns:
            True if the user is a member.
        """
        membership = await self.get_by_workspace_and_user(workspace_id, user_id)
        return membership is not None and membership.is_active

    async def is_admin(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """
        Check if a user is an admin of a workspace.

        Args:
            workspace_id: The workspace ID.
            user_id: The user ID.

        Returns:
            True if the user is an admin.
        """
        membership = await self.get_by_workspace_and_user(workspace_id, user_id)
        return (
            membership is not None
            and membership.is_active
            and membership.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
        )

    async def is_editor(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """
        Check if a user can edit a workspace.

        Args:
            workspace_id: The workspace ID.
            user_id: The user ID.

        Returns:
            True if the user can edit.
        """
        membership = await self.get_by_workspace_and_user(workspace_id, user_id)
        if membership is None or not membership.is_active:
            return False
        return membership.role in (
            WorkspaceRole.OWNER,
            WorkspaceRole.ADMIN,
            WorkspaceRole.EDITOR,
        )

    async def update_role(
        self,
        membership_id: uuid.UUID,
        role: WorkspaceRole,
        updated_by: uuid.UUID,
    ) -> Optional[WorkspaceMember]:
        """
        Update a member's role.

        Args:
            membership_id: The membership ID.
            role: The new role.
            updated_by: The user ID making the update.

        Returns:
            The updated membership if found.
        """
        return await self.update(membership_id, role=role)

    async def deactivate_membership(
        self, membership_id: uuid.UUID
    ) -> Optional[WorkspaceMember]:
        """
        Deactivate a membership.

        Args:
            membership_id: The membership ID.

        Returns:
            The deactivated membership if found.
        """
        return await self.update(membership_id, is_active=False)

    async def remove_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """
        Remove a member from a workspace.

        Args:
            workspace_id: The workspace ID.
            user_id: The user ID.

        Returns:
            True if removed, False if not found.
        """
        membership = await self.get_by_workspace_and_user(workspace_id, user_id)
        if membership:
            return await self.delete(membership.id)
        return False

    async def get_member_count(self, workspace_id: uuid.UUID) -> int:
        """
        Get the count of active members in a workspace.

        Args:
            workspace_id: The workspace ID.

        Returns:
            Number of active members.
        """
        from sqlalchemy import func

        query = (
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.is_active == True,
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one() or 0
