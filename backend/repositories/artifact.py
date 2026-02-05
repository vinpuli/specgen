"""
Artifact repository for artifact data access operations.

This module implements the repository pattern for Artifact and ArtifactVersion models,
providing data access methods for generated specification management.
"""

import uuid
from typing import Optional, List
from datetime import datetime
import hashlib
import json

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.artifact import (
    Artifact,
    ArtifactVersion,
    ArtifactType,
    ArtifactFormat,
    ArtifactStatus,
)
from backend.repositories.base import BaseRepository


class ArtifactRepository(BaseRepository[Artifact]):
    """
    Repository for Artifact data access operations.

    Provides methods for:
    - Artifact CRUD operations
    - Artifact version management
    - Status tracking for generation jobs
    - Export and regeneration
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the ArtifactRepository.

        Args:
            session: The async database session.
        """
        super().__init__(Artifact, session)

    async def get_by_project(
        self,
        project_id: uuid.UUID,
        artifact_type: Optional[ArtifactType] = None,
        status: Optional[ArtifactStatus] = None,
        branch_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Artifact]:
        """
        Get all artifacts in a project with optional filters.

        Args:
            project_id: The project ID.
            artifact_type: Optional type filter.
            status: Optional status filter.
            branch_id: Optional branch filter.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of artifacts.
        """
        query = select(Artifact).where(Artifact.project_id == project_id)

        if artifact_type:
            query = query.where(Artifact.artifact_type == artifact_type)
        if status:
            query = query.where(Artifact.status == status)
        if branch_id:
            query = query.where(Artifact.branch_id == branch_id)

        query = (
            query.offset(skip)
            .limit(limit)
            .order_by(Artifact.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_artifact(
        self,
        project_id: uuid.UUID,
        artifact_type: ArtifactType,
        branch_id: Optional[uuid.UUID] = None,
    ) -> Optional[Artifact]:
        """
        Get the latest artifact of a specific type.

        Args:
            project_id: The project ID.
            artifact_type: The artifact type.
            branch_id: Optional branch filter.

        Returns:
            The latest artifact if found.
        """
        query = (
            select(Artifact)
            .where(
                and_(
                    Artifact.project_id == project_id,
                    Artifact.artifact_type == artifact_type,
                    Artifact.is_latest == True,
                )
            )
            .options(selectinload(Artifact.versions))
        )

        if branch_id:
            query = query.where(Artifact.branch_id == branch_id)

        query = query.order_by(Artifact.created_at.desc()).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_artifact_with_details(
        self, artifact_id: uuid.UUID
    ) -> Optional[Artifact]:
        """
        Get an artifact with all relationships loaded.

        Args:
            artifact_id: The artifact ID.

        Returns:
            The artifact with details.
        """
        query = (
            select(Artifact)
            .where(Artifact.id == artifact_id)
            .options(
                selectinload(Artifact.project),
                selectinload(Artifact.branch),
                selectinload(Artifact.versions),
                selectinload(Artifact.comments),
                selectinload(Artifact.related_decisions),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_artifact_versions(
        self, artifact_id: uuid.UUID
    ) -> List[ArtifactVersion]:
        """
        Get all versions of an artifact.

        Args:
            artifact_id: The artifact ID.

        Returns:
            List of versions ordered by version number.
        """
        query = (
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_type(
        self, project_id: uuid.UUID, artifact_type: ArtifactType
    ) -> List[Artifact]:
        """
        Get all artifacts of a specific type.

        Args:
            project_id: The project ID.
            artifact_type: The artifact type.

        Returns:
            List of artifacts.
        """
        query = (
            select(Artifact)
            .where(
                and_(
                    Artifact.project_id == project_id,
                    Artifact.artifact_type == artifact_type,
                )
            )
            .order_by(Artifact.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_completed_artifacts(
        self, project_id: uuid.UUID
    ) -> List[Artifact]:
        """
        Get all completed artifacts in a project.

        Args:
            project_id: The project ID.

        Returns:
            List of completed artifacts.
        """
        query = (
            select(Artifact)
            .where(
                and_(
                    Artifact.project_id == project_id,
                    Artifact.status == ArtifactStatus.COMPLETED,
                )
            )
            .order_by(Artifact.updated_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_generating_artifacts(
        self, project_id: uuid.UUID
    ) -> List[Artifact]:
        """
        Get all artifacts currently being generated.

        Args:
            project_id: The project ID.

        Returns:
            List of generating artifacts.
        """
        query = (
            select(Artifact)
            .where(
                and_(
                    Artifact.project_id == project_id,
                    Artifact.status.in_(
                        [
                            ArtifactStatus.GENERATING,
                            ArtifactStatus.REGENERATING,
                        ]
                    ),
                )
            )
            .order_by(Artifact.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self, artifact_id: uuid.UUID, status: ArtifactStatus
    ) -> Optional[Artifact]:
        """
        Update an artifact's status.

        Args:
            artifact_id: The artifact ID.
            status: The new status.

        Returns:
            The updated artifact if found.
        """
        update_data = {"status": status}
        if status == ArtifactStatus.COMPLETED:
            update_data["generated_at"] = datetime.now(timezone.utc)
        return await self.update(artifact_id, **update_data)

    async def mark_failed(
        self, artifact_id: uuid.UUID, error_message: Optional[str] = None
    ) -> Optional[Artifact]:
        """
        Mark an artifact as failed.

        Args:
            artifact_id: The artifact ID.
            error_message: Optional error message in metadata.

        Returns:
            The updated artifact if found.
        """
        metadata = {"error": error_message} if error_message else {}
        return await self.update(
            artifact_id,
            status=ArtifactStatus.FAILED,
            metadata=metadata,
        )

    async def create_new_version(
        self,
        artifact_id: uuid.UUID,
        content: dict,
        changelog: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> ArtifactVersion:
        """
        Create a new version of an artifact.

        Args:
            artifact_id: The artifact ID.
            content: The new content.
            changelog: Description of changes.
            created_by: The user creating the version.

        Returns:
            The created version.
        """
        artifact = await self.get_by_id(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        # Create version record from current state
        version = ArtifactVersion(
            artifact_id=artifact_id,
            version=artifact.version,
            content=artifact.content,
            changelog=changelog,
            created_by=created_by,
        )
        self.session.add(version)

        # Update artifact with new content
        new_version = artifact.version + 1
        checksum = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()

        await self.update(
            artifact_id,
            version=new_version,
            content=content,
            checksum=checksum,
            status=ArtifactStatus.PENDING,
        )

        await self.session.flush()
        return version

    async def rollback_to_version(
        self, artifact_id: uuid.UUID, version_number: int
    ) -> Optional[Artifact]:
        """
        Rollback an artifact to a previous version.

        Args:
            artifact_id: The artifact ID.
            version_number: The version number to rollback to.

        Returns:
            The updated artifact if found.
        """
        # Get the version to rollback to
        query = (
            select(ArtifactVersion)
            .where(
                and_(
                    ArtifactVersion.artifact_id == artifact_id,
                    ArtifactVersion.version == version_number,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(query)
        version = result.scalar_one_or_none()

        if not version:
            raise ValueError(
                f"Version {version_number} not found for artifact {artifact_id}"
            )

        # Create a new version with the old content
        return await self.create_new_version(
            artifact_id=artifact_id,
            content=version.content,
            changelog=f"Rollback to version {version_number}",
        )

    async def set_as_latest(self, artifact_id: uuid.UUID) -> Optional[Artifact]:
        """
        Set an artifact as the latest version.

        Args:
            artifact_id: The artifact ID.

        Returns:
            The updated artifact.
        """
        artifact = await self.get_by_id(artifact_id)
        if not artifact:
            return None

        # Mark all other versions as not latest
        update_query = (
            select(Artifact)
            .where(
                and_(
                    Artifact.project_id == artifact.project_id,
                    Artifact.artifact_type == artifact.artifact_type,
                    Artifact.id != artifact_id,
                )
            )
        )

        # Note: This needs to be done in a transaction
        result = await self.session.execute(update_query)
        for other_artifact in result.scalars().all():
            await self.update(other_artifact.id, is_latest=False)

        return await self.update(artifact_id, is_latest=True)

    async def calculate_file_size(self, artifact_id: uuid.UUID) -> int:
        """
        Calculate and update the file size of an artifact.

        Args:
            artifact_id: The artifact ID.

        Returns:
            The calculated file size.
        """
        artifact = await self.get_by_id(artifact_id)
        if not artifact:
            return 0

        content_str = json.dumps(artifact.content)
        file_size = len(content_str.encode("utf-8"))

        await self.update(artifact_id, file_size=file_size)
        return file_size

    async def get_artifact_stats(self, project_id: uuid.UUID) -> dict:
        """
        Get statistics about artifacts in a project.

        Args:
            project_id: The project ID.

        Returns:
            Dictionary with artifact statistics.
        """
        from sqlalchemy import func

        stats = {
            "total": 0,
            "by_type": {},
            "by_status": {},
        }

        # Total count
        query = select(func.count()).select_from(Artifact).where(
            Artifact.project_id == project_id
        )
        result = await self.session.execute(query)
        stats["total"] = result.scalar_one() or 0

        # By type
        for artifact_type in ArtifactType:
            query = select(func.count()).select_from(Artifact).where(
                and_(
                    Artifact.project_id == project_id,
                    Artifact.artifact_type == artifact_type,
                )
            )
            result = await self.session.execute(query)
            stats["by_type"][artifact_type.value] = result.scalar_one() or 0

        # By status
        for status in ArtifactStatus:
            query = select(func.count()).select_from(Artifact).where(
                and_(
                    Artifact.project_id == project_id,
                    Artifact.status == status,
                )
            )
            result = await self.session.execute(query)
            stats["by_status"][status.value] = result.scalar_one() or 0

        return stats

    async def search_artifacts(
        self, project_id: uuid.UUID, query: str, limit: int = 50
    ) -> List[Artifact]:
        """
        Search artifacts by title or description.

        Args:
            project_id: The project ID.
            query: The search query.
            limit: Maximum number of results.

        Returns:
            List of matching artifacts.
        """
        search_query = (
            select(Artifact)
            .where(
                and_(
                    Artifact.project_id == project_id,
                    or_(
                        Artifact.title.ilike(f"%{query}%"),
                        Artifact.description.ilike(f"%{query}%"),
                    ),
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(search_query)
        return list(result.scalars().all())


class ArtifactVersionRepository(BaseRepository[ArtifactVersion]):
    """
    Repository for ArtifactVersion data access operations.

    Provides methods for:
    - Version CRUD operations
    - Version history queries
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the ArtifactVersionRepository.

        Args:
            session: The async database session.
        """
        super().__init__(ArtifactVersion, session)

    async def get_by_artifact_and_version(
        self, artifact_id: uuid.UUID, version: int
    ) -> Optional[ArtifactVersion]:
        """
        Get a specific version of an artifact.

        Args:
            artifact_id: The artifact ID.
            version: The version number.

        Returns:
            The version if found.
        """
        query = select(ArtifactVersion).where(
            and_(
                ArtifactVersion.artifact_id == artifact_id,
                ArtifactVersion.version == version,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_version_history(
        self, artifact_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> List[ArtifactVersion]:
        """
        Get the version history of an artifact.

        Args:
            artifact_id: The artifact ID.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of versions ordered by version (descending).
        """
        query = (
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .offset(skip)
            .limit(limit)
            .order_by(ArtifactVersion.version.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_version(
        self, artifact_id: uuid.UUID
    ) -> Optional[ArtifactVersion]:
        """
        Get the latest version of an artifact.

        Args:
            artifact_id: The artifact ID.

        Returns:
            The latest version.
        """
        query = (
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_version_count(self, artifact_id: uuid.UUID) -> int:
        """
        Get the number of versions for an artifact.

        Args:
            artifact_id: The artifact ID.

        Returns:
            The version count.
        """
        from sqlalchemy import func

        query = select(func.count()).select_from(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact_id
        )
        result = await self.session.execute(query)
        return result.scalar_one() or 0


# Import for timezone-aware datetime
from datetime import timezone  # noqa: E402
