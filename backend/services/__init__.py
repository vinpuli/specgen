"""
Services module for business logic.

This module provides:
- User service for authentication
- Workspace service for workspace management
- Project service for project management
- Decision service for decision tracking
"""

from backend.services.user_service import (
    UserService,
    UserServiceError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserNotFoundError,
    WeakPasswordError,
    InactiveUserError,
)
from backend.services.workspace_service import (
    WorkspaceService,
    WorkspaceServiceError,
    WorkspaceNotFoundError,
    WorkspaceMemberNotFoundError,
    InsufficientPermissionsError,
)
from backend.services.project_service import (
    ProjectService,
    ProjectServiceError,
    ProjectNotFoundError,
    BranchNotFoundError,
    TemplateNotFoundError,
)
from backend.services.decision_service import (
    DecisionService,
    DecisionServiceError,
    DecisionNotFoundError,
)
from backend.services.artifact_service import (
    ArtifactService,
    ArtifactServiceError,
    ArtifactNotFoundError,
    VersionNotFoundError,
)
from backend.services.session_service import (
    TokenBlacklistService,
    get_token_blacklist_service,
)
from backend.services.github_oauth_service import (
    GitHubOAuthService,
    GitHubOAuthError,
    GitHubOAuthConfigError,
    GitHubRepositoryAccessError,
)
from backend.services.gitlab_oauth_service import (
    GitLabOAuthService,
    GitLabOAuthError,
    GitLabOAuthConfigError,
    GitLabRepositoryAccessError,
)
from backend.services.repository_clone_service import (
    RepositoryCloneService,
    RepositoryCloneError,
    RepositoryCloneResult,
)
from backend.services.tree_sitter_service import (
    TreeSitterService,
    TreeSitterServiceError,
    TreeSitterUnavailableError,
    TreeSitterUnsupportedLanguageError,
)

__all__ = [
    # User service
    "UserService",
    "UserServiceError",
    "UserAlreadyExistsError",
    "InvalidCredentialsError",
    "UserNotFoundError",
    "WeakPasswordError",
    "InactiveUserError",
    # Workspace service
    "WorkspaceService",
    "WorkspaceServiceError",
    "WorkspaceNotFoundError",
    "WorkspaceMemberNotFoundError",
    "InsufficientPermissionsError",
    # Project service
    "ProjectService",
    "ProjectServiceError",
    "ProjectNotFoundError",
    "BranchNotFoundError",
    "TemplateNotFoundError",
    # Decision service
    "DecisionService",
    "DecisionServiceError",
    "DecisionNotFoundError",
    # Artifact service
    "ArtifactService",
    "ArtifactServiceError",
    "ArtifactNotFoundError",
    "VersionNotFoundError",
    # Session service
    "TokenBlacklistService",
    "get_token_blacklist_service",
    # GitHub OAuth service
    "GitHubOAuthService",
    "GitHubOAuthError",
    "GitHubOAuthConfigError",
    "GitHubRepositoryAccessError",
    "GitLabOAuthService",
    "GitLabOAuthError",
    "GitLabOAuthConfigError",
    "GitLabRepositoryAccessError",
    "RepositoryCloneService",
    "RepositoryCloneError",
    "RepositoryCloneResult",
    "TreeSitterService",
    "TreeSitterServiceError",
    "TreeSitterUnavailableError",
    "TreeSitterUnsupportedLanguageError",
]
