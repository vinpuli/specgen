"""
Codebase Analysis service for brownfield project analysis.

This module provides:
- Codebase analysis triggering and tracking
- Impact analysis for proposed changes
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.codebase import CodebaseAnalysis, ImpactAnalysis, AnalysisStatus, RiskLevel
from backend.db.models.project import Project

logger = logging.getLogger(__name__)


class CodebaseAnalysisServiceError(Exception):
    """Base exception for codebase analysis service errors."""
    pass


class CodebaseAnalysisNotFoundError(CodebaseAnalysisServiceError):
    """Raised when analysis is not found."""
    pass


class CodebaseAnalysisService:
    """
    Service for managing codebase analysis.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize codebase analysis service.

        Args:
            session: Async database session.
        """
        self.session = session

    # ======================
    # Analysis Management
    # ======================

    async def create_analysis(
        self,
        project_id: str,
        repository_url: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> CodebaseAnalysis:
        """
        Create a new codebase analysis.

        Args:
            project_id: Project ID.
            repository_url: Optional repository URL.
            branch_name: Optional branch name.

        Returns:
            Created CodebaseAnalysis.
        """
        analysis = CodebaseAnalysis(
            project_id=project_id,
            status=AnalysisStatus.PENDING,
            repository_url=repository_url,
            branch_name=branch_name,
        )

        self.session.add(analysis)
        await self.session.commit()
        await self.session.refresh(analysis)

        logger.info(f"Codebase analysis created: {analysis.id}")
        return analysis

    async def get_analysis_by_id(
        self,
        analysis_id: str,
    ) -> CodebaseAnalysis:
        """
        Get analysis by ID.

        Args:
            analysis_id: Analysis ID.

        Returns:
            CodebaseAnalysis.

        Raises:
            CodebaseAnalysisNotFoundError: If analysis not found.
        """
        result = await self.session.execute(
            select(CodebaseAnalysis)
            .options(selectinload(CodebaseAnalysis.project))
            .where(CodebaseAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()

        if not analysis:
            raise CodebaseAnalysisNotFoundError(f"Analysis not found: {analysis_id}")

        return analysis

    async def start_analysis(
        self,
        analysis_id: str,
        commit_sha: Optional[str] = None,
    ) -> CodebaseAnalysis:
        """
        Mark analysis as in progress.

        Args:
            analysis_id: Analysis ID.
            commit_sha: Optional commit SHA.

        Returns:
            Updated CodebaseAnalysis.
        """
        analysis = await self.get_analysis_by_id(analysis_id)

        analysis.status = AnalysisStatus.IN_PROGRESS
        analysis.commit_sha = commit_sha

        await self.session.commit()
        await self.session.refresh(analysis)

        logger.info(f"Codebase analysis started: {analysis_id}")
        return analysis

    async def complete_analysis(
        self,
        analysis_id: str,
        languages: list,
        language_stats: dict,
        total_loc: int,
        file_count: int,
        architecture_summary: Optional[str] = None,
        component_inventory: Optional[list] = None,
        dependency_graph: Optional[dict] = None,
        detected_patterns: Optional[list] = None,
        file_metrics: Optional[list] = None,
        findings: Optional[list] = None,
    ) -> CodebaseAnalysis:
        """
        Mark analysis as completed with results.

        Args:
            analysis_id: Analysis ID.
            languages: Detected languages.
            language_stats: Language statistics.
            total_loc: Total lines of code.
            file_count: Number of files.
            architecture_summary: Architecture summary.
            component_inventory: List of components.
            dependency_graph: Dependency graph.
            detected_patterns: Detected patterns.
            file_metrics: Per-file metrics.
            findings: Analysis findings.

        Returns:
            Updated CodebaseAnalysis.
        """
        analysis = await self.get_analysis_by_id(analysis_id)

        analysis.status = AnalysisStatus.COMPLETED
        analysis.languages = languages
        analysis.language_stats = language_stats
        analysis.total_loc = total_loc
        analysis.file_count = file_count
        analysis.architecture_summary = architecture_summary
        analysis.component_inventory = component_inventory or []
        analysis.dependency_graph = dependency_graph or {}
        analysis.detected_patterns = detected_patterns or []
        analysis.file_metrics = file_metrics or []
        analysis.findings = findings or []
        analysis.completed_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(analysis)

        logger.info(f"Codebase analysis completed: {analysis_id}")
        return analysis

    async def fail_analysis(
        self,
        analysis_id: str,
        error_message: str,
    ) -> CodebaseAnalysis:
        """
        Mark analysis as failed.

        Args:
            analysis_id: Analysis ID.
            error_message: Error message.

        Returns:
            Updated CodebaseAnalysis.
        """
        analysis = await self.get_analysis_by_id(analysis_id)

        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = error_message
        analysis.completed_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(analysis)

        logger.error(f"Codebase analysis failed: {analysis_id} - {error_message}")
        return analysis

    async def get_latest_analysis(
        self,
        project_id: str,
    ) -> Optional[CodebaseAnalysis]:
        """
        Get the latest analysis for a Project.

        Args:
            project_id: Project ID.

        Returns:
            Latest CodebaseAnalysis or None.
        """
        result = await self.session.execute(
            select(CodebaseAnalysis)
            .where(CodebaseAnalysis.project_id == project_id)
            .order_by(CodebaseAnalysis.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ======================
    # Impact Analysis
    # ======================

    async def create_impact_analysis(
        self,
        codebase_analysis_id: str,
        project_id: str,
        change_description: str,
    ) -> ImpactAnalysis:
        """
        Create a new impact analysis.

        Args:
            codebase_analysis_id: CodebaseAnalysis ID.
            project_id: Project ID.
            change_description: Description of proposed change.

        Returns:
            Created ImpactAnalysis.
        """
        impact = ImpactAnalysis(
            codebase_analysis_id=codebase_analysis_id,
            project_id=project_id,
            change_description=change_description,
        )

        self.session.add(impact)
        await self.session.commit()
        await self.session.refresh(impact)

        logger.info(f"Impact analysis created: {impact.id}")
        return impact

    async def get_impact_analysis(
        self,
        impact_id: str,
    ) -> ImpactAnalysis:
        """
        Get impact analysis by ID.

        Args:
            impact_id: ImpactAnalysis ID.

        Returns:
            ImpactAnalysis.
        """
        result = await self.session.execute(
            select(ImpactAnalysis)
            .options(selectinload(ImpactAnalysis.codebase_analysis))
            .where(ImpactAnalysis.id == impact_id)
        )
        impact = result.scalar_one_or_none()

        if not impact:
            raise CodebaseAnalysisNotFoundError(f"Impact analysis not found: {impact_id}")

        return impact

    async def update_impact_results(
        self,
        impact_id: str,
        affected_files: list,
        affected_components: list,
        risk_level: str,
        risk_factors: list,
        breaking_changes: list,
        downstream_dependencies: list,
        rollback_procedure: Optional[str] = None,
        change_plan: Optional[list] = None,
    ) -> ImpactAnalysis:
        """
        Update impact analysis with results.

        Args:
            impact_id: ImpactAnalysis ID.
            affected_files: List of affected files.
            affected_components: List of affected components.
            risk_level: Risk level.
            risk_factors: Risk factors.
            breaking_changes: Breaking changes.
            downstream_dependencies: Downstream dependencies.
            rollback_procedure: Rollback procedure.
            change_plan: Step-by-step change plan.

        Returns:
            Updated ImpactAnalysis.
        """
        impact = await self.get_impact_analysis(impact_id)

        impact.affected_files = affected_files
        impact.affected_components = affected_components
        impact.risk_level = RiskLevel(risk_level)
        impact.risk_factors = risk_factors
        impact.breaking_changes = breaking_changes
        impact.downstream_dependencies = downstream_dependencies
        impact.rollback_procedure = rollback_procedure
        impact.change_plan = change_plan or []

        await self.session.commit()
        await self.session.refresh(impact)

        logger.info(f"Impact analysis updated: {impact_id}")
        return impact

    # ======================
    # Response Helpers
    # ======================

    def to_response(self, analysis: CodebaseAnalysis) -> dict:
        """Convert CodebaseAnalysis to response dict."""
        return {
            "id": str(analysis.id),
            "project_id": str(analysis.project_id),
            "status": analysis.status.value if analysis.status else None,
            "repository_url": analysis.repository_url,
            "commit_sha": analysis.commit_sha,
            "branch_name": analysis.branch_name,
            "languages": analysis.languages or [],
            "language_stats": analysis.language_stats or {},
            "total_loc": analysis.total_loc,
            "file_count": analysis.file_count,
            "architecture_summary": analysis.architecture_summary,
            "component_inventory": analysis.component_inventory or [],
            "dependency_graph": analysis.dependency_graph or {},
            "detected_patterns": analysis.detected_patterns or [],
            "findings": analysis.findings or [],
            "created_at": analysis.created_at,
            "completed_at": analysis.completed_at,
            "error_message": analysis.error_message,
        }

    def to_impact_response(self, impact: ImpactAnalysis) -> dict:
        """Convert ImpactAnalysis to response dict."""
        return {
            "id": str(impact.id),
            "codebase_analysis_id": str(impact.codebase_analysis_id),
            "project_id": str(impact.project_id),
            "change_description": impact.change_description,
            "affected_files": impact.affected_files or [],
            "affected_components": impact.affected_components or [],
            "risk_level": impact.risk_level.value if impact.risk_level else None,
            "risk_factors": impact.risk_factors or [],
            "breaking_changes": impact.breaking_changes or [],
            "downstream_dependencies": impact.downstream_dependencies or [],
            "rollback_procedure": impact.rollback_procedure,
            "change_plan": impact.change_plan or [],
            "created_at": impact.created_at,
        }
