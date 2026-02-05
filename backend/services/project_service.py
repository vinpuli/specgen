"""
Project service for project and branch management.

This module provides:
- Project CRUD operations
- Branch management
- Template management
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.project import Project, Branch, Template, ProjectStatus, BranchStatus
from backend.services.workspace_service import WorkspaceService, InsufficientPermissionsError

logger = logging.getLogger(__name__)


class ProjectServiceError(Exception):
    """Base exception for project service errors."""

    pass


class ProjectNotFoundError(ProjectServiceError):
    """Raised when project is not found."""

    pass


class BranchNotFoundError(ProjectServiceError):
    """Raised when branch is not found."""

    pass


class TemplateNotFoundError(ProjectServiceError):
    """Raised when template is not found."""

    pass


class ProjectService:
    """
    Project service for managing projects and branches.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize project service.

        Args:
            session: Async database session.
        """
        self.session = session
        self.workspace_service = WorkspaceService(session)

    # ======================
    # Project CRUD
    # ======================

    async def create_project(
        self,
        workspace_id: str,
        name: str,
        description: Optional[str] = None,
        project_type: str = "greenfield",
        spec_template_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            workspace_id: Workspace ID.
            name: Project name.
            description: Project description.
            project_type: Project type (greenfield/brownfield).
            spec_template_id: Optional template ID.
            created_by: User ID creating the project.

        Returns:
            Created Project.
        """
        # Check workspace access
        await self.workspace_service.get_workspace_by_id(workspace_id)

        project = Project(
            workspace_id=workspace_id,
            name=name,
            description=description,
            project_type=project_type,
            status=ProjectStatus.DRAFT,
            settings={},
            created_by=created_by,
            spec_template_id=spec_template_id,
        )

        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)

        # Create main branch
        main_branch = Branch(
            project_id=str(project.id),
            name="main",
            description="Main branch",
            status=BranchStatus.ACTIVE,
            created_by=created_by,
        )
        self.session.add(main_branch)
        await self.session.commit()

        logger.info(f"Project created: {project.name} ({project.id})")
        return project

    async def get_project_by_id(
        self,
        project_id: str,
        user_id: Optional[str] = None,
    ) -> Project:
        """
        Get project by ID.

        Args:
            project_id: Project ID.
            user_id: Optional user ID for permission check.

        Returns:
            Project.

        Raises:
            ProjectNotFoundError: If project not found.
        """
        result = await self.session.execute(
            select(Project)
            .options(selectinload(Project.workspace))
            .where(Project.id == project_id)
            .where(Project.is_active == True)  # type: ignore
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ProjectNotFoundError(f"Project not found: {project_id}")

        # Check workspace access
        await self.workspace_service.get_workspace_by_id(
            str(project.workspace_id),
            user_id=user_id,
        )

        return project

    async def list_projects(
        self,
        user_id: str,
        workspace_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Project], int]:
        """
        List projects.

        Args:
            user_id: User ID.
            workspace_id: Optional workspace filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (projects, total_count).
        """
        # Build query
        query = (
            select(Project)
            .options(selectinload(Project.workspace))
            .where(Project.is_active == True)  # type: ignore
        )

        if workspace_id:
            query = query.where(Project.workspace_id == workspace_id)
        else:
            # Get user's workspaces
            query = query.where(
                Project.workspace_id.in_(
                    select(WorkspaceService.workspace_id).where(  # type: ignore
                        WorkspaceMember.user_id == user_id
                    )
                )
            )

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        projects = list(result.scalars().all())

        # Get total count
        count_query = select(Project).where(Project.is_active == True)  # type: ignore
        if workspace_id:
            count_query = count_query.where(Project.workspace_id == workspace_id)
        else:
            count_query = count_query.where(
                Project.workspace_id.in_(
                    select(WorkspaceService.workspace_id).where(  # type: ignore
                        WorkspaceMember.user_id == user_id
                    )
                )
            )
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        return projects, total

    async def update_project(
        self,
        project_id: str,
        user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        settings: Optional[dict] = None,
    ) -> Project:
        """
        Update project details.

        Args:
            project_id: Project ID.
            user_id: User making the update.
            name: Optional new name.
            description: Optional new description.
            status: Optional new status.
            settings: Optional new settings.

        Returns:
            Updated Project.

        Raises:
            ProjectNotFoundError: If project not found.
            InsufficientPermissionsError: If user lacks permission.
        """
        project = await self.get_project_by_id(project_id)

        # Check permission
        has_permission = await self.workspace_service.check_permission(
            workspace_id=str(project.workspace_id),
            user_id=user_id,
            action="update",
            resource="project",
        )
        if not has_permission:
            raise InsufficientPermissionsError("Cannot update project")

        if name:
            project.name = name
        if description is not None:
            project.description = description
        if status:
            project.status = status
        if settings is not None:
            project.settings = settings

        await self.session.commit()
        await self.session.refresh(project)

        logger.info(f"Project updated: {project.name}")
        return project

    async def delete_project(
        self,
        project_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete (deactivate) a project.

        Args:
            project_id: Project ID.
            user_id: User making the request.

        Returns:
            True if successful.

        Raises:
            ProjectNotFoundError: If project not found.
            InsufficientPermissionsError: If user lacks permission.
        """
        project = await self.get_project_by_id(project_id)

        # Check permission
        has_permission = await self.workspace_service.check_permission(
            workspace_id=str(project.workspace_id),
            user_id=user_id,
            action="delete",
            resource="project",
        )
        if not has_permission:
            raise InsufficientPermissionsError("Cannot delete project")

        project.is_active = False  # type: ignore
        await self.session.commit()

        logger.info(f"Project deleted: {project.name}")
        return True

    async def get_project_stats(
        self,
        project_id: str,
        user_id: str,
    ) -> dict:
        """
        Get project statistics.

        Args:
            project_id: Project ID.
            user_id: User ID.

        Returns:
            Statistics dict.
        """
        project = await self.get_project_by_id(project_id, user_id)

        # Get counts
        branches = await self.list_branches(project_id, user_id)
        # TODO: Get decision and artifact counts

        return {
            "project_id": str(project.id),
            "total_branches": len(branches),
            "total_decisions": 0,  # TODO: Implement
            "total_artifacts": 0,  # TODO: Implement
            "completed_artifacts": 0,
            "contributors": 0,  # TODO: Implement
            "last_activity": project.updated_at,
        }

    # ======================
    # Branch Management
    # ======================

    async def create_branch(
        self,
        project_id: str,
        name: str,
        parent_branch_id: Optional[str] = None,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Branch:
        """
        Create a new branch.

        Args:
            project_id: Project ID.
            name: Branch name.
            parent_branch_id: Parent branch ID.
            description: Branch description.
            created_by: User ID.

        Returns:
            Created Branch.

        Raises:
            ProjectNotFoundError: If project not found.
        """
        # Verify project exists
        await self.get_project_by_id(project_id)

        # Check parent branch if specified
        if parent_branch_id:
            parent = await self.get_branch(parent_branch_id)
            if str(parent.project_id) != project_id:
                raise ProjectServiceError("Parent branch belongs to different project")

        branch = Branch(
            project_id=project_id,
            name=name,
            parent_branch_id=parent_branch_id,
            description=description,
            status=BranchStatus.ACTIVE,
            created_by=created_by,
        )

        self.session.add(branch)
        await self.session.commit()
        await self.session.refresh(branch)

        logger.info(f"Branch created: {branch.name} in project {project_id}")
        return branch

    async def get_branch(
        self,
        branch_id: str,
        user_id: Optional[str] = None,
    ) -> Branch:
        """
        Get branch by ID.

        Args:
            branch_id: Branch ID.
            user_id: Optional user ID for permission check.

        Returns:
            Branch.

        Raises:
            BranchNotFoundError: If branch not found.
        """
        result = await self.session.execute(
            select(Branch)
            .options(selectinload(Branch.project))
            .where(Branch.id == branch_id)
            .where(Branch.is_active == True)  # type: ignore
        )
        branch = result.scalar_one_or_none()

        if not branch:
            raise BranchNotFoundError(f"Branch not found: {branch_id}")

        if user_id:
            await self.get_project_by_id(str(branch.project_id), user_id)

        return branch

    async def list_branches(
        self,
        project_id: str,
        user_id: Optional[str] = None,
    ) -> List[Branch]:
        """
        List all branches in a project.

        Args:
            project_id: Project ID.
            user_id: Optional user ID for permission check.

        Returns:
            List of Branches.
        """
        if user_id:
            await self.get_project_by_id(project_id, user_id)

        result = await self.session.execute(
            select(Branch)
            .where(Branch.project_id == project_id)
            .where(Branch.is_active == True)  # type: ignore
            .order_by(Branch.created_at)
        )
        return list(result.scalars().all())

    async def update_branch(
        self,
        branch_id: str,
        user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Branch:
        """
        Update branch details.

        Args:
            branch_id: Branch ID.
            user_id: User making the update.
            name: Optional new name.
            description: Optional new description.
            status: Optional new status.

        Returns:
            Updated Branch.

        Raises:
            BranchNotFoundError: If branch not found.
        """
        branch = await self.get_branch(branch_id)

        if name:
            branch.name = name
        if description is not None:
            branch.description = description
        if status:
            branch.status = status

        await self.session.commit()
        await self.session.refresh(branch)

        logger.info(f"Branch updated: {branch.name}")
        return branch

    async def merge_branches(
        self,
        project_id: str,
        target_branch_id: str,
        source_branch_id: str,
        user_id: str,
        commit_message: Optional[str] = None,
    ) -> dict:
        """
        Merge source branch into target branch.

        Args:
            project_id: Project ID.
            target_branch_id: Branch to merge into.
            source_branch_id: Branch to merge from.
            user_id: User performing the merge.
            commit_message: Optional commit message.

        Returns:
            Merge result dict.
        """
        # Verify branches exist
        target = await self.get_branch(target_branch_id)
        source = await self.get_branch(source_branch_id)

        if str(source.project_id) != project_id:
            raise ProjectServiceError("Source branch belongs to different project")

        # TODO: Implement actual merge logic

        # Update source branch status
        source.status = BranchStatus.MERGED
        source.merged_at = datetime.now(timezone.utc)
        source.merged_by = user_id

        await self.session.commit()

        logger.info(
            f"Branches merged: {source.name} -> {target.name} in project {project_id}"
        )

        return {
            "success": True,
            "source_branch": self.to_branch_response(source),
            "target_branch": self.to_branch_response(target),
            "merged_at": source.merged_at,
            "conflicts": None,
        }

    async def get_branch_stats(
        self,
        branch_id: str,
        user_id: str,
    ) -> dict:
        """
        Get branch statistics.

        Args:
            branch_id: Branch ID.
            user_id: User ID.

        Returns:
            Statistics dict.
        """
        branch = await self.get_branch(branch_id, user_id)

        return {
            "branch_id": str(branch.id),
            "total_decisions": 0,  # TODO: Implement
            "completed_decisions": 0,
            "total_artifacts": 0,
            "merged_decisions": 0,
            "created_by": branch.created_by,
            "created_at": branch.created_at,
            "last_activity": branch.updated_at,
        }

    # ======================
    # Template Management
    # ======================

    async def create_template(
        self,
        workspace_id: str,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        questions: Optional[list] = None,
        decisions: Optional[list] = None,
        is_public: bool = False,
        created_by: Optional[str] = None,
    ) -> Template:
        """
        Create a project template.

        Args:
            workspace_id: Workspace ID.
            name: Template name.
            description: Template description.
            category: Template category.
            questions: Template questions.
            decisions: Template decisions.
            is_public: Whether template is public.
            created_by: User ID.

        Returns:
            Created Template.
        """
        template = Template(
            workspace_id=workspace_id,
            name=name,
            description=description,
            category=category,
            questions=questions or [],
            decisions=decisions or [],
            is_public=is_public,
            created_by=created_by,
        )

        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)

        logger.info(f"Template created: {template.name}")
        return template

    async def list_templates(
        self,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Template], int]:
        """
        List templates.

        Args:
            workspace_id: Optional workspace filter.
            user_id: Optional user ID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (templates, total_count).
        """
        query = select(Template).where(Template.is_active == True)  # type: ignore

        if workspace_id:
            query = query.where(Template.workspace_id == workspace_id)
        elif user_id:
            # Include public templates and user's templates
            query = query.where(
                (Template.is_public == True) | (Template.created_by == user_id)  # type: ignore
            )

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        templates = list(result.scalars().all())

        # Get total count
        count_query = select(Template).where(Template.is_active == True)  # type: ignore
        if workspace_id:
            count_query = count_query.where(Template.workspace_id == workspace_id)
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        return templates, total

    async def create_project_from_template(
        self,
        template_id: str,
        project_name: str,
        project_description: Optional[str] = None,
        branch_name: str = "main",
        created_by: Optional[str] = None,
    ) -> Project:
        """
        Create a new project from a template.

        Args:
            template_id: Template ID.
            project_name: Name for the new project.
            project_description: Optional project description.
            branch_name: Initial branch name.
            created_by: User ID.

        Returns:
            Created Project.
        """
        result = await self.session.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            raise TemplateNotFoundError(f"Template not found: {template_id}")

        # Create project
        project = await self.create_project(
            workspace_id=str(template.workspace_id),
            name=project_name,
            description=project_description,
            project_type="greenfield",
            spec_template_id=template_id,
            created_by=created_by,
        )

        logger.info(f"Project created from template: {project.name}")
        return project

    # ======================
    # Response Helpers
    # ======================

    def to_response(self, project: Project) -> dict:
        """Convert Project to response dict."""
        return {
            "id": str(project.id),
            "workspace_id": str(project.workspace_id),
            "name": project.name,
            "description": project.description,
            "project_type": project.project_type,
            "status": project.status.value if project.status else None,
            "settings": project.settings or {},
            "created_by": project.created_by,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    def to_response_with_workspace(self, project: Project) -> dict:
        """Convert Project to response with workspace info."""
        response = self.to_response(project)
        if project.workspace:
            response["workspace"] = {
                "id": str(project.workspace.id),
                "name": project.workspace.name,
                "slug": project.workspace.slug,
            }
        return response

    def to_branch_response(self, branch: Branch) -> dict:
        """Convert Branch to response dict."""
        return {
            "id": str(branch.id),
            "project_id": str(branch.project_id),
            "name": branch.name,
            "parent_branch_id": str(branch.parent_branch_id) if branch.parent_branch_id else None,
            "description": branch.description,
            "status": branch.status.value if branch.status else None,
            "merged_at": branch.merged_at,
            "merged_by": branch.merged_by,
            "created_at": branch.created_at,
            "updated_at": branch.updated_at,
        }

    def to_branch_with_parent(self, branch: Branch) -> dict:
        """Convert Branch to response with parent info."""
        response = self.to_branch_response(branch)
        if branch.parent_branch:
            response["parent_branch"] = self.to_branch_response(branch.parent_branch)
        return response

    def to_template_response(self, template: Template) -> dict:
        """Convert Template to response dict."""
        return {
            "id": str(template.id),
            "workspace_id": str(template.workspace_id),
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "questions": template.questions or [],
            "decisions": template.decisions or [],
            "is_public": template.is_public,
            "usage_count": template.usage_count,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }


# Import for relationship setup
from backend.db.models.workspace import WorkspaceMember
