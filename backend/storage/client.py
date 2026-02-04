"""
S3-compatible Storage Client

Supports multiple S3-compatible storage providers:
- AWS S3 (cloud)
- MinIO (local development)
- Google Cloud Storage
- DigitalOcean Spaces
"""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from uuid import UUID


class StorageClient(ABC):
    """Abstract base class for storage clients."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to storage."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from storage."""
        pass

    @abstractmethod
    async def upload_file(
        self,
        key: str,
        data: bytes,
        content_type: str = None,
        metadata: Dict[str, str] = None,
    ) -> str:
        """Upload a file."""
        pass

    @abstractmethod
    async def download_file(self, key: str) -> bytes:
        """Download a file."""
        pass

    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        """Delete a file."""
        pass

    @abstractmethod
    async def list_files(
        self,
        prefix: str = None,
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """List files in a prefix."""
        pass

    @abstractmethod
    async def get_file_info(self, key: str) -> Dict[str, Any]:
        """Get file information."""
        pass

    @abstractmethod
    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Generate a presigned URL."""
        pass


class S3Client(StorageClient):
    """AWS S3 / S3-compatible storage client."""

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket: str = None,
        region: str = None,
        secure: bool = True,
    ):
        import boto3

        self.endpoint = endpoint or os.getenv("S3_ENDPOINT")
        self.access_key = access_key or os.getenv("S3_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("S3_SECRET_KEY")
        self.bucket = bucket or os.getenv("S3_BUCKET", "specgen-artifacts")
        self.region = region or os.getenv("S3_REGION", "us-east-1")
        self.secure = secure

        self._client = None

    async def connect(self) -> None:
        """Connect to S3."""
        import botocore.config
        import boto3

        config = botocore.config.Config(
            signature_version=botocore.UNSIGNED,
        )

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint if self.endpoint else None,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=config,
        )

        # Ensure bucket exists
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except self._client.exceptions.NoSuchBucket:
            self._client.create_bucket(Bucket=self.bucket)

    async def disconnect(self) -> None:
        """Disconnect from S3."""
        # boto3 client doesn't need explicit disconnect
        self._client = None

    async def upload_file(
        self,
        key: str,
        data: bytes,
        content_type: str = None,
        metadata: Dict[str, str] = None,
    ) -> str:
        """Upload a file to S3."""
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata

        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            **extra_args,
        )

        return key

    async def download_file(self, key: str) -> bytes:
        """Download a file from S3."""
        response = self._client.get_object(
            Bucket=self.bucket,
            Key=key,
        )
        return response["Body"].read()

    async def delete_file(self, key: str) -> bool:
        """Delete a file from S3."""
        try:
            self._client.delete_object(
                Bucket=self.bucket,
                Key=key,
            )
            return True
        except Exception:
            return False

    async def list_files(
        self,
        prefix: str = None,
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """List files in S3."""
        paginator = self._client.get_paginator("list_objects_v2")

        files = []
        for page in paginator.paginate(
            Bucket=self.bucket,
            Prefix=prefix or "",
            MaxKeys=max_keys,
        ):
            for obj in page.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj["ETag"],
                })

        return files

    async def get_file_info(self, key: str) -> Dict[str, Any]:
        """Get file information from S3."""
        response = self._client.head_object(
            Bucket=self.bucket,
            Key=key,
        )

        return {
            "key": key,
            "size": response["ContentLength"],
            "content_type": response.get("ContentType"),
            "last_modified": response["LastModified"].isoformat(),
            "metadata": response.get("Metadata", {}),
            "etag": response.get("ETag"),
        }

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Generate a presigned URL."""
        return self._client.generate_presigned_url(
            ClientMethod=method.lower(),
            Params={
                "Bucket": self.bucket,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )


class MinIOClient(S3Client):
    """MinIO storage client (S3-compatible)."""

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket: str = None,
        secure: bool = False,
    ):
        endpoint = endpoint or os.getenv("S3_ENDPOINT", "http://localhost:9000")
        access_key = access_key or os.getenv("S3_ACCESS_KEY", "minioadmin")
        secret_key = secret_key or os.getenv("S3_SECRET_KEY", "minioadmin")
        bucket = bucket or os.getenv("S3_BUCKET", "specgen-artifacts")

        super().__init__(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            region=os.getenv("S3_REGION", "us-east-1"),
            secure=secure if endpoint.startswith("https") else False,
        )


class LocalStorageClient(StorageClient):
    """Local filesystem storage client (for development)."""

    def __init__(
        self,
        base_path: str = None,
        base_url: str = None,
    ):
        self.base_path = base_path or os.getenv("STORAGE_LOCAL_PATH", "./uploads")
        self.base_url = base_url or os.getenv("STORAGE_LOCAL_URL", "http://localhost:8000/uploads")
        self._ensure_base_path()

    def _ensure_base_path(self):
        """Ensure base path exists."""
        import os
        os.makedirs(self.base_path, exist_ok=True)

    def _get_full_path(self, key: str) -> str:
        """Get full filesystem path."""
        return os.path.join(self.base_path, key)

    async def connect(self) -> None:
        """Connect to local storage (no-op)."""
        self._ensure_base_path()

    async def disconnect(self) -> None:
        """Disconnect from local storage (no-op)."""
        pass

    async def upload_file(
        self,
        key: str,
        data: bytes,
        content_type: str = None,
        metadata: Dict[str, str] = None,
    ) -> str:
        """Upload a file to local storage."""
        full_path = self._get_full_path(key)

        # Create directory structure
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write file
        with open(full_path, "wb") as f:
            f.write(data)

        return key

    async def download_file(self, key: str) -> bytes:
        """Download a file from local storage."""
        full_path = self._get_full_path(key)

        with open(full_path, "rb") as f:
            return f.read()

    async def delete_file(self, key: str) -> bool:
        """Delete a file from local storage."""
        import os

        full_path = self._get_full_path(key)

        if os.path.exists(full_path):
            os.remove(full_path)
            return True

        return False

    async def list_files(
        self,
        prefix: str = None,
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """List files in local storage."""
        import os
        from datetime import datetime

        base = os.path.join(self.base_path, prefix or "")
        files = []

        for root, _, filenames in os.walk(base):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                stat = os.stat(full_path)

                rel_path = os.path.relpath(full_path, self.base_path)
                files.append({
                    "key": rel_path,
                    "size": stat.st_size,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

                if len(files) >= max_keys:
                    break

        return files[:max_keys]

    async def get_file_info(self, key: str) -> Dict[str, Any]:
        """Get file information from local storage."""
        import os
        from datetime import datetime

        full_path = self._get_full_path(key)
        stat = os.stat(full_path)

        return {
            "key": key,
            "size": stat.st_size,
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Generate a presigned URL (not supported for local)."""
        return f"{self.base_url}/{key}"


def get_storage_client() -> StorageClient:
    """Get storage client based on configuration."""
    provider = os.getenv("S3_PROVIDER", "local")

    if provider == "aws" or provider == "s3":
        return S3Client()
    elif provider == "minio":
        return MinIOClient()
    elif provider == "local":
        return LocalStorageClient()
    else:
        raise ValueError(f"Unknown storage provider: {provider}")
