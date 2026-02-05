"""
Artifact API endpoints.

This module provides:
- Artifact CRUD endpoints
- Version management endpoints
- Export endpoints
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.api.schemas.artifact import (
    ArtifactCreate,
    ArtifactDetail,
    ArtifactListResponse,
    ArtifactResponse,
    ArtifactUpdate,
    ExportArtifactRequest,
    ExportArtifactResponse,
    GenerateArtifactRequest,
    GenerateArtifactResponse,
    ArtifactVersionDetail,
    ArtifactVersionListResponse,
)
from backend.services.artifact_service import (
    ArtifactService,
    ArtifactNotFoundError,
    VersionNotFoundError,
)
from backend.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================
# Artifact CRUD
# ======================


@router.post(
    "/projects/{project_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Artifacts"],
    summary="Create a new artifact",
)
async def create_artifact(
    project_id: str,
    request: ArtifactCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Create a new artifact in the specified project branch.

    Requires Editor or Admin role in the workspace.
    """
    try:
        project_service = ProjectService(session)

        # Verify project exists and user has access
        project = await project_service.get_project_by_id(
            project_id, current_user.get("user_id")
        )

        # Verify branch belongs to project
        if str(request.branch_id) != str(project.main_branch_id):
            branch = await project_service.get_branch(
                str(request.branch_id)
            )
            if branch.project_id != project.id:
                raise HTTPException(
                    status_code=400,
                    detail="Branch does not belong to this project",
                )

        # Check permission (Editor or Admin)
        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["editor", "admin"],
            )

        artifact_service = ArtifactService(session)
        artifact = await artifact_service.create_artifact(
            branch_id=str(request.branch_id),
            name=request.name,
            artifact_type=request.artifact_type,
            format=request.format,
            content=request.content,
            based_on_decisions=[str(d) for d in request.based_on_decisions] if request.based_on_decisions else None,
            metadata=request.metadata,
            created_by=current_user.get("user_id"),
        )

        return artifact_service.to_response(artifact)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create artifact"
        )


@router.get(
    "/projects/{project_id}/artifacts",
    response_model=ArtifactListResponse,
    tags=["Artifacts"],
    summary="List project artifacts",
)
async def list_project_artifacts(
    project_id: str,
    branch_id: Optional[str] = Query(None, description="Filter by branch"),
    artifact_type: Optional[str] = Query(None, description="Filter by type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search artifacts"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all artifacts in a project with optional filters.
    """
    try:
        project_service = ProjectService(session)

        # Verify project exists and user has access
        project = await project_service.get_project_by_id(
            project_id, current_user.get("user_id")
        )

        # Check permission ( Viewer, Editor, Admin can all view)
        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["viewer", "editor", "admin"],
            )

        artifact_service = ArtifactService(session)
        artifacts, total = await artifact_service.list_artifacts(
            user_id=current_user.get("user_id"),
            branch_id=branch_id,
            artifact_type=artifact_type,
            status=status,
            search=search,
            page=page,
            page_size=page_size,
        )

        return ArtifactListResponse(
            artifacts=[artifact_service.to_response(a) for a in artifacts],
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing artifacts: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to list artifacts"
        )


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ArtifactDetail,
    tags=["Artifacts"],
    summary="Get artifact details",
)
async def get_artifact(
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get detailed artifact information including content and versions.
    """
    try:
        artifact_service = ArtifactService(session)
        artifact = await artifact_service.get_artifact_by_id(artifact_id)

        # Verify user has access to the project/branch
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            str(artifact.branch_id.split("/")[0])  # Extract project_id from branch
            if "/" in str(artifact.branch_id) else str(artifact.branch_id),
            current_user.get("user_id"),
        )

        return artifact_service.to_detail(artifact)

    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=404, detail="Artifact not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get artifact"
        )


@router.patch(
    "/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
    tags=["Artifacts"],
    summary="Update artifact",
)
async def update_artifact(
    artifact_id: str,
    request: ArtifactUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Update artifact properties. Requires Editor or Admin role.
    """
    try:
        artifact_service = ArtifactService(session)

        # Get artifact and verify access
        artifact = await artifact_service.get_artifact_by_id(artifact_id)

        # Verify user has edit permission
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            str(artifact.branch_id.split("/")[0])
            if "/" in str(artifact.branch_id) else str(artifact.branch_id),
            current_user.get("user_id"),
        )

        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["editor", "admin"],
            )

        updated = await artifact_service.update_artifact(
            artifact_id=artifact_id,
            user_id=current_user.get("user_id"),
            name=request.name,
            content=request.content,
            status=request.status,
            metadata=request.metadata,
        )

        return artifact_service.to_response(updated)

    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=404, detail="Artifact not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to update artifact"
        )


@router.delete(
    "/artifacts/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Artifacts"],
    summary="Delete artifact",
)
async def delete_artifact(
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete an artifact. Requires Admin role.
    """
    try:
        artifact_service = ArtifactService(session)

        # Get artifact and verify access
        artifact = await artifact_service.get_artifact_by_id(artifact_id)

        # Verify user has admin permission
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            str(artifact.branch_id.split("/")[0])
            if "/" in str(artifact.branch_id) else str(artifact.branch_id),
            current_user.get("user_id"),
        )

        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["admin"],
            )

        await artifact_service.delete_artifact(
            artifact_id=artifact_id,
            user_id=current_user.get("user_id"),
        )

    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=404, detail="Artifact not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete artifact"
        )


# ======================
# Version Management
# ======================


@router.get(
    "/artifacts/{artifact_id}/versions",
    response_model=ArtifactVersionListResponse,
    tags=["Artifacts"],
    summary="List artifact versions",
)
async def list_artifact_versions(
    artifact_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all versions of an artifact.
    """
    try:
        artifact_service = ArtifactService(session)

        # Verify artifact exists
        await artifact_service.get_artifact_by_id(artifact_id)

        versions, total = await artifact_service.list_versions(
            artifact_id=artifact_id,
            page=page,
            page_size=page_size,
        )

        return ArtifactVersionListResponse(
            versions=[artifact_service.to_version_response(v) for v in versions],
            total=total,
            page=page,
            page_size=page_size,
        )

    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=404, detail="Artifact not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing versions: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to list versions"
        )


@router.get(
    "/artifacts/{artifact_id}/versions/{version_number}",
    response_model=ArtifactVersionDetail,
    tags=["Artifacts"],
    summary="Get specific artifact version",
)
async def get_artifact_version(
    artifact_id: str,
    version_number: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get a specific version of an artifact.
    """
    try:
        artifact_service = ArtifactService(session)

        version = await artifact_service.get_version(
            artifact_id=artifact_id,
            version_number=version_number,
        )

        return artifact_service.to_version_detail(version)

    except VersionNotFoundError:
        raise HTTPException(
            status_code=404, detail="Version not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting version: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get version"
        )


@router.post(
    "/artifacts/{artifact_id}/rollback/{version_number}",
    response_model=ArtifactResponse,
    tags=["Artifacts"],
    summary="Rollback to specific version",
)
async def rollback_artifact(
    artifact_id: str,
    version_number: int,
    version_message: Optional[str] = Query(
        None, description="Message for the rollback version"
    ),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Rollback artifact to a specific version. Requires Editor or Admin role.
    """
    try:
        artifact_service = ArtifactService(session)

        # Get artifact and verify access
        artifact = await artifact_service.get_artifact_by_id(artifact_id)

        # Verify user has edit permission
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            str(artifact.branch_id.split("/")[0])
            if "/" in str(artifact.branch_id) else str(artifact.branch_id),
            current_user.get("user_id"),
        )

        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["editor", "admin"],
            )

        updated = await artifact_service.rollback_to_version(
            artifact_id=artifact_id,
            version_number=version_number,
            user_id=current_user.get("user_id"),
            version_message=version_message,
        )

        return artifact_service.to_response(updated)

    except VersionNotFoundError:
        raise HTTPException(
            status_code=404, detail="Version not found"
        )
    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=404, detail="Artifact not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rolling back artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to rollback artifact"
        )


# ======================
# Generation & Export
# ======================


@router.post(
    "/projects/{project_id}/artifacts/generate",
    response_model=GenerateArtifactResponse,
    tags=["Artifacts"],
    summary="Generate artifact using AI",
)
async def generate_artifact(
    project_id: str,
    request: GenerateArtifactRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Trigger AI-powered artifact generation.
    This is a placeholder for LangGraph agent integration.
    """
    try:
        project_service = ProjectService(session)

        # Verify project exists and user has access
        project = await project_service.get_project_by_id(
            project_id, current_user.get("user_id")
        )

        # Check permission (Editor or Admin)
        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["editor", "admin"],
            )

        # TODO: Integrate with LangGraph Specification Agent
        # This is a placeholder that returns mock data
        return GenerateArtifactResponse(
            name=f"Generated {request.artifact_type}",
            artifact_type=request.artifact_type,
            format=request.format,
            content="# Generated Content\n\nThis is a placeholder for AI-generated content.",
            metadata={"generated_at": "2024-01-01T00:00:00Z"},
            confidence_score=0.85,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate artifact"
        )


@router.post(
    "/artifacts/{artifact_id}/regenerate",
    response_model=ArtifactResponse,
    tags=["Artifacts"],
    summary="Regenerate artifact",
)
async def regenerate_artifact(
    artifact_id: str,
    content: str,
    version_message: Optional[str] = Query(
        None, description="Message for the new version"
    ),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Regenerate artifact with new content. Requires Editor or Admin role.
    """
    try:
        artifact_service = ArtifactService(session)

        # Get artifact and verify access
        artifact = await artifact_service.get_artifact_by_id(artifact_id)

        # Verify user has edit permission
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            str(artifact.branch_id.split("/")[0])
            if "/" in str(artifact.branch_id) else str(artifact.branch_id),
            current_user.get("user_id"),
        )

        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["editor", "admin"],
            )

        updated = await artifact_service.regenerate_artifact(
            artifact_id=artifact_id,
            user_id=current_user.get("user_id"),
            content=content,
            version_message=version_message,
        )

        return artifact_service.to_response(updated)

    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=404, detail="Artifact not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to regenerate artifact"
        )


@router.post(
    "/artifacts/{artifact_id}/export",
    response_model=ExportArtifactResponse,
    tags=["Artifacts"],
    summary="Export artifact",
)
async def export_artifact(
    artifact_id: str,
    request: ExportArtifactRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Export artifact in the specified format.
    """
    try:
        artifact_service = ArtifactService(session)

        export_data = await artifact_service.export_artifact(
            artifact_id=artifact_id,
            format=request.format,
            include_metadata=request.include_metadata,
        )

        return ExportArtifactResponse(**export_data)

    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=404, detail="Artifact not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting artifact: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to export artifact"
        )
