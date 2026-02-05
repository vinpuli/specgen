"""
Comment API endpoints.

This module provides:
- Comment CRUD endpoints
- Threaded comment support
- Comment resolution
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.api.schemas.comment import (
    CommentCreate,
    CommentDetail,
    CommentListResponse,
    CommentResponse,
    CommentResolve,
)
from backend.services.comment_service import (
    CommentService,
    CommentNotFoundError,
)
from backend.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================
# Comment CRUD
# ======================


@router.post(
    "/artifacts/{artifact_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Comments"],
    summary="Add a comment to an artifact",
)
async def create_artifact_comment(
    artifact_id: str,
    request: CommentCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Add a comment to an artifact.

    Requires Viewer, Editor, or Admin role in the workspace.
    """
    try:
        # Verify artifact exists and user has access
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            request.resource_id if hasattr(request, 'resource_id') else artifact_id,
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

        comment_service = CommentService(session)
        comment = await comment_service.create_comment(
            project_id=str(project.id),
            content=request.content,
            author_id=current_user.get("user_id"),
            artifact_id=str(artifact_id),
            parent_comment_id=str(request.parent_comment_id) if request.parent_comment_id else None,
            metadata=request.metadata,
        )

        return comment_service.to_response(comment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating comment: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create comment"
        )


@router.get(
    "/artifacts/{artifact_id}/comments",
    response_model=CommentListResponse,
    tags=["Comments"],
    summary="List artifact comments",
)
async def list_artifact_comments(
    artifact_id: str,
    include_resolved: bool = Query(False, description="Include resolved comments"),
    search: Optional[str] = Query(None, description="Search in comment content"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all comments on an artifact.
    """
    try:
        # Verify user has access
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            artifact_id,
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

        comment_service = CommentService(session)
        comments, total = await comment_service.list_comments(
            artifact_id=artifact_id,
            is_resolved=None if include_resolved else False,
            search=search,
            page=page,
            page_size=page_size,
        )

        return CommentListResponse(
            comments=[comment_service.to_response(c) for c in comments],
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing comments: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to list comments"
        )


@router.get(
    "/comments/{comment_id}",
    response_model=CommentDetail,
    tags=["Comments"],
    summary="Get comment details",
)
async def get_comment(
    comment_id: str,
    include_replies: bool = Query(False, description="Include replies"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get detailed comment information including replies.
    """
    try:
        comment_service = CommentService(session)
        comment = await comment_service.get_comment_by_id(comment_id)

        # Verify user has access to the project
        project_service = ProjectService(session)
        await project_service.get_project_by_id(
            str(comment.project_id),
            current_user.get("user_id")
        )

        return comment_service.to_detail(comment, include_replies=include_replies)

    except CommentNotFoundError:
        raise HTTPException(
            status_code=404, detail="Comment not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting comment: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get comment"
        )


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    tags=["Comments"],
    summary="Update a comment",
)
async def update_comment(
    comment_id: str,
    request: CommentCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Update comment content. Only the author can edit.
    """
    try:
        comment_service = CommentService(session)
        comment = await comment_service.update_comment(
            comment_id=comment_id,
            user_id=current_user.get("user_id"),
            content=request.content,
        )

        return comment_service.to_response(comment)

    except CommentNotFoundError:
        raise HTTPException(
            status_code=404, detail="Comment not found"
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=403, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating comment: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to update comment"
        )


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Comments"],
    summary="Delete a comment",
)
async def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete (archive) a comment. Only the author can delete.
    """
    try:
        comment_service = CommentService(session)
        await comment_service.archive_comment(
            comment_id=comment_id,
            user_id=current_user.get("user_id"),
        )

    except CommentNotFoundError:
        raise HTTPException(
            status_code=404, detail="Comment not found"
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=403, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting comment: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete comment"
        )


# ======================
# Comment Resolution
# ======================


@router.post(
    "/comments/{comment_id}/resolve",
    response_model=CommentResponse,
    tags=["Comments"],
    summary="Resolve a comment",
)
async def resolve_comment(
    comment_id: str,
    request: CommentResolve,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Mark a comment as resolved or unresolved.

    Requires Editor or Admin role.
    """
    try:
        comment_service = CommentService(session)
        comment = await comment_service.get_comment_by_id(comment_id)

        # Verify user has access to the project
        project_service = ProjectService(session)
        project = await project_service.get_project_by_id(
            str(comment.project_id),
            current_user.get("user_id")
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

        resolved_comment = await comment_service.resolve_comment(
            comment_id=comment_id,
            user_id=current_user.get("user_id"),
            resolved=request.resolved,
        )

        return comment_service.to_response(resolved_comment)

    except CommentNotFoundError:
        raise HTTPException(
            status_code=404, detail="Comment not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving comment: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to resolve comment"
        )


# ======================
# Thread Support
# ======================


@router.get(
    "/comments/{comment_id}/replies",
    response_model=list[CommentResponse],
    tags=["Comments"],
    summary="Get comment replies",
)
async def get_comment_replies(
    comment_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get all replies to a comment.
    """
    try:
        comment_service = CommentService(session)
        comment = await comment_service.get_comment_by_id(comment_id)

        # Verify user has access to the project
        project_service = ProjectService(session)
        await project_service.get_project_by_id(
            str(comment.project_id),
            current_user.get("user_id")
        )

        replies = await comment_service.get_replies(comment_id)

        return [comment_service.to_response(r) for r in replies]

    except CommentNotFoundError:
        raise HTTPException(
            status_code=404, detail="Comment not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting replies: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get replies"
        )
