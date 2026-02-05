"""
Comment service for comment and conversation management.

This module provides:
- Comment CRUD operations
- Threaded comment support
- Comment resolution
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.comment import Comment, CommentStatus
from backend.db.models.project import Project

logger = logging.getLogger(__name__)


class CommentServiceError(Exception):
    """Base exception for comment service errors."""
    pass


class CommentNotFoundError(CommentServiceError):
    """Raised when comment is not found."""
    pass


class CommentService:
    """
    Comment service for managing threaded comments.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize comment service.

        Args:
            session: Async database session.
        """
        self.session = session

    # ======================
    # Comment CRUD
    # ======================

    async def create_comment(
        self,
        project_id: str,
        content: str,
        author_id: str,
        artifact_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        parent_comment_id: Optional[str] = None,
        comment_type: str = "suggestion",
        metadata: Optional[dict] = None,
    ) -> Comment:
        """
        Create a new comment.

        Args:
            project_id: Project ID.
            content: Comment content.
            author_id: Author user ID.
            artifact_id: Optional artifact ID.
            decision_id: Optional decision ID.
            parent_comment_id: Optional parent comment ID for threads.
            comment_type: Type of comment.
            metadata: Optional metadata.

        Returns:
            Created Comment.
        """
        from backend.db.models.comment import CommentType

        # Verify parent comment exists if provided
        if parent_comment_id:
            parent = await self.get_comment_by_id(parent_comment_id)
            if str(parent.project_id) != project_id:
                raise ValueError("Parent comment must be from the same project")

        comment = Comment(
            project_id=project_id,
            artifact_id=artifact_id,
            decision_id=decision_id,
            parent_comment_id=parent_comment_id,
            author_id=author_id,
            comment_type=CommentType(comment_type),
            content=content,
            status=CommentStatus.OPEN,
            metadata=metadata or {},
        )

        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)

        logger.info(f"Comment created: {comment.id}")
        return comment

    async def get_comment_by_id(
        self,
        comment_id: str,
    ) -> Comment:
        """
        Get comment by ID.

        Args:
            comment_id: Comment ID.

        Returns:
            Comment.

        Raises:
            CommentNotFoundError: If comment not found.
        """
        result = await self.session.execute(
            select(Comment)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.replies),
            )
            .where(Comment.id == comment_id)
            .where(Comment.status != CommentStatus.ARCHIVED)
        )
        comment = result.scalar_one_or_none()

        if not comment:
            raise CommentNotFoundError(f"Comment not found: {comment_id}")

        return comment

    async def list_comments(
        self,
        project_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        author_id: Optional[str] = None,
        parent_comment_id: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Comment], int]:
        """
        List comments with optional filters.

        Args:
            project_id: Optional project ID filter.
            artifact_id: Optional artifact ID filter.
            decision_id: Optional decision ID filter.
            author_id: Optional author filter.
            parent_comment_id: Optional parent comment filter (None for root comments).
            is_resolved: Optional resolved status filter.
            search: Optional search query.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (comments, total_count).
        """
        query = (
            select(Comment)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.replies),
            )
            .where(Comment.status != CommentStatus.ARCHIVED)
        )

        if project_id:
            query = query.where(Comment.project_id == project_id)
        if artifact_id:
            query = query.where(Comment.artifact_id == artifact_id)
        if decision_id:
            query = query.where(Comment.decision_id == decision_id)
        if author_id:
            query = query.where(Comment.author_id == author_id)
        if parent_comment_id:
            query = query.where(Comment.parent_comment_id == parent_comment_id)
        else:
            query = query.where(Comment.parent_comment_id == None)  # noqa: E711
        if is_resolved is not None:
            status = CommentStatus.RESOLVED if is_resolved else CommentStatus.OPEN
            query = query.where(Comment.status == status)
        if search:
            query = query.where(
                or_(
                    Comment.content.ilike(f"%{search}%"),
                )
            )

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        comments = list(result.scalars().all())

        # Get total count
        count_query = select(func.count(Comment.id)).where(
            Comment.status != CommentStatus.ARCHIVED
        )
        if project_id:
            count_query = count_query.where(Comment.project_id == project_id)
        if artifact_id:
            count_query = count_query.where(Comment.artifact_id == artifact_id)
        if decision_id:
            count_query = count_query.where(Comment.decision_id == decision_id)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        return comments, total

    async def update_comment(
        self,
        comment_id: str,
        user_id: str,
        content: Optional[str] = None,
    ) -> Comment:
        """
        Update comment content.

        Args:
            comment_id: Comment ID.
            user_id: User making the update.
            content: Optional new content.

        Returns:
            Updated Comment.

        Raises:
            CommentNotFoundError: If comment not found.
            PermissionError: If user is not the author.
        """
        comment = await self.get_comment_by_id(comment_id)

        if str(comment.author_id) != user_id:
            raise PermissionError("Only the author can edit this comment")

        if content:
            comment.content = content

        await self.session.commit()
        await self.session.refresh(comment)

        logger.info(f"Comment updated: {comment_id}")
        return comment

    async def resolve_comment(
        self,
        comment_id: str,
        user_id: str,
        resolved: bool = True,
    ) -> Comment:
        """
        Resolve or unresolve a comment.

        Args:
            comment_id: Comment ID.
            user_id: User resolving the comment.
            resolved: Whether to mark as resolved.

        Returns:
            Updated Comment.

        Raises:
            CommentNotFoundError: If comment not found.
        """
        comment = await self.get_comment_by_id(comment_id)

        comment.status = CommentStatus.RESOLVED if resolved else CommentStatus.OPEN
        comment.resolved_at = datetime.now(timezone.utc) if resolved else None
        comment.resolved_by = user_id if resolved else None

        await self.session.commit()
        await self.session.refresh(comment)

        logger.info(f"Comment {comment_id} resolved: {resolved}")
        return comment

    async def archive_comment(
        self,
        comment_id: str,
        user_id: str,
    ) -> bool:
        """
        Archive (soft delete) a comment.

        Args:
            comment_id: Comment ID.
            user_id: User archiving the comment.

        Returns:
            True if successful.

        Raises:
            CommentNotFoundError: If comment not found.
        """
        comment = await self.get_comment_by_id(comment_id)

        # Only author or project admin can archive
        if str(comment.author_id) != user_id:
            # Check if user is project admin
            # For now, allow if author
            raise PermissionError("Only the author can archive this comment")

        comment.status = CommentStatus.ARCHIVED
        await self.session.commit()

        logger.info(f"Comment archived: {comment_id}")
        return True

    # ======================
    # Thread Support
    # ======================

    async def get_replies(
        self,
        parent_comment_id: str,
    ) -> List[Comment]:
        """
        Get replies to a comment.

        Args:
            parent_comment_id: Parent comment ID.

        Returns:
            List of reply comments.
        """
        result = await self.session.execute(
            select(Comment)
            .options(selectinload(Comment.author))
            .where(Comment.parent_comment_id == parent_comment_id)
            .where(Comment.status != CommentStatus.ARCHIVED)
            .order_by(Comment.created_at)
        )
        return list(result.scalars().all())

    async def get_thread(
        self,
        root_comment_id: str,
    ) -> dict:
        """
        Get a complete thread (root comment + all replies).

        Args:
            root_comment_id: Root comment ID.

        Returns:
            Dict with root comment and replies.
        """
        root = await self.get_comment_by_id(root_comment_id)
        replies = await self.get_replies(root_comment_id)

        return {
            "root": root,
            "replies": replies,
            "reply_count": len(replies),
        }

    # ======================
    # Response Helpers
    # ======================

    def to_response(self, comment: Comment) -> dict:
        """Convert Comment to response dict."""
        return {
            "id": str(comment.id),
            "project_id": str(comment.project_id),
            "artifact_id": str(comment.artifact_id) if comment.artifact_id else None,
            "decision_id": str(comment.decision_id) if comment.decision_id else None,
            "parent_comment_id": str(comment.parent_comment_id) if comment.parent_comment_id else None,
            "author_id": str(comment.author_id) if comment.author_id else None,
            "comment_type": comment.comment_type.value if comment.comment_type else None,
            "content": comment.content,
            "status": comment.status.value if comment.status else None,
            "is_resolved": comment.status == CommentStatus.RESOLVED,
            "resolve_requested": comment.resolve_requested,
            "re_question_triggered": comment.re_question_triggered,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
            "resolved_at": comment.resolved_at,
            "resolved_by": str(comment.resolved_by) if comment.resolved_by else None,
        }

    def to_detail(self, comment: Comment, include_replies: bool = False) -> dict:
        """Convert Comment to detail response."""
        response = self.to_response(comment)

        # Add author info if loaded
        if comment.author:
            response["author"] = {
                "id": str(comment.author.id),
                "email": comment.author.email,
                "name": getattr(comment.author, 'name', None) or getattr(comment.author, 'full_name', None),
            }

        # Add replies if requested and loaded
        if include_replies and comment.replies:
            response["replies"] = [self.to_response(r) for r in comment.replies]
            response["reply_count"] = len(comment.replies)

        return response
