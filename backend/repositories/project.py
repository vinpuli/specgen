"""
Project repository for project data access operations.

This module implements the repository pattern for Project and Branch models,
providing data access methods for specification project management.
"""

import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.project import Project, Branch, ProjectType, ProjectStatus, BranchStatus
from backend.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """
    Repository for Project data access operations.

    Provides methods for:
    - Project CRUD operations
    - Greenfield and brownfield project queries
    - Project status management
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the ProjectRepository.

        Args:
            session: The async database session.
        """
        super().__init__(Project, session)

    async def get_by_workspace(
        self,
        workspace_id: uuid.UUID,
        status: Optional[ProjectStatus] = None,
        project_type: Optional[ProjectType] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        """
        Get all projects in a workspace with optional filters.

        Args:
            workspace_id: The workspace ID.
            status: Optional status filter.
            project_type: Optional type filter (greenfield/brownfield).
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of projects.
        """
        query = select(Project).where(Project.workspace_id == workspace_id)

        if status:
            query = query.where(Project.status == status)
        if project_type:
            query = query.where(Project.project_type == project_type)

        query = (
            query.offset(skip)
            .limit(limit)
            .order_by(Project.updated_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_creator(self, creator_id: uuid.UUID) -> List[Project]:
        """
        Get all projects created by a user.

        Args:
            creator_id: The creator's user ID.

        Returns:
            List of projects.
        """
        query = (
            select(Project)
            .where(Project.created_by == creator_id)
            .order_by(Project.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_projects(
        self, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get all active (non-archived) projects with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of active projects.
        """
        query = (
            select(Project)
            .where(
                and_(
                    Project.status != ProjectStatus.ARCHIVED,
                    Project.status != ProjectStatus.COMPLETED,
                )
            )
            .offset(skip)
            .limit(limit)
            .order_by(Project.updated_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_brownfield_projects(self) -> List[Project]:
        """
        Get all brownfield projects.

        Returns:
            List of brownfield projects.
        """
        query = select(Project).where(
            Project.project_type == ProjectType.BROWNFIELD
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_greenfield_projects(self) -> List[Project]:
        """
        Get all greenfield projects.

        Returns:
            List of greenfield projects.
        """
        query = select(Project).where(
            Project.project_type == ProjectType.GREENFIELD
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_project_with_details(
        self, project_id: uuid.UUID
    ) -> Optional[Project]:
        """
        Get a project with all relationships loaded.

        Args:
            project_id: The project ID.

        Returns:
            The project with details.
        """
        query = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.workspace),
                selectinload(Project.creator),
                selectinload(Project.branches),
                selectinload(Project.decisions),
                selectinload(Project.artifacts),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_project_with_decisions(
        self, project_id: uuid.UUID
    ) -> Optional[Project]:
        """
        Get a project with decisions loaded.

        Args:
            project_id: The project ID.

        Returns:
            The project with decisions.
        """
        query = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.decisions).selectinload(
                    "conversation_turns"
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def search_projects(
        self,
        workspace_id: uuid.UUID,
        query: str,
        limit: int = 50,
    ) -> List[Project]:
        """
        Search projects in a workspace by name or description.

        Args:
            workspace_id: The workspace ID.
            query: The search query.
            limit: Maximum number of results.

        Returns:
            List of matching projects.
        """
        search_query = (
            select(Project)
            .where(
                and_(
                    Project.workspace_id == workspace_id,
                    or_(
                        Project.name.ilike(f"%{query}%"),
                        Project.description.ilike(f"%{query}%"),
                    ),
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(search_query)
        return list(result.scalars().all())

    async def update_status(
        self, project_id: uuid.UUID, status: ProjectStatus
    ) -> Optional[Project]:
        """
        Update a project's status.

        Args:
            project_id: The project ID.
            status: The new status.

        Returns:
            The updated project if found.
        """
        return await self.update(project_id, status=status)

    async def archive(self, project_id: uuid.UUID) -> Optional[Project]:
        """
        Archive a project.

        Args:
            project_id: The project ID.

        Returns:
            The archived project if found.
        """
        return await self.update(
            project_id, status=ProjectStatus.ARCHIVED
        )

    async def complete(self, project_id: uuid.UUID) -> Optional[Project]:
        """
        Mark a project as completed.

        Args:
            project_id: The project ID.

        Returns:
            The completed project if found.
        """
        return await self.update(
            project_id, status=ProjectStatus.COMPLETED
        )

    async def get_by_repository_url(
        self, repository_url: str
    ) -> Optional[Project]:
        """
        Get a project by its repository URL.

        Args:
            repository_url: The repository URL.

        Returns:
            The project if found.
        """
        query = select(Project).where(
            Project.repository_url == repository_url
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class BranchRepository(BaseRepository[Branch]):
    """
    Repository for Branch data access operations.

    Provides methods for:
    - Branch CRUD operations
    - Branch hierarchy queries
    - Merge status management
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the BranchRepository.

        Args:
            session: The async database session.
        """
        super().__init__(Branch, session)

    async def get_by_project_and_name(
        self, project_id: uuid.UUID, name: str
    ) -> Optional[Branch]:
        """
        Get a branch by project and name.

        Args:
            project_id: The project ID.
            name: The branch name.

        Returns:
            The branch if found, None otherwise.
        """
        query = select(Branch).where(
            and_(Branch.project_id == project_id, Branch.name == name)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_project(
        self, project_id: uuid.UUID, status: Optional[BranchStatus] = None
    ) -> List[Branch]:
        """
        Get all branches of a project.

        Args:
            project_id: The project ID.
            status: Optional status filter.

        Returns:
            List of branches.
        """
        query = (
            select(Branch)
            .where(Branch.project_id == project_id)
            .options(selectinload(Branch.project))
        )

        if status:
            query = query.where(Branch.status == status)

        query = query.order_by(Branch.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_branches(self, project_id: uuid.UUID) -> List[Branch]:
        """
        Get all active branches of a project.

        Args:
            project_id: The project ID.

        Returns:
            List of active branches.
        """
        return await self.get_by_project(project_id, status=BranchStatus.ACTIVE)

    async def get_main_branch(self, project_id: uuid.UUID) -> Optional[Branch]:
        """
        Get the main/default branch of a project.

        Args:
            project_id: The project ID.

        Returns:
            The main branch if found.
        """
        project = await self.session.get(Project, project_id)
        if project:
            return await self.get_by_project_and_name(
                project_id, project.default_branch
            )
        return None

    async def get_child_branches(
        self, parent_branch_id: uuid.UUID
    ) -> List[Branch]:
        """
        Get all child branches of a parent branch.

        Args:
            parent_branch_id: The parent branch ID.

        Returns:
            List of child branches.
        """
        query = (
            select(Branch)
            .where(Branch.parent_branch_id == parent_branch_id)
            .order_by(Branch.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_branch_with_decisions(
        self, branch_id: uuid.UUID
    ) -> Optional[Branch]:
        """
        Get a branch with decisions loaded.

        Args:
            branch_id: The branch ID.

        Returns:
            The branch with decisions.
        """
        query = (
            select(Branch)
            .where(Branch.id == branch_id)
            .options(selectinload(Branch.decisions))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def merge(
        self,
        branch_id: uuid.UUID,
        merged_by: Optional[uuid.UUID] = None,
    ) -> Optional[Branch]:
        """
        Mark a branch as merged.

        Args:
            branch_id: The branch ID.
            merged_by: The user who merged.

        Returns:
            The merged branch if found.
        """
        return await self.update(
            branch_id,
            status=BranchStatus.MERGED,
            merged_at=datetime.now(timezone.utc),
        )

    async def close(self, branch_id: uuid.UUID) -> Optional[Branch]:
        """
        Close a branch.

        Args:
            branch_id: The branch ID.

        Returns:
            The closed branch if found.
        """
        return await self.update(branch_id, status=BranchStatus.CLOSED)

    async def is_mergeable(self, branch_id: uuid.UUID) -> bool:
        """
        Check if a branch can be merged.

        Args:
            branch_id: The branch ID.

        Returns:
            True if mergeable, False otherwise.
        """
        branch = await self.get_by_id(branch_id)
        return branch is not None and branch.mergeable

    async def has_conflicts(self, branch_id: uuid.UUID) -> bool:
        """
        Check if a branch has merge conflicts.

        Args:
            branch_id: The branch ID.

        Returns:
            True if conflicts exist.
        """
        branch = await self.get_by_id(branch_id)
        if branch:
            return branch.merge_conflicts is not None and len(
                branch.merge_conflicts
            ) > 0
        return False

    async def get_merged_branches(
        self, project_id: uuid.UUID
    ) -> List[Branch]:
        """
        Get all merged branches of a project.

        Args:
            project_id: The project ID.

        Returns:
            List of merged branches.
        """
        return await self.get_by_project(project_id, status=BranchStatus.MERGED)


# Import for timezone-aware datetime
from datetime import timezone  # noqa: E402
