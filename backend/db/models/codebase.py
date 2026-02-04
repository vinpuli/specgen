"""
CodebaseAnalysis and ImpactAnalysis models for brownfield projects.

These models handle:
- Brownfield project code analysis results
- Architecture inference and component inventory
- Change impact analysis
- Risk assessment for modifications
"""

import enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSONB,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.base import Base
from backend.db.meta import metadata


class AnalysisStatus(str, enum.Enum):
    """Status for codebase analysis."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(str, enum.Enum):
    """Risk level for impact analysis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CodebaseAnalysis(Base):
    """
    Codebase analysis model for brownfield projects.

    Attributes:
        id: Unique identifier (UUID primary key)
        project_id: Reference to parent Project
        status: Current analysis status
        repository_url: Analyzed repository URL
        commit_sha: Analyzed commit SHA
        languages: Detected programming languages
        language_stats: Language distribution statistics
        total_loc: Total lines of code
        architecture_summary: LLM-generated architecture summary
        component_inventory: List of detected components
        dependency_graph: Dependency relationships between components
        detected_patterns: Architectural patterns detected
        file_metrics: Per-file code metrics
        findings: Analysis findings and recommendations
        created_at: Record creation timestamp
        completed_at: Timestamp when analysis completed
    """

    __tablename__ = "codebase_analyses"
    __table_args__ = (
        Index("ix_codebase_analyses_project_id", "project_id"),
        Index("ix_codebase_analyses_status", "status"),
        {"schema": "public"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=Text("gen_random_uuid()"),
    )

    # Foreign keys
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        doc="Project ID",
    )

    # Analysis status
    status = Column(
        Enum(AnalysisStatus),
        default=AnalysisStatus.PENDING,
        nullable=False,
        doc="Current analysis status",
    )

    # Repository info
    repository_url = Column(
        String(512),
        nullable=True,
        doc="Analyzed repository URL",
    )
    commit_sha = Column(
        String(40),
        nullable=True,
        doc="Analyzed commit SHA",
    )
    branch_name = Column(
        String(100),
        nullable=True,
        doc="Analyzed branch name",
    )

    # Code statistics
    languages = Column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
        doc="Detected programming languages",
    )
    language_stats = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Language distribution statistics",
    )
    total_loc = Column(
        Integer,
        nullable=True,
        doc="Total lines of code",
    )
    file_count = Column(
        Integer,
        nullable=True,
        doc="Total number of files",
    )

    # Architecture analysis
    architecture_summary = Column(
        Text,
        nullable=True,
        doc="LLM-generated architecture summary",
    )
    component_inventory = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="List of detected components",
    )
    dependency_graph = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Dependency relationships between components",
    )
    detected_patterns = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Architectural patterns detected",
    )

    # Detailed metrics
    file_metrics = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Per-file code metrics",
    )
    findings = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Analysis findings and recommendations",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        server_default="NOW()",
        doc="Record creation timestamp",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when analysis completed",
    )
    error_message = Column(
        Text,
        nullable=True,
        doc="Error message if analysis failed",
    )

    # Relationships
    project = relationship(
        "Project",
        back_populates="codebase_analyses",
    )
    impact_analyses = relationship(
        "ImpactAnalysis",
        back_populates="codebase_analysis",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CodebaseAnalysis(id={self.id}, project_id={self.project_id}, status={self.status})>"


class ImpactAnalysis(Base):
    """
    Impact analysis model for change impact tracking.

    Attributes:
        id: Unique identifier (UUID primary key)
        codebase_analysis_id: Reference to CodebaseAnalysis
        project_id: Reference to parent Project
        change_description: Description of the proposed change
        affected_files: List of files affected by the change
        risk_level: Overall risk level
        risk_factors: Contributing risk factors
        breaking_changes: Breaking changes detected
        downstream_dependencies: Components affected by the change
        test_impact: Impact on existing tests
        rollback_procedure: Procedure for rollback if needed
        created_at: Record creation timestamp
    """

    __tablename__ = "impact_analyses"
    __table_args__ = (
        Index("ix_impact_analyses_project_id", "project_id"),
        Index("ix_impact_analyses_risk_level", "risk_level"),
        {"schema": "public"},
    )

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=Text("gen_random_uuid()"),
    )

    # Foreign keys
    codebase_analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("codebase_analyses.id", ondelete="CASCADE"),
        nullable=False,
        doc="Codebase analysis ID",
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        doc="Project ID",
    )

    # Change description
    change_description = Column(
        Text,
        nullable=False,
        doc="Description of the proposed change",
    )

    # Impact analysis
    affected_files = Column(
        ARRAY(String(512)),
        default=list,
        nullable=False,
        doc="List of files affected by the change",
    )
    affected_components = Column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
        doc="Components affected by the change",
    )
    risk_level = Column(
        Enum(RiskLevel),
        default=RiskLevel.MEDIUM,
        nullable=False,
        doc="Overall risk level",
    )
    risk_factors = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Contributing risk factors",
    )

    # Breaking changes
    breaking_changes = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Breaking changes detected",
    )
    api_changes = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="API changes detected",
    )
    schema_changes = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Database schema changes",
    )

    # Dependencies
    downstream_dependencies = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Components affected by the change",
    )
    upstream_dependencies = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Dependencies that affect this change",
    )

    # Testing
    test_impact = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Impact on existing tests",
    )
    new_tests_needed = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="New tests that should be written",
    )

    # Rollback
    rollback_procedure = Column(
        Text,
        nullable=True,
        doc="Procedure for rollback if needed",
    )
    rollback_risk = Column(
        Enum(RiskLevel),
        nullable=True,
        doc="Risk level of rollback",
    )

    # Change plan
    change_plan = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Step-by-step change procedure",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        server_default="NOW()",
        doc="Record creation timestamp",
    )

    # Relationships
    codebase_analysis = relationship(
        "CodebaseAnalysis",
        back_populates="impact_analyses",
    )
    project = relationship("Project")

    def __repr__(self) -> str:
        return f"<ImpactAnalysis(id={self.id}, project_id={self.project_id}, risk_level={self.risk_level})>"


# Import for relationship setup (avoid circular import)
from backend.db.models.project import Project  # noqa: E402
