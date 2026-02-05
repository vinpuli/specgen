"""
Codebase Analysis API endpoints.

This module provides:
- Codebase analysis triggering and status endpoints
- Impact analysis endpoints
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.api.schemas.codebase import (
    CodebaseAnalysisCreate,
    CodebaseAnalysisResponse,
    CodebaseAnalysisResultResponse,
    ImpactAnalysisCreate,
    ImpactAnalysisResponse,
)
from backend.services.codebase_analysis_service import (
    CodebaseAnalysisService,
    CodebaseAnalysisNotFoundError,
)
from backend.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================
# Codebase Analysis
# ======================


@router.post(
    "/codebase/analyze",
    response_model=CodebaseAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Codebase Analysis"],
    summary="Trigger codebase analysis",
)
async def trigger_codebase_analysis(
    request: CodebaseAnalysisCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Trigger a new codebase analysis for a brownfield project.

    Requires Editor or Admin role in the workspace.
    """
    try:
        # Verify project exists and user has access
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            str(request.project_id),
            current_user.get("user_id")
        )

        # Check permission
        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["editor", "admin"],
            )

        # Create analysis record
        analysis_service = CodebaseAnalysisService(session)
        analysis = await analysis_service.create_analysis(
            project_id=str(request.project_id),
            repository_url=str(request.repository_url) if request.repository_url else None,
            branch_name=request.branch_name,
        )

        # TODO: Trigger actual analysis (e.g., via Celery task or LangGraph agent)
        # For now, return the created analysis with pending status

        return CodebaseAnalysisResponse(
            id=str(analysis.id),
            project_id=str(analysis.project_id),
            status=analysis.status.value,
            repository_url=analysis.repository_url,
            branch_name=analysis.branch_name,
            message="Analysis queued successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering analysis: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to trigger analysis"
        )


@router.get(
    "/codebase/analyses/{analysis_id}",
    response_model=CodebaseAnalysisResultResponse,
    tags=["Codebase Analysis"],
    summary="Get analysis results",
)
async def get_analysis_results(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get the results of a codebase analysis.
    """
    try:
        analysis_service = CodebaseAnalysisService(session)
        analysis = await analysis_service.get_analysis_by_id(analysis_id)

        # Verify user has access to the project
        project_service = ProjectService(session)
        await project_service.get_project_by_id(
            str(analysis.project_id),
            current_user.get("user_id")
        )

        return CodebaseAnalysisResultResponse(
            id=str(analysis.id),
            project_id=str(analysis.project_id),
            status=analysis.status.value,
            repository_url=analysis.repository_url,
            languages=analysis.languages or [],
            language_stats=analysis.language_stats or {},
            total_loc=analysis.total_loc,
            file_count=analysis.file_count,
            architecture_summary=analysis.architecture_summary,
            component_inventory=analysis.component_inventory or [],
            dependency_graph=analysis.dependency_graph or {},
            detected_patterns=analysis.detected_patterns or [],
            findings=analysis.findings or [],
            created_at=analysis.created_at.isoformat() if analysis.created_at else None,
            completed_at=analysis.completed_at.isoformat() if analysis.completed_at else None,
            error_message=analysis.error_message,
        )

    except CodebaseAnalysisNotFoundError:
        raise HTTPException(
            status_code=404, detail="Analysis not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get analysis"
        )


@router.get(
    "/projects/{project_id}/codebase/analyses",
    response_model=list[CodebaseAnalysisResponse],
    tags=["Codebase Analysis"],
    summary="List project analyses",
)
async def list_project_analyses(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all codebase analyses for a project.
    """
    try:
        # Verify user has access
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            project_id,
            current_user.get("user_id")
        )

        # Check permission
        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["viewer", "editor", "admin"],
            )

        # Get latest analysis
        analysis_service = CodebaseAnalysisService(session)
        latest_analysis = await analysis_service.get_latest_analysis(project_id)

        if not latest_analysis:
            return []

        return [CodebaseAnalysisResponse(
            id=str(latest_analysis.id),
            project_id=str(latest_analysis.project_id),
            status=latest_analysis.status.value,
            repository_url=latest_analysis.repository_url,
            branch_name=latest_analysis.branch_name,
            created_at=latest_analysis.created_at.isoformat() if latest_analysis.created_at else None,
        )]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing analyses: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to list analyses"
        )


# ======================
# Impact Analysis
# ======================


@router.post(
    "/projects/{project_id}/impact-analysis",
    response_model=ImpactAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Impact Analysis"],
    summary="Trigger impact analysis",
)
async def trigger_impact_analysis(
    project_id: str,
    request: ImpactAnalysisCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Trigger an impact analysis for a proposed change.

    Requires Editor or Admin role.
    """
    try:
        # Verify project exists and user has access
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            project_id,
            current_user.get("user_id")
        )

        # Check permission
        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["editor", "admin"],
            )

        # Get latest codebase analysis
        analysis_service = CodebaseAnalysisService(session)
        latest_analysis = await analysis_service.get_latest_analysis(project_id)

        if not latest_analysis:
            raise HTTPException(
                status_code=400,
                detail="No codebase analysis found. Please run analysis first."
            )

        # Create impact analysis record
        impact = await analysis_service.create_impact_analysis(
            codebase_analysis_id=str(latest_analysis.id),
            project_id=project_id,
            change_description=request.change_description,
        )

        # TODO: Trigger actual impact analysis

        return ImpactAnalysisResponse(
            id=str(impact.id),
            codebase_analysis_id=str(impact.codebase_analysis_id),
            project_id=str(impact.project_id),
            change_description=impact.change_description,
            status="pending",
            message="Impact analysis queued successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering impact analysis: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to trigger impact analysis"
        )


@router.get(
    "/impact-analyses/{impact_id}",
    response_model=ImpactAnalysisResponse,
    tags=["Impact Analysis"],
    summary="Get impact analysis results",
)
async def get_impact_analysis(
    impact_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get the results of an impact analysis.
    """
    try:
        analysis_service = CodebaseAnalysisService(session)
        impact = await analysis_service.get_impact_analysis(impact_id)

        # Verify user has access to the project
        project_service = ProjectService(session)
        await project_service.get_project_by_id(
            str(impact.project_id),
            current_user.get("user_id")
        )

        return ImpactAnalysisResponse(
            id=str(impact.id),
            codebase_analysis_id=str(impact.codebase_analysis_id),
            project_id=str(impact.project_id),
            change_description=impact.change_description,
            affected_files=impact.affected_files or [],
            affected_components=impact.affected_components or [],
            risk_level=impact.risk_level.value if impact.risk_level else None,
            risk_factors=impact.risk_factors or [],
            breaking_changes=impact.breaking_changes or [],
            downstream_dependencies=impact.downstream_dependencies or [],
            rollback_procedure=impact.rollback_procedure,
            change_plan=impact.change_plan or [],
            created_at=impact.created_at.isoformat() if impact.created_at else None,
        )

    except CodebaseAnalysisNotFoundError:
        raise HTTPException(
            status_code=404, detail="Impact analysis not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting impact analysis: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get impact analysis"
        )


@router.get(
    "/projects/{project_id}/impact-analyses",
    response_model=list[ImpactAnalysisResponse],
    tags=["Impact Analysis"],
    summary="List project impact analyses",
)
async def list_impact_analyses(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all impact analyses for a project.
    """
    try:
        # Verify user has access
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            project_id,
            current_user.get("user_id")
        )

        # Check permission
        if project.workspace_id:
            from backend.services.workspace_service import WorkspaceService
            ws_service = WorkspaceService(session)
            await ws_service.check_permission(
                project.workspace_id,
                current_user.get("user_id"),
                ["viewer", "editor", "admin"],
            )

        # Get latest codebase analysis and its impacts
        analysis_service = CodebaseAnalysisService(session)
        latest_analysis = await analysis_service.get_latest_analysis(project_id)

        if not latest_analysis:
            return []

        # This is simplified - in production, you'd want pagination
        return []

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing impact analyses: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to list impact analyses"
        )
