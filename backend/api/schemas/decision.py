"""
Decision and DecisionDependency Pydantic schemas.

This module provides:
- Decision creation, update, and response schemas
- Decision dependency schemas
- Decision category and status enums
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin


# ======================
# Enums
# ======================


class DecisionCategory(str, Enum):
    """Decision category enum."""

    ARCHITECTURE = "architecture"
    DATA = "data"
    SECURITY = "security"
    PERFORMANCE = "performance"
    UX = "ux"
    PROCESS = "process"
    INTEGRATION = "integration"
    COMPLIANCE = "compliance"


class DecisionStatus(str, Enum):
    """Decision status enum."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class DecisionPriority(str, Enum):
    """Decision priority enum."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ======================
# Decision Schemas
# ======================


class DecisionCreate(BaseSchema):
    """Decision creation request schema."""

    branch_id: UUID = Field(..., description="Branch ID")
    question_text: str = Field(..., min_length=10, description="Question being decided")
    answer_text: str = Field(..., min_length=1, description="Answer/decision made")
    category: str = Field(..., description="Decision category")
    priority: str = Field(default="medium", description="Decision priority")
    status: str = Field(default="accepted", description="Decision status")
    explanation: Optional[str] = Field(default=None, description="Detailed explanation")
    pros: List[str] = Field(default_factory=list, description="Pros of this decision")
    cons: List[str] = Field(default_factory=list, description="Cons of this decision")
    notes: Optional[str] = Field(default=None, description="Additional notes")
    tags: List[str] = Field(default_factory=list, description="Tags for organization")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate decision category."""
        if v not in [c.value for c in DecisionCategory]:
            raise ValueError(f"Invalid category: {v}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate decision priority."""
        if v not in [p.value for p in DecisionPriority]:
            raise ValueError(f"Invalid priority: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate decision status."""
        if v not in [s.value for s in DecisionStatus]:
            raise ValueError(f"Invalid status: {v}")
        return v


class DecisionUpdate(BaseSchema):
    """Decision update request schema."""

    question_text: Optional[str] = Field(default=None, min_length=10)
    answer_text: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    explanation: Optional[str] = None
    pros: Optional[List[str]] = None
    cons: Optional[List[str]] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class DecisionResponse(UUIDMixin, TimestampSchema):
    """Decision response schema."""

    branch_id: UUID
    question_text: str
    answer_text: str
    category: str
    priority: str
    status: str
    explanation: Optional[str] = None
    pros: List[str]
    cons: List[str]
    notes: Optional[str] = None
    tags: List[str]
    created_by: Optional[UUID] = None
    parent_decision_id: Optional[UUID] = None
    dependent_decisions: Optional[int] = None


class DecisionDetail(DecisionResponse):
    """Decision detail response with full relationships."""

    based_on_decisions: Optional[List["DecisionResponse"]] = None
    dependent_decisions_list: Optional[List["DecisionResponse"]] = None


class DecisionListResponse(BaseModel):
    """Decision list response with pagination."""

    decisions: List[DecisionResponse]
    total: int
    page: int
    page_size: int


class DecisionFilter(BaseModel):
    """Decision filter parameters."""

    branch_id: Optional[UUID] = None
    category: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    created_by: Optional[UUID] = None
    search: Optional[str] = None


# ======================
# Decision Dependency Schemas
# ======================


class DecisionDependencyCreate(BaseSchema):
    """Decision dependency creation request schema."""

    decision_id: UUID = Field(..., description="Decision that has the dependency")
    depends_on_decision_id: UUID = Field(..., description="Decision this depends on")
    dependency_type: str = Field(
        default="related", description="Type of dependency (related, blocks, required_by)"
    )

    @field_validator("dependency_type")
    @classmethod
    def validate_dependency_type(cls, v: str) -> str:
        """Validate dependency type."""
        valid_types = ["related", "blocks", "required_by", "supersedes", "implements"]
        if v not in valid_types:
            raise ValueError(f"Invalid dependency type: {v}")
        return v


class DecisionDependencyResponse(BaseSchema):
    """Decision dependency response schema."""

    id: UUID
    decision_id: UUID
    depends_on_decision_id: UUID
    dependency_type: str
    created_at: datetime


class DecisionDependencyDetail(BaseSchema):
    """Decision dependency with full decision info."""

    dependency: DecisionDependencyResponse
    depends_on_decision: DecisionResponse


# ======================
# Decision Templates
# ======================


class DecisionTemplateCreate(BaseSchema):
    """Decision template creation request schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str
    question_template: str = Field(..., description="Template question with placeholders")
    default_pros: List[str] = Field(default_factory=list)
    default_cons: List[str] = Field(default_factory=list)
    is_public: bool = Field(default=False)


class DecisionTemplateResponse(UUIDMixin, TimestampSchema):
    """Decision template response schema."""

    name: str
    description: Optional[str] = None
    category: str
    question_template: str
    default_pros: List[str]
    default_cons: List[str]
    is_public: bool
    usage_count: Optional[int] = None


# ======================
# AI-assisted Decision
# ======================


class GenerateDecisionRequest(BaseSchema):
    """Request to generate a decision using AI."""

    context: str = Field(..., description="Context for the decision")
    question: str = Field(..., min_length=10, description="Question to decide")
    existing_decisions: Optional[List[UUID]] = Field(
        default=None, description="IDs of related decisions"
    )
    branch_id: UUID = Field(..., description="Branch ID for the decision")


class GenerateDecisionResponse(BaseSchema):
    """Response with AI-generated decision."""

    question_text: str
    answer_text: str
    explanation: Optional[str] = None
    pros: List[str]
    cons: List[str]
    category: str
    confidence_score: float
    suggestions: List[str] = Field(default_factory=list)


# Update forward references
DecisionDetail.model_rebuild()
