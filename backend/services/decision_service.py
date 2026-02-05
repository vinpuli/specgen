"""
Decision service for decision and dependency management.

This module provides:
- Decision CRUD operations
- Dependency management
- Template management
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.decision import Decision, DecisionDependency, DecisionTemplate, DecisionStatus, DecisionCategory
from backend.db.models.project import Branch
from backend.services.project_service import ProjectService, BranchNotFoundError

logger = logging.getLogger(__name__)


class DecisionServiceError(Exception):
    """Base exception for decision service errors."""

    pass


class DecisionNotFoundError(DecisionServiceError):
    """Raised when decision is not found."""

    pass


class BranchNotInProjectError(DecisionServiceError):
    """Raised when branch doesn't belong to project."""

    pass


class DecisionService:
    """
    Decision service for managing decisions.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize decision service.

        Args:
            session: Async database session.
        """
        self.session = session
        self.project_service = ProjectService(session)

    # ======================
    # Decision CRUD
    # ======================

    async def create_decision(
        self,
        branch_id: str,
        question_text: str,
        answer_text: str,
        category: str,
        priority: str = "medium",
        status: str = "accepted",
        explanation: Optional[str] = None,
        pros: Optional[List[str]] = None,
        cons: Optional[List[str]] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None,
    ) -> Decision:
        """
        Create a new decision.

        Args:
            branch_id: Branch ID.
            question_text: The question being decided.
            answer_text: The answer/decision made.
            category: Decision category.
            priority: Decision priority.
            status: Decision status.
            explanation: Detailed explanation.
            pros: Pros of this decision.
            cons: Cons of this decision.
            notes: Additional notes.
            tags: Tags for organization.
            created_by: User ID.

        Returns:
            Created Decision.
        """
        # Verify branch exists
        branch = await self._get_branch(branch_id)

        decision = Decision(
            branch_id=branch_id,
            question_text=question_text,
            answer_text=answer_text,
            category=category,
            priority=priority,
            status=status,
            explanation=explanation,
            pros=pros or [],
            cons=cons or [],
            notes=notes,
            tags=tags or [],
            created_by=created_by,
        )

        self.session.add(decision)
        await self.session.commit()
        await self.session.refresh(decision)

        logger.info(f"Decision created: {decision.id} in branch {branch_id}")
        return decision

    async def get_decision_by_id(
        self,
        decision_id: str,
        user_id: Optional[str] = None,
    ) -> Decision:
        """
        Get decision by ID.

        Args:
            decision_id: Decision ID.
            user_id: Optional user ID for permission check.

        Returns:
            Decision.

        Raises:
            DecisionNotFoundError: If decision not found.
        """
        result = await self.session.execute(
            select(Decision)
            .options(
                selectinload(Decision.branch),
                selectinload(Decision.dependencies),
                selectinload(Decision.dependents),
            )
            .where(Decision.id == decision_id)
            .where(Decision.is_active == True)  # type: ignore
        )
        decision = result.scalar_one_or_none()

        if not decision:
            raise DecisionNotFoundError(f"Decision not found: {decision_id}")

        return decision

    async def list_decisions(
        self,
        user_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        category: Optional[str] = None,
        decision_status: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Decision], int]:
        """
        List decisions with optional filters.

        Args:
            user_id: Optional user ID filter.
            branch_id: Optional branch ID filter.
            category: Optional category filter.
            decision_status: Optional status filter.
            priority: Optional priority filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (decisions, total_count).
        """
        query = (
            select(Decision)
            .options(selectinload(Decision.branch))
            .where(Decision.is_active == True)  # type: ignore
        )

        if branch_id:
            query = query.where(Decision.branch_id == branch_id)
        if category:
            query = query.where(Decision.category == category)
        if decision_status:
            query = query.where(Decision.status == decision_status)
        if priority:
            query = query.where(Decision.priority == priority)

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        decisions = list(result.scalars().all())

        # Get total count
        count_query = select(Decision).where(Decision.is_active == True)  # type: ignore
        if branch_id:
            count_query = count_query.where(Decision.branch_id == branch_id)
        if category:
            count_query = count_query.where(Decision.category == category)
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        return decisions, total

    async def update_decision(
        self,
        decision_id: str,
        user_id: str,
        question_text: Optional[str] = None,
        answer_text: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        explanation: Optional[str] = None,
        pros: Optional[List[str]] = None,
        cons: Optional[List[str]] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Decision:
        """
        Update decision details.

        Args:
            decision_id: Decision ID.
            user_id: User making the update.
            Other fields are optional update values.

        Returns:
            Updated Decision.

        Raises:
            DecisionNotFoundError: If decision not found.
        """
        decision = await self.get_decision_by_id(decision_id)

        if question_text:
            decision.question_text = question_text
        if answer_text:
            decision.answer_text = answer_text
        if category:
            decision.category = category
        if priority:
            decision.priority = priority
        if status:
            decision.status = status
        if explanation is not None:
            decision.explanation = explanation
        if pros is not None:
            decision.pros = pros
        if cons is not None:
            decision.cons = cons
        if notes is not None:
            decision.notes = notes
        if tags is not None:
            decision.tags = tags

        await self.session.commit()
        await self.session.refresh(decision)

        logger.info(f"Decision updated: {decision_id}")
        return decision

    async def delete_decision(
        self,
        decision_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete (deactivate) a decision.

        Args:
            decision_id: Decision ID.
            user_id: User making the request.

        Returns:
            True if successful.
        """
        decision = await self.get_decision_by_id(decision_id)

        decision.is_active = False  # type: ignore
        await self.session.commit()

        logger.info(f"Decision deleted: {decision_id}")
        return True

    async def search_decisions(
        self,
        query: str,
        branch_id: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Decision], int]:
        """
        Search decisions by query.

        Args:
            query: Search query.
            branch_id: Optional branch ID filter.
            category: Optional category filter.
            user_id: Optional user ID filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Tuple of (decisions, total_count).
        """
        search_query = (
            select(Decision)
            .options(selectinload(Decision.branch))
            .where(Decision.is_active == True)  # type: ignore
            .where(
                or_(
                    Decision.question_text.ilike(f"%{query}%"),
                    Decision.answer_text.ilike(f"%{query}%"),
                    Decision.explanation.ilike(f"%{query}%"),
                )
            )
        )

        if branch_id:
            search_query = search_query.where(Decision.branch_id == branch_id)
        if category:
            search_query = search_query.where(Decision.category == category)

        search_query = search_query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(search_query)
        decisions = list(result.scalars().all())

        # Get total count
        count_query = (
            select(Decision)
            .where(Decision.is_active == True)  # type: ignore
            .where(
                or_(
                    Decision.question_text.ilike(f"%{query}%"),
                    Decision.answer_text.ilike(f"%{query}%"),
                    Decision.explanation.ilike(f"%{query}%"),
                )
            )
        )
        if branch_id:
            count_query = count_query.where(Decision.branch_id == branch_id)
        if category:
            count_query = count_query.where(Decision.category == category)
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        return decisions, total

    # ======================
    # Dependencies
    # ======================

    async def add_dependency(
        self,
        decision_id: str,
        depends_on_decision_id: str,
        dependency_type: str = "related",
    ) -> DecisionDependency:
        """
        Add a dependency between decisions.

        Args:
            decision_id: Decision that has the dependency.
            depends_on_decision_id: Decision this depends on.
            dependency_type: Type of dependency.

        Returns:
            Created DecisionDependency.

        Raises:
            DecisionServiceError: If dependency already exists.
        """
        # Verify decisions exist
        await self.get_decision_by_id(decision_id)
        await self.get_decision_by_id(depends_on_decision_id)

        # Check for existing dependency
        existing = await self._get_dependency(decision_id, depends_on_decision_id)
        if existing:
            raise DecisionServiceError("Dependency already exists")

        # Verify branch compatibility
        decision = await self.get_decision_by_id(decision_id)
        depends_on = await self.get_decision_by_id(depends_on_decision_id)
        if decision.branch_id != depends_on.branch_id:
            raise DecisionServiceError("Decisions must be in the same branch")

        dependency = DecisionDependency(
            decision_id=decision_id,
            depends_on_decision_id=depends_on_decision_id,
            dependency_type=dependency_type,
        )

        self.session.add(dependency)
        await self.session.commit()
        await self.session.refresh(dependency)

        logger.info(f"Dependency added: {decision_id} -> {depends_on_decision_id}")
        return dependency

    async def list_dependencies(
        self,
        decision_id: str,
        user_id: Optional[str] = None,
    ) -> List[DecisionDependency]:
        """
        List all dependencies of a decision.

        Args:
            decision_id: Decision ID.
            user_id: Optional user ID for permission check.

        Returns:
            List of DecisionDependencies.
        """
        await self.get_decision_by_id(decision_id, user_id)

        result = await self.session.execute(
            select(DecisionDependency)
            .options(
                selectinload(DecisionDependency.decision),
                selectinload(DecisionDependency.depends_on_decision),
            )
            .where(DecisionDependency.decision_id == decision_id)
        )
        return list(result.scalars().all())

    async def remove_dependency(
        self,
        dependency_id: str,
        user_id: str,
    ) -> bool:
        """
        Remove a dependency.

        Args:
            dependency_id: Dependency ID.
            user_id: User making the request.

        Returns:
            True if successful.
        """
        result = await self.session.execute(
            select(DecisionDependency).where(DecisionDependency.id == dependency_id)
        )
        dependency = result.scalar_one_or_none()

        if not dependency:
            raise DecisionServiceError("Dependency not found")

        await self.session.delete(dependency)
        await self.session.commit()

        logger.info(f"Dependency removed: {dependency_id}")
        return True

    async def _get_dependency(
        self,
        decision_id: str,
        depends_on_decision_id: str,
    ) -> Optional[DecisionDependency]:
        """Get dependency if it exists."""
        result = await self.session.execute(
            select(DecisionDependency)
            .where(DecisionDependency.decision_id == decision_id)
            .where(DecisionDependency.depends_on_decision_id == depends_on_decision_id)
        )
        return result.scalar_one_or_none()

    # ======================
    # Templates
    # ======================

    async def create_template(
        self,
        name: str,
        category: str,
        question_template: str,
        description: Optional[str] = None,
        default_pros: Optional[List[str]] = None,
        default_cons: Optional[List[str]] = None,
        is_public: bool = False,
        created_by: Optional[str] = None,
    ) -> DecisionTemplate:
        """
        Create a decision template.

        Args:
            name: Template name.
            category: Template category.
            question_template: Template question with placeholders.
            description: Template description.
            default_pros: Default pros list.
            default_cons: Default cons list.
            is_public: Whether template is public.
            created_by: User ID.

        Returns:
            Created DecisionTemplate.
        """
        template = DecisionTemplate(
            name=name,
            description=description,
            category=category,
            question_template=question_template,
            default_pros=default_pros or [],
            default_cons=default_cons or [],
            is_public=is_public,
            created_by=created_by,
        )

        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)

        logger.info(f"Decision template created: {template.id}")
        return template

    async def list_templates(
        self,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[DecisionTemplate]:
        """
        List decision templates.

        Args:
            category: Optional category filter.
            user_id: Optional user ID for access control.

        Returns:
            List of DecisionTemplates.
        """
        query = (
            select(DecisionTemplate)
            .where(DecisionTemplate.is_active == True)  # type: ignore
        )

        if category:
            query = query.where(DecisionTemplate.category == category)
        elif user_id:
            # Include public templates and user's templates
            query = query.where(
                (DecisionTemplate.is_public == True) | (DecisionTemplate.created_by == user_id)  # type: ignore
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())

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

    # ======================
    # Response Helpers
    # ======================

    def to_response(self, decision: Decision) -> dict:
        """Convert Decision to response dict."""
        return {
            "id": str(decision.id),
            "branch_id": str(decision.branch_id),
            "question_text": decision.question_text,
            "answer_text": decision.answer_text,
            "category": decision.category,
            "priority": decision.priority,
            "status": decision.status,
            "explanation": decision.explanation,
            "pros": decision.pros or [],
            "cons": decision.cons or [],
            "notes": decision.notes,
            "tags": decision.tags or [],
            "created_by": decision.created_by,
            "created_at": decision.created_at,
            "updated_at": decision.updated_at,
        }

    def to_detail(self, decision: Decision) -> dict:
        """Convert Decision to detail response."""
        response = self.to_response(decision)

        # Add dependency counts
        response["based_on_decisions"] = []  # TODO: Populate
        response["dependent_decisions"] = 0  # TODO: Populate

        return response

    def to_dependency_response(self, dependency: DecisionDependency) -> dict:
        """Convert DecisionDependency to response dict."""
        return {
            "id": str(dependency.id),
            "decision_id": str(dependency.decision_id),
            "depends_on_decision_id": str(dependency.depends_on_decision_id),
            "dependency_type": dependency.dependency_type,
            "created_at": dependency.created_at,
        }

    def to_dependency_detail(self, dependency: DecisionDependency) -> dict:
        """Convert DecisionDependency to detail response."""
        response = self.to_dependency_response(dependency)

        if dependency.depends_on_decision:
            response["depends_on_decision"] = self.to_response(
                dependency.depends_on_decision
            )

        return response

    def to_template_response(self, template: DecisionTemplate) -> dict:
        """Convert DecisionTemplate to response dict."""
        return {
            "id": str(template.id),
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "question_template": template.question_template,
            "default_pros": template.default_pros or [],
            "default_cons": template.default_cons or [],
            "is_public": template.is_public,
            "usage_count": template.usage_count,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }
