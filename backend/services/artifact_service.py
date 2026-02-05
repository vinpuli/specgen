"""
Artifact service for artifact and version management.

This module provides:
- Artifact CRUD operations
- Version management
- Content storage
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.artifact import Artifact, ArtifactVersion, ArtifactStatus
from backend.db.models.project import Branch
from backend.services.project_service import ProjectService, BranchNotFoundError
from backend.storage.service import StorageService

logger = logging.getLogger(__name__)


class ArtifactServiceError(Exception):
    """Base exception for artifact service errors."""

    pass


class ArtifactNotFoundError(ArtifactServiceError):
    """Raised when artifact is not found."""

    pass


class VersionNotFoundError(ArtifactServiceError):
    """Raised when artifact version is not found."""

    pass


class ArtifactService:
    """
    Artifact service for managing specification artifacts.
    """

    def __init__(self, session: AsyncSession, storage_service: Optional[StorageService] = None):
        """
        Initialize artifact service.

        Args:
            session: Async database session.
            storage_service: Optional storage service for file operations.
        """
        self.session = session
        self.project_service = ProjectService(session)
        self.storage_service = storage_service

    # ======================
    # Artifact CRUD
    # ======================

    async def create_artifact(
        self,
        branch_id: str,
        name: str,
        artifact_type: str,
        format: str,
        content: str,
        based_on_decisions: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
        created_by: Optional[str] = None,
    ) -> Artifact:
        """
        Create a new artifact.

        Args:
            branch_id: Branch ID.
            name: Artifact name.
            artifact_type: Artifact type.
            format: Content format.
            content: Artifact content.
            based_on_decisions: Decision IDs this artifact is based on.
            metadata: Additional metadata.
            created_by: User ID.

        Returns:
            Created Artifact.
        """
        # Verify branch exists
        branch = await self._get_branch(branch_id)

        artifact = Artifact(
            branch_id=branch_id,
            name=name,
            artifact_type=artifact_type,
            format=format,
            content=content,
            status=ArtifactStatus.DRAFT,
            metadata=metadata or {},
            created_by=created_by,
            based_on_decisions=based_on_decisions or [],
        )

        self.session.add(artifact)
        await self.session.commit()
        await self.session.refresh(artifact)

        # Create initial version
        await self._create_version(artifact.id, content, "Initial version", created_by)

        logger.info(f"Artifact created: {artifact.id} in branch {branch_id}")
        return artifact

    async def get_artifact_by_id(
        self,
        artifact_id: str,
        user_id: Optional[str] = None,
    ) -> Artifact:
        """
        Get artifact by ID.

        Args:
            artifact_id: Artifact ID.
            user_id: Optional user ID for permission check.

        Returns:
            Artifact.

        Raises:
            ArtifactNotFoundError: If artifact not found.
        """
        result = await self.session.execute(
            select(Artifact)
            .options(
                selectinload(Artifact.branch),
                selectinload(Artifact.versions),
            )
            .where(Artifact.id == artifact_id)
            .where(Artifact.is_active == True)  # type: ignore
        )
        artifact = result.scalar_one_or_none()

        if not artifact:
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        return artifact

    async def list_artifacts(
        self,
        user_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        status: Optional[str] = None,
        created_by: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Artifact], int]:
        """
        List artifacts with optional filters.

        Args:
            user_id: Optional user ID filter.
            branch_id: Optional branch ID filter.
            artifact_type: Optional type filter.
            status: Optional status filter.
            created_by: Optional creator filter.
            search: Optional search query.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (artifacts, total_count).
        """
        query = (
            select(Artifact)
            .options(selectinload(Artifact.branch))
            .where(Artifact.is_active == True)  # type: ignore
        )

        if branch_id:
            query = query.where(Artifact.branch_id == branch_id)
        if artifact_type:
            query = query.where(Artifact.artifact_type == artifact_type)
        if status:
            query = query.where(Artifact.status == status)
        if created_by:
            query = query.where(Artifact.created_by == created_by)
        if search:
            query = query.where(
                or_(
                    Artifact.name.ilike(f"%{search}%"),
                    Artifact.content.ilike(f"%{search}%"),
                )
            )

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        artifacts = list(result.scalars().all())

        # Get total count
        count_query = select(Artifact).where(Artifact.is_active == True)  # type: ignore
        if branch_id:
            count_query = count_query.where(Artifact.branch_id == branch_id)
        if artifact_type:
            count_query = count_query.where(Artifact.artifact_type == artifact_type)
        if status:
            count_query = count_query.where(Artifact.status == status)
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        return artifacts, total

    async def update_artifact(
        self,
        artifact_id: str,
        user_id: str,
        name: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[dict] = None,
        version_message: Optional[str] = None,
    ) -> Artifact:
        """
        Update artifact details.

        Args:
            artifact_id: Artifact ID.
            user_id: User making the update.
            name: Optional new name.
            content: Optional new content.
            status: Optional new status.
            metadata: Optional new metadata.
            version_message: Message for new version.

        Returns:
            Updated Artifact.

        Raises:
            ArtifactNotFoundError: If artifact not found.
        """
        artifact = await self.get_artifact_by_id(artifact_id)

        if name:
            artifact.name = name
        if status:
            artifact.status = ArtifactStatus(status)
        if metadata is not None:
            artifact.metadata = metadata

        # Create new version if content changed
        if content and content != artifact.content:
            artifact.content = content
            artifact.current_version += 1
            await self._create_version(artifact.id, content, version_message, user_id)

        await self.session.commit()
        await self.session.refresh(artifact)

        logger.info(f"Artifact updated: {artifact_id}")
        return artifact

    async def delete_artifact(
        self,
        artifact_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete (deactivate) an artifact.

        Args:
            artifact_id: Artifact ID.
            user_id: User making the request.

        Returns:
            True if successful.
        """
        artifact = await self.get_artifact_by_id(artifact_id)

        artifact.is_active = False  # type: ignore
        await self.session.commit()

        logger.info(f"Artifact deleted: {artifact_id}")
        return True

    # ======================
    # Version Management
    # ======================

    async def list_versions(
        self,
        artifact_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[ArtifactVersion], int]:
        """
        List all versions of an artifact.

        Args:
            artifact_id: Artifact ID.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (versions, total_count).
        """
        # Verify artifact exists
        await self.get_artifact_by_id(artifact_id)

        query = (
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(query)
        versions = list(result.scalars().all())

        # Get total count
        count_query = select(func.count(ArtifactVersion.id)).where(
            ArtifactVersion.artifact_id == artifact_id
        )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        return versions, total

    async def get_version(
        self,
        artifact_id: str,
        version_number: int,
    ) -> ArtifactVersion:
        """
        Get specific version of an artifact.

        Args:
            artifact_id: Artifact ID.
            version_number: Version number.

        Returns:
            ArtifactVersion.

        Raises:
            VersionNotFoundError: If version not found.
        """
        await self.get_artifact_by_id(artifact_id)

        result = await self.session.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .where(ArtifactVersion.version == version_number)
        )
        version = result.scalar_one_or_none()

        if not version:
            raise VersionNotFoundError(
                f"Version {version_number} not found for artifact {artifact_id}"
            )

        return version

    async def rollback_to_version(
        self,
        artifact_id: str,
        version_number: int,
        user_id: str,
        version_message: Optional[str] = None,
    ) -> Artifact:
        """
        Rollback artifact to a specific version.

        Args:
            artifact_id: Artifact ID.
            version_number: Version number to rollback to.
            user_id: User performing rollback.
            version_message: Message for rollback version.

        Returns:
            Updated Artifact.

        Raises:
            VersionNotFoundError: If version not found.
        """
        version = await self.get_version(artifact_id, version_number)

        # Update artifact with rolled back content
        return await self.update_artifact(
            artifact_id=artifact_id,
            user_id=user_id,
            content=version.content,
            version_message=version_message or f"Rollback to version {version_number}",
        )

    async def regenerate_artifact(
        self,
        artifact_id: str,
        user_id: str,
        content: str,
        version_message: Optional[str] = None,
    ) -> Artifact:
        """
        Regenerate artifact with new content.

        Args:
            artifact_id: Artifact ID.
            user_id: User performing regeneration.
            content: New content.
            version_message: Message for regeneration.

        Returns:
            Updated Artifact.

        Raises:
            ArtifactNotFoundError: If artifact not found.
        """
        return await self.update_artifact(
            artifact_id=artifact_id,
            user_id=user_id,
            content=content,
            version_message=version_message or "Regenerated artifact",
        )

    # ======================
    # Export
    # ======================

    async def export_artifact(
        self,
        artifact_id: str,
        format: str = "markdown",
        include_metadata: bool = False,
    ) -> dict:
        """
        Export artifact in specified format.

        Args:
            artifact_id: Artifact ID.
            format: Export format.
            include_metadata: Include metadata in export.

        Returns:
            Export data dict.
        """
        artifact = await self.get_artifact_by_id(artifact_id)

        content = artifact.content
        filename = f"{artifact.name}.{format}"

        response = {
            "content": content,
            "format": format,
            "filename": filename,
            "content_type": self._get_content_type(format),
        }

        if include_metadata:
            response["metadata"] = {
                "name": artifact.name,
                "artifact_type": artifact.artifact_type,
                "version": artifact.current_version,
                "created_at": artifact.created_at.isoformat(),
                "status": artifact.status.value,
            }

        return response

    def _get_content_type(self, format: str) -> str:
        """Get content type for format."""
        content_types = {
            "markdown": "text/markdown",
            "json": "application/json",
            "yaml": "application/yaml",
            "html": "text/html",
            "text": "text/plain",
        }
        return content_types.get(format, "text/plain")

    # ======================
    # Helpers
    # ======================

    async def _get_branch(self, branch_id: str) -> Branch:
        """Get branch by ID."""
        result = await self.session.execute(
            select(Branch)
            .options(selectinload(Branch.project))
            .where(Branch.id == branch_id)
            .where(Branch.is_active == True)  # type: ignore
        )
        branch = result.scalar_one_or_none()

        if not branch:
            raise BranchNotFoundError(f"Branch not found: {branch_id}")

        return branch

    async def _create_version(
        self,
        artifact_id: str,
        content: str,
        version_message: Optional[str],
        created_by: Optional[str],
    ) -> ArtifactVersion:
        """Create a new artifact version."""
        # Get current version count
        result = await self.session.execute(
            select(func.count(ArtifactVersion.id)).where(
                ArtifactVersion.artifact_id == artifact_id
            )
        )
        version_number = (result.scalar() or 0) + 1

        version = ArtifactVersion(
            artifact_id=artifact_id,
            version=version_number,
            content=content,
            version_message=version_message,
            created_by=created_by,
        )

        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)

        return version

    # ======================
    # Response Helpers
    # ======================

    def to_response(self, artifact: Artifact) -> dict:
        """Convert Artifact to response dict."""
        return {
            "id": str(artifact.id),
            "branch_id": str(artifact.branch_id),
            "name": artifact.name,
            "artifact_type": artifact.artifact_type,
            "format": artifact.format,
            "status": artifact.status.value if hasattr(artifact.status, 'value') else str(artifact.status),
            "metadata": artifact.metadata or {},
            "created_by": artifact.created_by,
            "current_version": artifact.current_version,
            "based_on_decisions": artifact.based_on_decisions or [],
            "created_at": artifact.created_at,
            "updated_at": artifact.updated_at,
        }

    def to_detail(self, artifact: Artifact) -> dict:
        """Convert Artifact to detail response."""
        response = self.to_response(artifact)
        response["content"] = artifact.content

        # Add versions info
        if artifact.versions:
            response["versions"] = [
                {
                    "id": str(v.id),
                    "version": v.version,
                    "version_message": v.version_message,
                    "created_at": v.created_at,
                }
                for v in sorted(artifact.versions, key=lambda x: x.version, reverse=True)
            ]

        return response

    def to_version_response(self, version: ArtifactVersion) -> dict:
        """Convert ArtifactVersion to response dict."""
        return {
            "id": str(version.id),
            "artifact_id": str(version.artifact_id),
            "version": version.version,
            "content": version.content,
            "version_message": version.version_message,
            "created_by": version.created_by,
            "created_at": version.created_at,
        }

    def to_version_detail(self, version: ArtifactVersion, diff: Optional[str] = None) -> dict:
        """Convert ArtifactVersion to detail response."""
        response = self.to_version_response(version)
        if diff:
            response["diff_from_previous"] = diff
        return response
