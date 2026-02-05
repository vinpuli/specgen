"""
Project API endpoints.

This module provides:
- Project CRUD operations
- Branch management
- Project statistics
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectWithWorkspace,
    ProjectListResponse,
    ProjectStats,
    ProjectSettingsUpdate,
    BranchCreate,
    BranchUpdate,
    BranchResponse,
    BranchWithParent,
    BranchMergeRequest,
    BranchMergeResponse,
    BranchDiff,
    BranchStats,
    TemplateCreate,
    TemplateResponse,
    TemplateListResponse,
    CreateProjectFromTemplate,
)
from backend.api.schemas.common import SuccessResponse, ErrorResponse, PaginationParams
from backend.db.connection import get_db
from backend.services.user_service import UserService
from backend.api.endpoints.auth import CurrentUser
from backend.services.project_service import (
    ProjectService,
    ProjectServiceError,
    ProjectNotFoundError,
    BranchNotFoundError,
    InsufficientPermissionsError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


# ======================
# Project CRUD
# ======================


@router.post(
    "",
    response_model=ProjectWithWorkspace,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": ProjectWithWorkspace, "description": "Project created"},
        400: {"model": ErrorResponse, "description": "Creation failed"},
    },
    summary="Create project",
    description="Create a new project in a workspace.",
)
async def create_project(
    project_data: ProjectCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ProjectWithWorkspace:
    """
    Create a new project.
    """
    project_service = ProjectService(session)

    try:
        project = await project_service.create_project(
            workspace_id=str(project_data.workspace_id),
            name=project_data.name,
            description=project_data.description,
            project_type=project_data.project_type,
            spec_template_id=str(project_data.spec_template_id) if project_data.spec_template_id else None,
            created_by=str(current_user.id),
        )
        return project_service.to_response_with_workspace(project)

    except ProjectServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
    description="List all projects in a workspace.",
)
async def list_projects(
    workspace_id: Optional[UUID] = None,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
) -> ProjectListResponse:
    """
    List projects, optionally filtered by workspace.
    """
    project_service = ProjectService(session)

    projects, total = await project_service.list_projects(
        user_id=str(current_user.id),
        workspace_id=str(workspace_id) if workspace_id else None,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return ProjectListResponse(
        projects=[project_service.to_response(p) for p in projects],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectWithWorkspace,
    responses={
        200: {"model": ProjectWithWorkspace, "description": "Project details"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
    summary="Get project",
    description="Get project details by ID.",
)
async def get_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> ProjectWithWorkspace:
    """
    Get project details.
    """
    project_service = ProjectService(session)

    try:
        project = await project_service.get_project_by_id(
            project_id=str(project_id),
            user_id=str(current_user.id),
        )
        return project_service.to_response_with_workspace(project)

    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        200: {"model": ProjectResponse, "description": "Project updated"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
    summary="Update project",
    description="Update project details.",
)
async def update_project(
    project_id: UUID,
    update: ProjectUpdate,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Update project details.
    """
    project_service = ProjectService(session)

    try:
        project = await project_service.update_project(
            project_id=str(project_id),
            user_id=str(current_user.id),
            name=update.name,
            description=update.description,
            status=update.status,
            settings=update.settings,
        )
        return project_service.to_response(project)

    except ProjectNotFoundError as e:
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
    "/{project_id}",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Project deleted"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
    summary="Delete project",
    description="Delete a project.",
)
async def delete_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """
    Delete a project.
    """
    project_service = ProjectService(session)

    try:
        await project_service.delete_project(
            project_id=str(project_id),
            user_id=str(current_user.id),
        )
        return SuccessResponse(success=True, message="Project deleted successfully")

    except ProjectNotFoundError as e:
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
# Project Statistics
# ======================


@router.get(
    "/{project_id}/stats",
    response_model=ProjectStats,
    summary="Get project statistics",
    description="Get project statistics and metrics.",
)
async def get_project_stats(
    project_id: UUID,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> ProjectStats:
    """
    Get project statistics.
    """
    project_service = ProjectService(session)

    try:
        stats = await project_service.get_project_stats(
            project_id=str(project_id),
            user_id=str(current_user.id),
        )
        return stats

    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ======================
# Branch Management
# ======================


@router.post(
    "/{project_id}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create branch",
    description="Create a new branch in a project.",
)
async def create_branch(
    project_id: UUID,
    branch_data: BranchCreate,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> BranchResponse:
    """
    Create a new branch.
    """
    project_service = ProjectService(session)

    try:
        branch = await project_service.create_branch(
            project_id=str(project_id),
            name=branch_data.name,
            parent_branch_id=str(branch_data.parent_branch_id) if branch_data.parent_branch_id else None,
            description=branch_data.description,
            created_by=str(current_user.id),
        )
        return project_service.to_branch_response(branch)

    except ProjectServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{project_id}/branches",
    response_model=list[BranchResponse],
    summary="List branches",
    description="List all branches in a project.",
)
async def list_branches(
    project_id: UUID,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> list[BranchResponse]:
    """
    List all branches in a project.
    """
    project_service = ProjectService(session)

    branches = await project_service.list_branches(
        project_id=str(project_id),
        user_id=str(current_user.id),
    )

    return [project_service.to_branch_response(b) for b in branches]


@router.get(
    "/{project_id}/branches/{branch_id}",
    response_model=BranchWithParent,
    summary="Get branch",
    description="Get branch details.",
)
async def get_branch(
    project_id: UUID,
    branch_id: UUID,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> BranchWithParent:
    """
    Get branch details.
    """
    project_service = ProjectService(session)

    try:
        branch = await project_service.get_branch(
            branch_id=str(branch_id),
            user_id=str(current_user.id),
        )
        return project_service.to_branch_with_parent(branch)

    except BranchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put(
    "/{project_id}/branches/{branch_id}",
    response_model=BranchResponse,
    summary="Update branch",
    description="Update branch details.",
)
async def update_branch(
    project_id: UUID,
    branch_id: UUID,
    update: BranchUpdate,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> BranchResponse:
    """
    Update branch details.
    """
    project_service = ProjectService(session)

    try:
        branch = await project_service.update_branch(
            branch_id=str(branch_id),
            user_id=str(current_user.id),
            name=update.name,
            description=update.description,
            status=update.status,
        )
        return project_service.to_branch_response(branch)

    except BranchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{project_id}/branches/merge",
    response_model=BranchMergeResponse,
    summary="Merge branches",
    description="Merge one branch into another.",
)
async def merge_branches(
    project_id: UUID,
    merge_request: BranchMergeRequest,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> BranchMergeResponse:
    """
    Merge source branch into target branch.
    """
    project_service = ProjectService(session)

    try:
        result = await project_service.merge_branches(
            project_id=str(project_id),
            target_branch_id=str(merge_request.target_branch_id),
            source_branch_id=str(merge_request.source_branch_id),
            user_id=str(current_user.id),
            commit_message=merge_request.commit_message,
        )
        return result

    except ProjectServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{project_id}/branches/{branch_id}/stats",
    response_model=BranchStats,
    summary="Get branch statistics",
    description="Get branch statistics.",
)
async def get_branch_stats(
    project_id: UUID,
    branch_id: UUID,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> BranchStats:
    """
    Get branch statistics.
    """
    project_service = ProjectService(session)

    try:
        stats = await project_service.get_branch_stats(
            branch_id=str(branch_id),
            user_id=str(current_user.id),
        )
        return stats

    except BranchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ======================
# Project Templates
# ======================


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create template",
    description="Create a project template.",
)
async def create_template(
    template_data: TemplateCreate,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """
    Create a project template.
    """
    project_service = ProjectService(session)

    template = await project_service.create_template(
        workspace_id=str(template_data.workspace_id),
        name=template_data.name,
        description=template_data.description,
        category=template_data.category,
        questions=template_data.questions,
        decisions=template_data.decisions,
        is_public=template_data.is_public,
        created_by=str(current_user.id),
    )

    return project_service.to_template_response(template)


@router.get(
    "/templates",
    response_model=TemplateListResponse,
    summary="List templates",
    description="List project templates.",
)
async def list_templates(
    workspace_id: Optional[UUID] = None,
    current_user: Optional[CurrentUser] = None,
    session: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
) -> TemplateListResponse:
    """
    List templates, optionally filtered by workspace.
    """
    project_service = ProjectService(session)

    templates, total = await project_service.list_templates(
        workspace_id=str(workspace_id) if workspace_id else None,
        user_id=str(current_user.id) if current_user else None,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return TemplateListResponse(
        templates=[project_service.to_template_response(t) for t in templates],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/from-template",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project from template",
    description="Create a new project from a template.",
)
async def create_from_template(
    request: CreateProjectFromTemplate,
    current_user: CurrentUser = Depends(),
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Create a new project from a template.
    """
    project_service = ProjectService(session)

    project = await project_service.create_project_from_template(
        template_id=str(request.template_id),
        project_name=request.project_name,
        project_description=request.project_description,
        branch_name=request.branch_name,
        created_by=str(current_user.id),
    )

    return project_service.to_response(project)
