"""
Storage Service

High-level storage operations for:
- Artifact file management
- Upload/download handling
- File organization by project/artifact
- Presigned URL generation
"""

import hashlib
import os
import shutil
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID

from backend.storage.client import StorageClient, get_storage_client


class FileType(str, Enum):
    """File type enumeration."""

    DOCUMENT = "document"
    IMAGE = "image"
    ARCHIVE = "archive"
    OTHER = "other"


class StorageService:
    """
    Storage service for artifact and file management.

    Handles:
    - File uploads with automatic organization
    - Download with optional decompression
    - File metadata tracking
    - Presigned URL generation
    - Cleanup operations
    """

    # File type mappings
    DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".rst"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
    ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".7z", ".rar"}

    def __init__(self, client: StorageClient = None):
        """
        Initialize storage service.

        Args:
            client: Storage client (auto-initialized if not provided)
        """
        self.client = client or get_storage_client()

    async def initialize(self) -> None:
        """Initialize the storage service."""
        await self.client.connect()

    def _detect_file_type(self, filename: str) -> FileType:
        """Detect file type from extension."""
        ext = Path(filename).suffix.lower()

        if ext in self.DOCUMENT_EXTENSIONS:
            return FileType.DOCUMENT
        elif ext in self.IMAGE_EXTENSIONS:
            return FileType.IMAGE
        elif ext in self.ARCHIVE_EXTENSIONS:
            return FileType.ARCHIVE
        else:
            return FileType.OTHER

    def _generate_storage_key(
        self,
        project_id: UUID,
        artifact_id: UUID,
        filename: str,
    ) -> str:
        """Generate storage key for a file."""
        date = datetime.utcnow().strftime("%Y/%m/%d")
        file_type = self._detect_file_type(filename)
        unique_id = uuid.uuid4().hex[:8]

        return f"projects/{project_id}/artifacts/{artifact_id}/{date}/{unique_id}_{filename}"

    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate SHA-256 checksum for data."""
        return hashlib.sha256(data).hexdigest()

    async def upload_artifact(
        self,
        project_id: UUID,
        artifact_id: UUID,
        filename: str,
        data: bytes,
        content_type: str = None,
        metadata: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Upload an artifact file.

        Args:
            project_id: Project UUID
            artifact_id: Artifact UUID
            filename: Original filename
            data: File data
            content_type: MIME type
            metadata: Additional metadata

        Returns:
            Upload result with file info
        """
        # Generate storage key
        key = self._generate_storage_key(project_id, artifact_id, filename)

        # Detect content type if not provided
        if content_type is None:
            content_type = self._guess_content_type(filename)

        # Calculate checksum
        checksum = self._calculate_checksum(data)

        # Add checksum to metadata
        file_metadata = {
            "original_filename": filename,
            "project_id": str(project_id),
            "artifact_id": str(artifact_id),
            "checksum": checksum,
            "uploaded_at": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }

        # Upload file
        await self.client.upload_file(
            key=key,
            data=data,
            content_type=content_type,
            metadata=file_metadata,
        )

        # Return file info
        return {
            "key": key,
            "filename": filename,
            "size": len(data),
            "content_type": content_type,
            "checksum": checksum,
            "url": await self.client.generate_presigned_url(key),
        }

    async def upload_file_stream(
        self,
        project_id: UUID,
        artifact_id: UUID,
        filename: str,
        file_stream: BinaryIO,
        content_type: str = None,
        metadata: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Upload a file from a stream."""
        data = file_stream.read()
        return await self.upload_artifact(
            project_id=project_id,
            artifact_id=artifact_id,
            filename=filename,
            data=data,
            content_type=content_type,
            metadata=metadata,
        )

    async def download_artifact(
        self,
        project_id: UUID,
        artifact_id: UUID,
        filename: str = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Download an artifact file.

        Args:
            project_id: Project UUID
            artifact_id: Artifact UUID
            filename: Optional specific filename (gets latest if not provided)

        Returns:
            Tuple of (file data, metadata)
        """
        # Find the file
        prefix = f"projects/{project_id}/artifacts/{artifact_id}/"

        files = await self.client.list_files(prefix=prefix)

        if not files:
            raise FileNotFoundError(f"No files found for artifact {artifact_id}")

        # Use the first file or match filename
        if filename:
            target = next((f for f in files if filename in f["key"]), files[0])
        else:
            target = files[0]

        # Download file
        data = await self.client.download_file(target["key"])

        # Get file info
        info = await self.client.get_file_info(target["key"])

        return data, info

    async def delete_artifact(
        self,
        project_id: UUID,
        artifact_id: UUID,
    ) -> int:
        """
        Delete all files for an artifact.

        Args:
            project_id: Project UUID
            artifact_id: Artifact UUID

        Returns:
            Number of files deleted
        """
        prefix = f"projects/{project_id}/artifacts/{artifact_id}/"

        files = await self.client.list_files(prefix=prefix)

        deleted = 0
        for file_info in files:
            if await self.client.delete_file(file_info["key"]):
                deleted += 1

        return deleted

    async def list_project_files(
        self,
        project_id: UUID,
        artifact_id: UUID = None,
        max_keys: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List files for a project.

        Args:
            project_id: Project UUID
            artifact_id: Optional artifact UUID filter
            max_keys: Maximum files to return

        Returns:
            List of file information
        """
        if artifact_id:
            prefix = f"projects/{project_id}/artifacts/{artifact_id}/"
        else:
            prefix = f"projects/{project_id}/"

        return await self.client.list_files(prefix=prefix, max_keys=max_keys)

    async def get_file_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Get a presigned URL for a file.

        Args:
            key: File key
            expires_in: URL expiration time in seconds

        Returns:
            Presigned URL
        """
        return await self.client.generate_presigned_url(key, expires_in=expires_in)

    async def verify_checksum(
        self,
        key: str,
        expected_checksum: str,
    ) -> bool:
        """
        Verify file checksum.

        Args:
            key: File key
            expected_checksum: Expected SHA-256 checksum

        Returns:
            True if checksum matches
        """
        data = await self.client.download_file(key)
        actual_checksum = self._calculate_checksum(data)

        return actual_checksum == expected_checksum

    async def cleanup_orphaned_files(
        self,
        project_id: UUID,
        valid_artifact_ids: List[UUID],
    ) -> int:
        """
        Remove files for artifacts that no longer exist.

        Args:
            project_id: Project UUID
            valid_artifact_ids: List of valid artifact IDs

        Returns:
            Number of files deleted
        """
        prefix = f"projects/{project_id}/artifacts/"
        files = await self.client.list_files(prefix=prefix)

        valid_ids = {str(id) for id in valid_artifact_ids}
        deleted = 0

        for file_info in files:
            # Extract artifact_id from key
            # Format: projects/{project_id}/artifacts/{artifact_id}/...
            parts = file_info["key"].split("/")

            if len(parts) >= 4:
                artifact_id = parts[3]

                if artifact_id not in valid_ids:
                    await self.client.delete_file(file_info["key"])
                    deleted += 1

        return deleted

    def _guess_content_type(self, filename: str) -> str:
        """Guess content type from filename."""
        import mimetypes

        content_type, _ = mimetypes.guess_type(filename)

        return content_type or "application/octet-stream"

    async def health_check(self) -> Dict[str, Any]:
        """Check storage service health."""
        try:
            # Try to list files (will fail if no access)
            await self.client.list_files(prefix="", max_keys=1)
            return {
                "status": "healthy",
                "provider": type(self.client).__name__,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def close(self) -> None:
        """Close the storage service."""
        await self.client.disconnect()


# Service instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get storage service instance."""
    global _storage_service

    if _storage_service is None:
        _storage_service = StorageService()

    return _storage_service
