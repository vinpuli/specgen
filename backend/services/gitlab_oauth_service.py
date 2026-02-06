"""
GitLab OAuth service for brownfield repository access.

Supports:
- GitLab.com OAuth
- Self-hosted GitLab OAuth (custom base URL)
- Project listing and repository access verification
"""

import os
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import httpx


class GitLabOAuthError(Exception):
    """Base exception for GitLab OAuth operations."""


class GitLabOAuthConfigError(GitLabOAuthError):
    """Raised when GitLab OAuth configuration is missing."""


class GitLabRepositoryAccessError(GitLabOAuthError):
    """Raised when GitLab repository/project access validation fails."""


class GitLabOAuthService:
    """Service for GitLab OAuth and repository access checks."""

    DEFAULT_BASE_URL = "https://gitlab.com"
    DEFAULT_SCOPE = "read_user read_api"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        timeout_seconds: float = 15.0,
        default_base_url: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("GITLAB_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GITLAB_CLIENT_SECRET")
        self.timeout_seconds = timeout_seconds
        self.default_base_url = default_base_url or os.getenv("GITLAB_BASE_URL", self.DEFAULT_BASE_URL)

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        scope: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> tuple[str, str]:
        """Build GitLab OAuth authorization URL."""
        if not self.client_id:
            raise GitLabOAuthConfigError("GITLAB_CLIENT_ID is not configured")

        resolved_base = self._normalize_base_url(base_url)
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope or self.DEFAULT_SCOPE,
            "state": state,
        }
        auth_url = f"{resolved_base}/oauth/authorize?{urllib.parse.urlencode(params)}"
        return auth_url, resolved_base

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange GitLab auth code for OAuth token."""
        if not self.client_id or not self.client_secret:
            raise GitLabOAuthConfigError("GITLAB_CLIENT_ID/GITLAB_CLIENT_SECRET must be configured")

        resolved_base = self._normalize_base_url(base_url)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{resolved_base}/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

        token_data = response.json()
        if "access_token" not in token_data:
            error = token_data.get("error_description") or token_data.get("error") or "token exchange failed"
            raise GitLabOAuthError(f"GitLab token exchange failed: {error}")
        return token_data

    async def list_projects(
        self,
        access_token: str,
        base_url: Optional[str] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """List projects accessible to GitLab OAuth token."""
        resolved_base = self._normalize_base_url(base_url)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{resolved_base}/api/v4/projects",
                params={
                    "membership": "true",
                    "simple": "true",
                    "order_by": "last_activity_at",
                    "sort": "desc",
                    "page": page,
                    "per_page": per_page,
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.status_code == 401:
            raise GitLabOAuthError("Invalid GitLab access token")
        if response.status_code >= 400:
            raise GitLabOAuthError(f"Failed to list GitLab projects (status {response.status_code})")

        data = response.json()
        if not isinstance(data, list):
            raise GitLabOAuthError("Unexpected GitLab projects response format")
        return data

    async def verify_repository_access(
        self,
        repository_url: str,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify repository/project accessibility via GitLab API."""
        project_path, inferred_base = self._parse_repository_url(repository_url)
        resolved_base = self._normalize_base_url(base_url or inferred_base)
        encoded_project = urllib.parse.quote(project_path, safe="")

        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{resolved_base}/api/v4/projects/{encoded_project}",
                headers=headers,
            )

        if response.status_code == 404:
            if access_token:
                raise GitLabRepositoryAccessError(
                    "GitLab project not found or not accessible with provided token"
                )
            raise GitLabRepositoryAccessError(
                "GitLab project not found or private. Provide gitlab_access_token for private repositories."
            )
        if response.status_code == 401:
            raise GitLabRepositoryAccessError("Invalid GitLab access token")
        if response.status_code == 403:
            raise GitLabRepositoryAccessError("Insufficient GitLab token permissions for repository access")
        if response.status_code >= 400:
            raise GitLabRepositoryAccessError(
                f"GitLab repository access check failed (status {response.status_code})"
            )

        project_data = response.json()
        return {
            "id": project_data.get("id"),
            "name": project_data.get("name"),
            "path_with_namespace": project_data.get("path_with_namespace"),
            "private": project_data.get("visibility") == "private",
            "default_branch": project_data.get("default_branch"),
            "web_url": project_data.get("web_url"),
            "base_url": resolved_base,
        }

    def _normalize_base_url(self, base_url: Optional[str]) -> str:
        """Normalize GitLab base URL for cloud/self-hosted usage."""
        resolved = (base_url or self.default_base_url or self.DEFAULT_BASE_URL).strip()
        if not resolved.startswith("http://") and not resolved.startswith("https://"):
            resolved = f"https://{resolved}"
        return resolved.rstrip("/")

    @staticmethod
    def _parse_repository_url(repository_url: str) -> Tuple[str, str]:
        """
        Parse GitLab repository URL to project path and inferred base URL.
        """
        cleaned = repository_url.strip()
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]

        parsed = urllib.parse.urlparse(cleaned)
        if not parsed.scheme or not parsed.netloc:
            raise GitLabRepositoryAccessError("Invalid repository URL format")

        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) < 2:
            raise GitLabRepositoryAccessError(
                "Invalid GitLab repository URL format. Expected https://host/group/project"
            )

        project_path = "/".join(parts)
        inferred_base = f"{parsed.scheme}://{parsed.netloc}"
        return project_path, inferred_base
