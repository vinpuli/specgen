"""
Codebase Analysis Pydantic schemas.

This module provides:
- Codebase analysis request/response schemas
- Impact analysis schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin


# ======================
# Codebase Analysis Schemas
# ======================


class CodebaseAnalysisCreate(BaseSchema):
    """Request to trigger codebase analysis."""

    project_id: UUID = Field(..., description="Project ID")
    repository_url: Optional[str] = Field(
        None, description="Repository URL (optional if already set in project)"
    )
    branch_name: Optional[str] = Field(
        None, description="Branch name to analyze"
    )
    directory_scope: Optional[List[str]] = Field(
        None,
        description="Optional list of repository directories to analyze (partial analysis)",
    )
    github_access_token: Optional[str] = Field(
        None,
        description="Optional GitHub OAuth access token for private repository access",
    )
    gitlab_access_token: Optional[str] = Field(
        None,
        description="Optional GitLab OAuth access token for private repository access",
    )
    gitlab_base_url: Optional[str] = Field(
        None,
        description="Optional GitLab base URL for self-hosted instances (e.g. https://gitlab.example.com)",
    )


class GitHubOAuthAuthorizeResponse(BaseSchema):
    """Response with GitHub OAuth authorization URL for repository access."""

    provider: str = Field(default="github")
    auth_url: str = Field(..., description="GitHub OAuth authorization URL")
    state: str = Field(..., description="OAuth state for callback validation")
    scope: str = Field(..., description="Requested OAuth scope")


class GitHubOAuthTokenExchangeRequest(BaseSchema):
    """Request to exchange GitHub OAuth code for access token."""

    code: str = Field(..., description="Authorization code returned by GitHub")
    redirect_uri: str = Field(..., description="Redirect URI used in OAuth authorize request")


class GitHubOAuthTokenResponse(BaseSchema):
    """Response containing GitHub OAuth access token details."""

    access_token: str = Field(..., description="GitHub access token")
    token_type: str = Field(default="bearer", description="Token type")
    scope: Optional[str] = Field(default=None, description="Granted OAuth scopes")


class GitHubRepositorySummary(BaseSchema):
    """Simplified GitHub repository metadata."""

    id: int
    name: str
    full_name: str
    private: bool
    html_url: str
    default_branch: Optional[str] = None
    visibility: Optional[str] = None


class GitHubRepositoryListResponse(BaseSchema):
    """Response for listing accessible GitHub repositories."""

    repositories: List[GitHubRepositorySummary] = Field(default_factory=list)
    total: int = 0


class GitLabOAuthAuthorizeResponse(BaseSchema):
    """Response with GitLab OAuth authorization URL for repository access."""

    provider: str = Field(default="gitlab")
    auth_url: str = Field(..., description="GitLab OAuth authorization URL")
    state: str = Field(..., description="OAuth state for callback validation")
    scope: str = Field(..., description="Requested OAuth scope")
    base_url: str = Field(..., description="GitLab base URL used for OAuth")


class GitLabOAuthTokenExchangeRequest(BaseSchema):
    """Request to exchange GitLab OAuth code for access token."""

    code: str = Field(..., description="Authorization code returned by GitLab")
    redirect_uri: str = Field(..., description="Redirect URI used in OAuth authorize request")
    base_url: Optional[str] = Field(
        default=None,
        description="Optional GitLab base URL for self-hosted instances",
    )


class GitLabOAuthTokenResponse(BaseSchema):
    """Response containing GitLab OAuth access token details."""

    access_token: str = Field(..., description="GitLab access token")
    token_type: str = Field(default="bearer", description="Token type")
    scope: Optional[str] = Field(default=None, description="Granted OAuth scopes")
    created_at: Optional[int] = Field(default=None, description="Token creation timestamp (unix)")


class GitLabProjectSummary(BaseSchema):
    """Simplified GitLab project metadata."""

    id: int
    name: str
    path_with_namespace: str
    private: bool
    web_url: str
    default_branch: Optional[str] = None
    visibility: Optional[str] = None


class GitLabProjectListResponse(BaseSchema):
    """Response for listing accessible GitLab projects."""

    projects: List[GitLabProjectSummary] = Field(default_factory=list)
    total: int = 0


class CodebaseAnalysisResponse(BaseSchema):
    """Response after triggering analysis."""

    id: UUID
    project_id: UUID
    status: str = Field(..., description="Analysis status: pending, in_progress, completed, failed")
    repository_url: Optional[str] = None
    branch_name: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[str] = None


class CodebaseAnalysisResultResponse(BaseSchema):
    """Full analysis results response."""

    id: UUID
    project_id: UUID
    status: str
    repository_url: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    language_stats: Dict[str, Any] = Field(default_factory=dict)
    total_loc: Optional[int] = None
    file_count: Optional[int] = None
    architecture_summary: Optional[str] = None
    component_inventory: List[Dict[str, Any]] = Field(default_factory=list)
    dependency_graph: Dict[str, Any] = Field(default_factory=dict)
    detected_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


# ======================
# Impact Analysis Schemas
# ======================


class ImpactAnalysisCreate(BaseSchema):
    """Request to trigger impact analysis."""

    change_description: str = Field(
        ..., min_length=10, description="Description of the proposed change"
    )


class ImpactAnalysisResponse(BaseSchema):
    """Response after triggering or getting impact analysis."""

    id: UUID
    codebase_analysis_id: UUID
    project_id: UUID
    change_description: str
    status: str = Field(default="pending")
    affected_files: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    risk_level: Optional[str] = Field(
        None, description="Risk level: low, medium, high, critical"
    )
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    breaking_changes: List[Dict[str, Any]] = Field(default_factory=list)
    downstream_dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    rollback_procedure: Optional[str] = None
    change_plan: List[Dict[str, Any]] = Field(default_factory=list)
    message: Optional[str] = None
    created_at: Optional[str] = None


class ImpactAnalysisDetailResponse(BaseSchema):
    """Full impact analysis detail response."""

    id: UUID
    codebase_analysis_id: UUID
    project_id: UUID
    change_description: str
    affected_files: List[str]
    affected_components: List[str]
    risk_level: str
    risk_factors: List[Dict[str, Any]]
    breaking_changes: List[Dict[str, Any]]
    api_changes: List[Dict[str, Any]]
    schema_changes: List[Dict[str, Any]]
    downstream_dependencies: List[Dict[str, Any]]
    upstream_dependencies: List[Dict[str, Any]]
    test_impact: Dict[str, Any]
    new_tests_needed: List[Dict[str, Any]]
    rollback_procedure: Optional[str]
    rollback_risk: Optional[str]
    change_plan: List[Dict[str, Any]]
    created_at: datetime
