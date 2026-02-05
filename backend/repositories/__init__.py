"""
Repository layer for data access operations.

This module provides a repository pattern implementation for:
- User data access (TICKET-034)
- Workspace data access (TICKET-035)
- Project data access (TICKET-036)
- Decision data access (TICKET-037)
- Artifact data access (TICKET-038)
"""

from backend.repositories.base import BaseRepository
from backend.repositories.user import UserRepository
from backend.repositories.workspace import WorkspaceRepository, WorkspaceMemberRepository
from backend.repositories.project import ProjectRepository, BranchRepository
from backend.repositories.decision import DecisionRepository, DecisionDependencyRepository
from backend.repositories.artifact import ArtifactRepository, ArtifactVersionRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "WorkspaceRepository",
    "WorkspaceMemberRepository",
    "ProjectRepository",
    "BranchRepository",
    "DecisionRepository",
    "DecisionDependencyRepository",
    "ArtifactRepository",
    "ArtifactVersionRepository",
]
