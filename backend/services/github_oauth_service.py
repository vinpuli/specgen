"""
GitHub OAuth service for brownfield repository access.

This service provides:
- OAuth authorization URL generation with repository scopes
- OAuth code exchange for access tokens
- Repository listing for authenticated user
- Repository access validation for analysis requests
"""

import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import httpx


logger = logging.getLogger(__name__)


class GitHubOAuthError(Exception):
    """Base exception for GitHub OAuth service errors."""


class GitHubOAuthConfigError(GitHubOAuthError):
    """Raised when required GitHub OAuth configuration is missing."""


class GitHubRepositoryAccessError(GitHubOAuthError):
    """Raised when repository access validation fails."""


class GitHubOAuthService:
    """
    Service handling GitHub OAuth and repository access operations.
    """

    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    API_BASE_URL = "https://api.github.com"
    DEFAULT_SCOPE = "repo read:user user:email"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ):
        self.client_id = client_id or os.getenv("GITHUB_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GITHUB_CLIENT_SECRET")
        self.timeout_seconds = timeout_seconds

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        scope: Optional[str] = None,
    ) -> str:
        """
        Build GitHub OAuth authorization URL for repository access.
        """
        if not self.client_id:
            raise GitHubOAuthConfigError("GITHUB_CLIENT_ID is not configured")

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope or self.DEFAULT_SCOPE,
            "state": state,
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for GitHub access token.
        """
        if not self.client_id or not self.client_secret:
            raise GitHubOAuthConfigError(
                "GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET must be configured"
            )

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            error = token_data.get("error_description") or token_data.get("error") or "token exchange failed"
            raise GitHubOAuthError(f"GitHub token exchange failed: {error}")

        return token_data

    async def list_repositories(
        self,
        access_token: str,
        visibility: str = "all",
        page: int = 1,
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        List repositories accessible to the authenticated GitHub user.
        """
        params = {
            "visibility": visibility,
            "sort": "updated",
            "page": page,
            "per_page": per_page,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.API_BASE_URL}/user/repos",
                params=params,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

        if response.status_code == 401:
            raise GitHubOAuthError("Invalid GitHub access token")
        if response.status_code >= 400:
            raise GitHubOAuthError(
                f"Failed to list repositories (status {response.status_code})"
            )

        data = response.json()
        if not isinstance(data, list):
            raise GitHubOAuthError("Unexpected GitHub repositories response format")
        return data

    async def verify_repository_access(
        self,
        repository_url: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify that repository exists and token (if provided) can access it.
        """
        owner, repo = self._parse_repository_url(repository_url)
        headers = {"Accept": "application/vnd.github+json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.API_BASE_URL}/repos/{owner}/{repo}",
                headers=headers,
            )

        if response.status_code == 404:
            if access_token:
                raise GitHubRepositoryAccessError(
                    "Repository not found or not accessible with the provided token"
                )
            raise GitHubRepositoryAccessError(
                "Repository not found or private. Provide github_access_token for private repositories."
            )
        if response.status_code == 401:
            raise GitHubRepositoryAccessError("Invalid GitHub access token")
        if response.status_code == 403:
            raise GitHubRepositoryAccessError("Insufficient GitHub token permissions for repository access")
        if response.status_code >= 400:
            raise GitHubRepositoryAccessError(
                f"GitHub repository access check failed (status {response.status_code})"
            )

        repo_data = response.json()
        return {
            "id": repo_data.get("id"),
            "name": repo_data.get("name"),
            "full_name": repo_data.get("full_name"),
            "private": repo_data.get("private", False),
            "default_branch": repo_data.get("default_branch"),
            "html_url": repo_data.get("html_url"),
        }

    @staticmethod
    def _parse_repository_url(repository_url: str) -> Tuple[str, str]:
        """
        Parse GitHub repository URL into (owner, repo).
        """
        cleaned = repository_url.strip()
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]

        parsed = urllib.parse.urlparse(cleaned)
        if parsed.netloc and "github.com" not in parsed.netloc.lower():
            raise GitHubRepositoryAccessError("Only github.com repository URLs are supported")

        path = parsed.path.strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            raise GitHubRepositoryAccessError(
                "Invalid GitHub repository URL format. Expected https://github.com/{owner}/{repo}"
            )

        owner = parts[0]
        repo = parts[1]
        return owner, repo
