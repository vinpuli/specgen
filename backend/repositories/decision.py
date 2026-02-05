"""
Decision repository for decision data access operations.

This module implements the repository pattern for Decision and DecisionDependency models,
providing data access methods for specification decision management.
"""

import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.decision import (
    Decision,
    DecisionDependency,
    DecisionCategory,
    DecisionStatus,
    DecisionPriority,
)
from backend.repositories.base import BaseRepository


class DecisionRepository(BaseRepository[Decision]):
    """
    Repository for Decision data access operations.

    Provides methods for:
    - Decision CRUD operations
    - Decision status and priority management
    - Decision dependency queries
    - Semantic search for context retrieval
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the DecisionRepository.

        Args:
            session: The async database session.
        """
        super().__init__(Decision, session)

    async def get_by_project(
        self,
        project_id: uuid.UUID,
        status: Optional[DecisionStatus] = None,
        category: Optional[DecisionCategory] = None,
        branch_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Decision]:
        """
        Get all decisions in a project with optional filters.

        Args:
            project_id: The project ID.
            status: Optional status filter.
            category: Optional category filter.
            branch_id: Optional branch filter.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of decisions.
        """
        query = select(Decision).where(Decision.project_id == project_id)

        if status:
            query = query.where(Decision.status == status)
        if category:
            query = query.where(Decision.category == category)
        if branch_id:
            query = query.where(Decision.branch_id == branch_id)

        query = (
            query.offset(skip)
            .limit(limit)
            .order_by(Decision.priority.desc(), Decision.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pending_decisions(
        self, project_id: uuid.UUID, branch_id: Optional[uuid.UUID] = None
    ) -> List[Decision]:
        """
        Get all pending decisions in a project.

        Args:
            project_id: The project ID.
            branch_id: Optional branch filter.

        Returns:
            List of pending decisions ordered by priority.
        """
        query = (
            select(Decision)
            .where(
                and_(
                    Decision.project_id == project_id,
                    Decision.status.in_(
                        [
                            DecisionStatus.PENDING,
                            DecisionStatus.IN_PROGRESS,
                            DecisionStatus.AWAITING_ANSWER,
                        ]
                    ),
                )
            )
            .options(selectinload(Decision.outgoing_dependencies))
        )

        if branch_id:
            query = query.where(Decision.branch_id == branch_id)

        query = query.order_by(Decision.priority.desc(), Decision.created_at)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_answered_decisions(
        self, project_id: uuid.UUID, branch_id: Optional[uuid.UUID] = None
    ) -> List[Decision]:
        """
        Get all answered decisions in a project.

        Args:
            project_id: The project ID.
            branch_id: Optional branch filter.

        Returns:
            List of answered decisions.
        """
        query = (
            select(Decision)
            .where(
                and_(
                    Decision.project_id == project_id,
                    Decision.status.in_(
                        [DecisionStatus.ANSWERED, DecisionStatus.LOCKED]
                    ),
                )
            )
            .options(selectinload(Decision.outgoing_dependencies))
        )

        if branch_id:
            query = query.where(Decision.branch_id == branch_id)

        query = query.order_by(Decision.answered_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_decision_with_details(
        self, decision_id: uuid.UUID
    ) -> Optional[Decision]:
        """
        Get a decision with all relationships loaded.

        Args:
            decision_id: The decision ID.

        Returns:
            The decision with details.
        """
        query = (
            select(Decision)
            .where(Decision.id == decision_id)
            .options(
                selectinload(Decision.project),
                selectinload(Decision.branch),
                selectinload(Decision.conversation_turns),
                selectinload(Decision.outgoing_dependencies).selectinload(
                    "target_decision"
                ),
                selectinload(Decision.incoming_dependencies).selectinload(
                    "source_decision"
                ),
                selectinload(Decision.based_on_artifacts),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_category(
        self, project_id: uuid.UUID, category: DecisionCategory
    ) -> List[Decision]:
        """
        Get all decisions of a specific category.

        Args:
            project_id: The project ID.
            category: The decision category.

        Returns:
            List of decisions.
        """
        query = (
            select(Decision)
            .where(
                and_(
                    Decision.project_id == project_id,
                    Decision.category == category,
                )
            )
            .order_by(Decision.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_priority(
        self, project_id: uuid.UUID, priority: DecisionPriority
    ) -> List[Decision]:
        """
        Get all decisions of a specific priority.

        Args:
            project_id: The project ID.
            priority: The decision priority.

        Returns:
            List of decisions.
        """
        query = (
            select(Decision)
            .where(
                and_(
                    Decision.project_id == project_id,
                    Decision.priority == priority,
                )
            )
            .order_by(Decision.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_locked_decisions(
        self, project_id: uuid.UUID
    ) -> List[Decision]:
        """
        Get all locked decisions in a project.

        Args:
            project_id: The project ID.

        Returns:
            List of locked decisions.
        """
        query = (
            select(Decision)
            .where(
                and_(
                    Decision.project_id == project_id,
                    Decision.is_locked == True,
                )
            )
            .order_by(Decision.locked_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self, decision_id: uuid.UUID, status: DecisionStatus
    ) -> Optional[Decision]:
        """
        Update a decision's status.

        Args:
            decision_id: The decision ID.
            status: The new status.

        Returns:
            The updated decision if found.
        """
        update_data = {"status": status}
        if status == DecisionStatus.ANSWERED:
            update_data["answered_at"] = datetime.now(timezone.utc)
        return await self.update(decision_id, **update_data)

    async def answer(
        self,
        decision_id: uuid.UUID,
        answer_text: str,
        reasoning: Optional[str] = None,
        answered_by: Optional[uuid.UUID] = None,
        ai_generated: bool = False,
        confidence_score: Optional[int] = None,
    ) -> Optional[Decision]:
        """
        Record an answer for a decision.

        Args:
            decision_id: The decision ID.
            answer_text: The answer text.
            reasoning: Optional reasoning.
            answered_by: The user who answered.
            ai_generated: Whether the answer was AI-generated.
            confidence_score: AI confidence score.

        Returns:
            The updated decision if found.
        """
        return await self.update(
            decision_id,
            answer_text=answer_text,
            reasoning=reasoning,
            answered_by=answered_by,
            ai_generated=ai_generated,
            confidence_score=confidence_score,
            status=DecisionStatus.ANSWERED,
            answered_at=datetime.now(timezone.utc),
        )

    async def lock(
        self,
        decision_id: uuid.UUID,
        locked_by: uuid.UUID,
    ) -> Optional[Decision]:
        """
        Lock a decision to prevent modifications.

        Args:
            decision_id: The decision ID.
            locked_by: The user who locked.

        Returns:
            The locked decision if found.
        """
        return await self.update(
            decision_id,
            is_locked=True,
            locked_by=locked_by,
            locked_at=datetime.now(timezone.utc),
            status=DecisionStatus.LOCKED,
        )

    async def unlock(self, decision_id: uuid.UUID) -> Optional[Decision]:
        """
        Unlock a decision.

        Args:
            decision_id: The decision ID.

        Returns:
            The unlocked decision if found.
        """
        return await self.update(
            decision_id,
            is_locked=False,
            locked_by=None,
            locked_at=None,
        )

    async def get_decision_count_by_status(
        self, project_id: uuid.UUID
    ) -> dict:
        """
        Get the count of decisions by status in a project.

        Args:
            project_id: The project ID.

        Returns:
            Dictionary of status to count.
        """
        counts = {}
        for status in DecisionStatus:
            query = (
                select(func.count())
                .select_from(Decision)
                .where(
                    and_(
                        Decision.project_id == project_id,
                        Decision.status == status,
                    )
                )
            )
            result = await self.session.execute(query)
            counts[status.value] = result.scalar_one() or 0
        return counts

    async def search_decisions(
        self, project_id: uuid.UUID, query: str, limit: int = 50
    ) -> List[Decision]:
        """
        Search decisions by question or answer text.

        Args:
            project_id: The project ID.
            query: The search query.
            limit: Maximum number of results.

        Returns:
            List of matching decisions.
        """
        search_query = (
            select(Decision)
            .where(
                and_(
                    Decision.project_id == project_id,
                    or_(
                        Decision.question_text.ilike(f"%{query}%"),
                        Decision.answer_text.ilike(f"%{query}%"),
                    ),
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(search_query)
        return list(result.scalars().all())

    async def get_dependent_decisions(
        self, decision_id: uuid.UUID
    ) -> List[Decision]:
        """
        Get all decisions that depend on this decision.

        Args:
            decision_id: The decision ID.

        Returns:
            List of dependent decisions.
        """
        query = (
            select(Decision)
            .join(
                DecisionDependency,
                Decision.id == DecisionDependency.source_decision_id,
            )
            .where(DecisionDependency.target_decision_id == decision_id)
            .options(
                selectinload(Decision.outgoing_dependencies).selectinload(
                    "target_decision"
                )
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_prerequisite_decisions(
        self, decision_id: uuid.UUID
    ) -> List[Decision]:
        """
        Get all prerequisite decisions for this decision.

        Args:
            decision_id: The decision ID.

        Returns:
            List of prerequisite decisions.
        """
        query = (
            select(Decision)
            .join(
                DecisionDependency,
                Decision.id == DecisionDependency.target_decision_id,
            )
            .where(
                DecisionDependency.source_decision_id == decision_id
            )
            .options(selectinload(Decision.incoming_dependencies))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class DecisionDependencyRepository(BaseRepository[DecisionDependency]):
    """
    Repository for DecisionDependency data access operations.

    Provides methods for:
    - Dependency CRUD operations
    - Dependency chain queries
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the DecisionDependencyRepository.

        Args:
            session: The async database session.
        """
        super().__init__(DecisionDependency, session)

    async def get_by_source_and_target(
        self,
        source_decision_id: uuid.UUID,
        target_decision_id: uuid.UUID,
    ) -> Optional[DecisionDependency]:
        """
        Get a dependency by source and target decisions.

        Args:
            source_decision_id: The source decision ID.
            target_decision_id: The target decision ID.

        Returns:
            The dependency if found.
        """
        query = select(DecisionDependency).where(
            and_(
                DecisionDependency.source_decision_id == source_decision_id,
                DecisionDependency.target_decision_id == target_decision_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_dependencies_for_decision(
        self, decision_id: uuid.UUID
    ) -> List[DecisionDependency]:
        """
        Get all dependencies where this decision is the source.

        Args:
            decision_id: The decision ID.

        Returns:
            List of outgoing dependencies.
        """
        query = (
            select(DecisionDependency)
            .where(
                DecisionDependency.source_decision_id == decision_id
            )
            .options(selectinload(DecisionDependency.target_decision))
            .order_by(DecisionDependency.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_dependents_for_decision(
        self, decision_id: uuid.UUID
    ) -> List[DecisionDependency]:
        """
        Get all dependencies where this decision is the target.

        Args:
            decision_id: The decision ID.

        Returns:
            List of incoming dependencies.
        """
        query = (
            select(DecisionDependency)
            .where(
                DecisionDependency.target_decision_id == decision_id
            )
            .options(selectinload(DecisionDependency.source_decision))
            .order_by(DecisionDependency.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_dependency(
        self,
        source_decision_id: uuid.UUID,
        target_decision_id: uuid.UUID,
        dependency_type: str = "requires",
        description: Optional[str] = None,
    ) -> DecisionDependency:
        """
        Create a dependency between two decisions.

        Args:
            source_decision_id: The source decision.
            target_decision_id: The target/prerequisite decision.
            dependency_type: The type of dependency.
            description: Optional description.

        Returns:
            The created dependency.
        """
        return await self.create(
            source_decision_id=source_decision_id,
            target_decision_id=target_decision_id,
            dependency_type=dependency_type,
            description=description,
        )

    async def remove_dependency(
        self,
        source_decision_id: uuid.UUID,
        target_decision_id: uuid.UUID,
    ) -> bool:
        """
        Remove a dependency between two decisions.

        Args:
            source_decision_id: The source decision.
            target_decision_id: The target decision.

        Returns:
            True if removed, False if not found.
        """
        dependency = await self.get_by_source_and_target(
            source_decision_id, target_decision_id
        )
        if dependency:
            return await self.delete(dependency.id)
        return False

    async def has_dependency(
        self,
        source_decision_id: uuid.UUID,
        target_decision_id: uuid.UUID,
    ) -> bool:
        """
        Check if a dependency exists between two decisions.

        Args:
            source_decision_id: The source decision.
            target_decision_id: The target decision.

        Returns:
            True if dependency exists.
        """
        dependency = await self.get_by_source_and_target(
            source_decision_id, target_decision_id
        )
        return dependency is not None

    async def get_dependency_graph(
        self, project_id: uuid.UUID
    ) -> List[DecisionDependency]:
        """
        Get all dependencies for decisions in a project.

        Args:
            project_id: The project ID.

        Returns:
            List of all dependencies.
        """
        # This query finds all dependencies where both decisions
        # belong to the specified project
        query = (
            select(DecisionDependency)
            .join(
                Decision,
                Decision.id == DecisionDependency.source_decision_id,
            )
            .where(Decision.project_id == project_id)
            .options(
                selectinload(DecisionDependency.source_decision),
                selectinload(DecisionDependency.target_decision),
            )
            .order_by(DecisionDependency.created_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


# Import for timezone-aware datetime
from datetime import timezone  # noqa: E402
