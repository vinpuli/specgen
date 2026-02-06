"""
Database ToolNode for LangGraph agents.

This module provides ToolNode wrappers for database operations
that agents can use during execution.
"""

from typing import Any, Dict, List, Optional, Type
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from backend.db.session import get_db_session
from backend.db.models import (
    User, Workspace, Project, Branch, Decision,
    Artifact, ArtifactVersion, Comment, ConversationTurn,
)


# ==================== Database Tool Schemas ====================


class UserQuery(BaseModel):
    """Query parameters for user operations."""
    user_id: Optional[str] = None
    email: Optional[str] = None
    include_deleted: bool = False


class ProjectQuery(BaseModel):
    """Query parameters for project operations."""
    project_id: Optional[str] = None
    workspace_id: Optional[str] = None
    status: Optional[str] = None
    project_type: Optional[str] = None


class DecisionQuery(BaseModel):
    """Query parameters for decision operations."""
    decision_id: Optional[str] = None
    project_id: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None


class ArtifactQuery(BaseModel):
    """Query parameters for artifact operations."""
    artifact_id: Optional[str] = None
    project_id: Optional[str] = None
    artifact_type: Optional[str] = None
    format: Optional[str] = None


class BranchQuery(BaseModel):
    """Query parameters for branch operations."""
    branch_id: Optional[str] = None
    project_id: Optional[str] = None
    parent_branch_id: Optional[str] = None


class CreateDecisionInput(BaseModel):
    """Input for creating a decision."""
    project_id: str
    question_text: str
    answer_text: str
    category: str
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateArtifactInput(BaseModel):
    """Input for creating an artifact."""
    project_id: str
    artifact_type: str
    format: str
    content: str
    based_on_decisions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateBranchInput(BaseModel):
    """Input for creating a branch."""
    project_id: str
    name: str
    description: Optional[str] = None
    parent_branch_id: Optional[str] = None


class AddCommentInput(BaseModel):
    """Input for adding a comment."""
    artifact_id: str
    content: str
    parent_comment_id: Optional[str] = None


class UpdateProjectInput(BaseModel):
    """Input for updating a project."""
    project_id: str
    name: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


# ==================== Database Tools ====================


class GetUserTool(BaseTool):
    """Tool to retrieve user information."""
    name = "get_user"
    description = "Retrieve user information by ID or email"
    args_schema: Type[BaseModel] = UserQuery
    
    def _run(
        self,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_user(user_id, email, include_deleted))
    
    async def _aget_user(
        self,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                query = session.query(User)
                
                if user_id:
                    user = query.filter(User.id == user_id).first()
                elif email:
                    user = query.filter(User.email == email).first()
                else:
                    return {"success": False, "error": "Either user_id or email required"}
                
                if user:
                    return {
                        "success": True,
                        "user": {
                            "id": str(user.id),
                            "email": user.email,
                            "name": user.name,
                            "created_at": user.created_at.isoformat() if user.created_at else None,
                        }
                    }
                else:
                    return {"success": False, "error": "User not found"}
            except Exception as e:
                return {"success": False, "error": str(e)}


class GetProjectTool(BaseTool):
    """Tool to retrieve project information."""
    name = "get_project"
    description = "Retrieve project information by ID or query parameters"
    args_schema: Type[BaseModel] = ProjectQuery
    
    def _run(
        self,
        project_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        project_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_project(project_id, workspace_id, status, project_type))
    
    async def _aget_project(
        self,
        project_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        project_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                from backend.db.models import Project as ProjectModel
                
                query = session.query(ProjectModel)
                
                if project_id:
                    project = query.filter(ProjectModel.id == project_id).first()
                else:
                    if workspace_id:
                        query = query.filter(ProjectModel.workspace_id == workspace_id)
                    if status:
                        query = query.filter(ProjectModel.status == status)
                    if project_type:
                        query = query.filter(ProjectModel.project_type == project_type)
                    
                    projects = query.limit(10).all()
                    return {
                        "success": True,
                        "projects": [
                            {
                                "id": str(p.id),
                                "name": p.name,
                                "status": p.status,
                                "project_type": p.project_type,
                                "created_at": p.created_at.isoformat() if p.created_at else None,
                            }
                            for p in projects
                        ]
                    }
                
                if project:
                    return {
                        "success": True,
                        "project": {
                            "id": str(project.id),
                            "name": project.name,
                            "status": project.status,
                            "project_type": project.project_type,
                            "settings": project.settings,
                            "created_at": project.created_at.isoformat() if project.created_at else None,
                        }
                    }
                else:
                    return {"success": False, "error": "Project not found"}
            except Exception as e:
                return {"success": False, "error": str(e)}


class GetDecisionsTool(BaseTool):
    """Tool to retrieve decisions."""
    name = "get_decisions"
    description = "Retrieve decisions for a project with optional filtering"
    args_schema: Type[BaseModel] = DecisionQuery
    
    def _run(
        self,
        decision_id: Optional[str] = None,
        project_id: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_decisions(decision_id, project_id, category, status))
    
    async def _aget_decisions(
        self,
        decision_id: Optional[str] = None,
        project_id: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                query = session.query(Decision)
                
                if decision_id:
                    decision = query.filter(Decision.id == decision_id).first()
                    if decision:
                        return {
                            "success": True,
                            "decision": {
                                "id": str(decision.id),
                                "question_text": decision.question_text,
                                "answer_text": decision.answer_text,
                                "category": decision.category,
                                "status": decision.status,
                                "dependencies": decision.dependencies,
                                "created_at": decision.created_at.isoformat() if decision.created_at else None,
                            }
                        }
                    else:
                        return {"success": False, "error": "Decision not found"}
                else:
                    if project_id:
                        query = query.filter(Decision.project_id == project_id)
                    if category:
                        query = query.filter(Decision.category == category)
                    if status:
                        query = query.filter(Decision.status == status)
                    
                    decisions = query.limit(50).all()
                    return {
                        "success": True,
                        "decisions": [
                            {
                                "id": str(d.id),
                                "question_text": d.question_text,
                                "answer_text": d.answer_text,
                                "category": d.category,
                                "status": d.status,
                                "dependencies": d.dependencies,
                            }
                            for d in decisions
                        ]
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}


class CreateDecisionTool(BaseTool):
    """Tool to create a new decision."""
    name = "create_decision"
    description = "Create a new decision for a project"
    args_schema: Type[BaseModel] = CreateDecisionInput
    
    def _run(
        self,
        project_id: str,
        question_text: str,
        answer_text: str,
        category: str,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_create_decision(
            project_id, question_text, answer_text, category,
            dependencies or [], metadata or {}
        ))
    
    async def _aget_create_decision(
        self,
        project_id: str,
        question_text: str,
        answer_text: str,
        category: str,
        dependencies: List[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                decision = Decision(
                    id=uuid4(),
                    project_id=project_id,
                    question_text=question_text,
                    answer_text=answer_text,
                    category=category,
                    dependencies=dependencies,
                    metadata=metadata,
                    status="active",
                )
                session.add(decision)
                await session.commit()
                
                return {
                    "success": True,
                    "decision_id": str(decision.id),
                    "message": "Decision created successfully"
                }
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}


class GetArtifactsTool(BaseTool):
    """Tool to retrieve artifacts."""
    name = "get_artifacts"
    description = "Retrieve artifacts for a project with optional filtering"
    args_schema: Type[BaseModel] = ArtifactQuery
    
    def _run(
        self,
        artifact_id: Optional[str] = None,
        project_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_artifacts(artifact_id, project_id, artifact_type, format))
    
    async def _aget_artifacts(
        self,
        artifact_id: Optional[str] = None,
        project_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                query = session.query(Artifact)
                
                if artifact_id:
                    artifact = query.filter(Artifact.id == artifact_id).first()
                    if artifact:
                        return {
                            "success": True,
                            "artifact": {
                                "id": str(artifact.id),
                                "project_id": str(artifact.project_id),
                                "artifact_type": artifact.artifact_type,
                                "format": artifact.format,
                                "status": artifact.status,
                                "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                            }
                        }
                    else:
                        return {"success": False, "error": "Artifact not found"}
                else:
                    if project_id:
                        query = query.filter(Artifact.project_id == project_id)
                    if artifact_type:
                        query = query.filter(Artifact.artifact_type == artifact_type)
                    if format:
                        query = query.filter(Artifact.format == format)
                    
                    artifacts = query.limit(20).all()
                    return {
                        "success": True,
                        "artifacts": [
                            {
                                "id": str(a.id),
                                "artifact_type": a.artifact_type,
                                "format": a.format,
                                "status": a.status,
                            }
                            for a in artifacts
                        ]
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}


class CreateArtifactTool(BaseTool):
    """Tool to create a new artifact."""
    name = "create_artifact"
    description = "Create a new artifact for a project"
    args_schema: Type[BaseModel] = CreateArtifactInput
    
    def _run(
        self,
        project_id: str,
        artifact_type: str,
        format: str,
        content: str,
        based_on_decisions: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_create_artifact(
            project_id, artifact_type, format, content,
            based_on_decisions or [], metadata or {}
        ))
    
    async def _aget_create_artifact(
        self,
        project_id: str,
        artifact_type: str,
        format: str,
        content: str,
        based_on_decisions: List[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                artifact = Artifact(
                    id=uuid4(),
                    project_id=project_id,
                    artifact_type=artifact_type,
                    format=format,
                    content=content,
                    based_on_decisions=based_on_decisions,
                    metadata=metadata,
                    status="generated",
                )
                session.add(artifact)
                await session.commit()
                
                return {
                    "success": True,
                    "artifact_id": str(artifact.id),
                    "message": "Artifact created successfully"
                }
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}


class GetBranchesTool(BaseTool):
    """Tool to retrieve branches."""
    name = "get_branches"
    description = "Retrieve branches for a project"
    args_schema: Type[BaseModel] = BranchQuery
    
    def _run(
        self,
        branch_id: Optional[str] = None,
        project_id: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_branches(branch_id, project_id, parent_branch_id))
    
    async def _aget_branches(
        self,
        branch_id: Optional[str] = None,
        project_id: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                query = session.query(Branch)
                
                if branch_id:
                    branch = query.filter(Branch.id == branch_id).first()
                    if branch:
                        return {
                            "success": True,
                            "branch": {
                                "id": str(branch.id),
                                "name": branch.name,
                                "project_id": str(branch.project_id),
                                "parent_branch_id": str(branch.parent_branch_id) if branch.parent_branch_id else None,
                                "status": branch.status,
                                "created_at": branch.created_at.isoformat() if branch.created_at else None,
                            }
                        }
                    else:
                        return {"success": False, "error": "Branch not found"}
                else:
                    if project_id:
                        query = query.filter(Branch.project_id == project_id)
                    if parent_branch_id:
                        query = query.filter(Branch.parent_branch_id == parent_branch_id)
                    
                    branches = query.limit(20).all()
                    return {
                        "success": True,
                        "branches": [
                            {
                                "id": str(b.id),
                                "name": b.name,
                                "status": b.status,
                                "parent_branch_id": str(b.parent_branch_id) if b.parent_branch_id else None,
                            }
                            for b in branches
                        ]
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}


class CreateBranchTool(BaseTool):
    """Tool to create a new branch."""
    name = "create_branch"
    description = "Create a new branch for a project"
    args_schema: Type[BaseModel] = CreateBranchInput
    
    def _run(
        self,
        project_id: str,
        name: str,
        description: Optional[str] = None,
        parent_branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_create_branch(
            project_id, name, description, parent_branch_id
        ))
    
    async def _aget_create_branch(
        self,
        project_id: str,
        name: str,
        description: Optional[str],
        parent_branch_id: Optional[str],
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                branch = Branch(
                    id=uuid4(),
                    project_id=project_id,
                    name=name,
                    description=description,
                    parent_branch_id=parent_branch_id,
                    status="active",
                )
                session.add(branch)
                await session.commit()
                
                return {
                    "success": True,
                    "branch_id": str(branch.id),
                    "message": "Branch created successfully"
                }
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}


class AddCommentTool(BaseTool):
    """Tool to add a comment to an artifact."""
    name = "add_comment"
    description = "Add a comment to an artifact"
    args_schema: Type[BaseModel] = AddCommentInput
    
    def _run(
        self,
        artifact_id: str,
        content: str,
        parent_comment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_add_comment(artifact_id, content, parent_comment_id))
    
    async def _aget_add_comment(
        self,
        artifact_id: str,
        content: str,
        parent_comment_id: Optional[str],
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                comment = Comment(
                    id=uuid4(),
                    artifact_id=artifact_id,
                    user_id=None,  # Will be set from context
                    content=content,
                    parent_comment_id=parent_comment_id,
                    status="active",
                )
                session.add(comment)
                await session.commit()
                
                return {
                    "success": True,
                    "comment_id": str(comment.id),
                    "message": "Comment added successfully"
                }
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}


class UpdateProjectTool(BaseTool):
    """Tool to update a project."""
    name = "update_project"
    description = "Update project information"
    args_schema: Type[BaseModel] = UpdateProjectInput
    
    def _run(
        self,
        project_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        import asyncio
        return asyncio.run(self._aget_update_project(project_id, name, status, settings))
    
    async def _aget_update_project(
        self,
        project_id: str,
        name: Optional[str],
        status: Optional[str],
        settings: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Async implementation."""
        async for session in get_db_session():
            try:
                from backend.db.models import Project as ProjectModel
                
                project = session.query(ProjectModel).filter(
                    ProjectModel.id == project_id
                ).first()
                
                if not project:
                    return {"success": False, "error": "Project not found"}
                
                if name:
                    project.name = name
                if status:
                    project.status = status
                if settings:
                    project.settings = settings
                
                await session.commit()
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "message": "Project updated successfully"
                }
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}


# ==================== ToolNode Factory ====================


class DatabaseToolNode:
    """Factory for creating database tool nodes."""
    
    @staticmethod
    def get_tools() -> List[BaseTool]:
        """Get all database tools."""
        return [
            GetUserTool(),
            GetProjectTool(),
            GetDecisionsTool(),
            CreateDecisionTool(),
            GetArtifactsTool(),
            CreateArtifactTool(),
            GetBranchesTool(),
            CreateBranchTool(),
            AddCommentTool(),
            UpdateProjectTool(),
        ]
    
    @staticmethod
    def get_tool_by_name(name: str) -> Optional[BaseTool]:
        """Get a specific tool by name."""
        tools = DatabaseToolNode.get_tools()
        for tool in tools:
            if tool.name == name:
                return tool
        return None


# ==================== Exports ====================


__all__ = [
    "DatabaseToolNode",
    "GetUserTool",
    "GetProjectTool",
    "GetDecisionsTool",
    "CreateDecisionTool",
    "GetArtifactsTool",
    "CreateArtifactTool",
    "GetBranchesTool",
    "CreateBranchTool",
    "AddCommentTool",
    "UpdateProjectTool",
]
