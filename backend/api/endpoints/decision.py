"""
Decision API endpoints.

This module provides:
- Decision CRUD operations
- Decision dependency management
- AI-assisted decision generation
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.decision import (
    DecisionCreate,
    DecisionUpdate,
    DecisionResponse,
    DecisionDetail,
    DecisionListResponse,
    DecisionFilter,
    DecisionDependencyCreate,
    DecisionDependencyResponse,
    DecisionDependencyDetail,
    DecisionTemplateCreate,
    DecisionTemplateResponse,
    GenerateDecisionRequest,
    GenerateDecisionResponse,
)
from backend.api.schemas.common import SuccessResponse, ErrorResponse, PaginationParams
from backend.db.connection import get_db
from backend.api.endpoints.auth import CurrentUser
from backend.services.decision_service import (
    DecisionService,
    DecisionServiceError,
    DecisionNotFoundError,
    InsufficientPermissionsError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decisions", tags=["Decisions"])


# ======================
# Decision CRUD
# ======================


@router.post(
    "",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": DecisionResponse, "description": "Decision created"},
        400: {"model": ErrorResponse, "description": "Creation failed"},
    },
    summary="Create decision",
    description="Create a new decision in a branch.",
)
async def create_decision(
    decision_data: DecisionCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DecisionResponse:
    """
    Create a new decision.
    """
    decision_service = DecisionService(session)

    try:
        decision = await decision_service.create_decision(
            branch_id=str(decision_data.branch_id),
            question_text=decision_data.question_text,
            answer_text=decision_data.answer_text,
            category=decision_data.category,
            priority=decision_data.priority,
            status=decision_data.status,
            explanation=decision_data.explanation,
            pros=decision_data.pros,
            cons=decision_data.cons,
            notes=decision_data.notes,
            tags=decision_data.tags,
            created_by=str(current_user.id),
        )
        return decision_service.to_response(decision)

    except DecisionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=DecisionListResponse,
    summary="List decisions",
    description="List decisions with optional filters.",
)
async def list_decisions(
    branch_id: Optional[UUID] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: Optional[CurrentUser] = None,
    session: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
) -> DecisionListResponse:
    """
    List decisions with optional filters.
    """
    decision_service = DecisionService(session)

    decisions, total = await decision_service.list_decisions(
        user_id=str(current_user.id) if current_user else None,
        branch_id=str(branch_id) if branch_id else None,
        category=category,
        decision_status=status,
        priority=priority,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return DecisionListResponse(
        decisions=[decision_service.to_response(d) for d in decisions],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{decision_id}",
    response_model=DecisionDetail,
    responses={
        200: {"model": DecisionDetail, "description": "Decision details"},
        404: {"model": ErrorResponse, "description": "Decision not found"},
    },
    summary="Get decision",
    description="Get decision details with dependencies.",
)
async def get_decision(
    decision_id: UUID,
    current_user: Optional[CurrentUser] = None,
    session: AsyncSession = Depends(get_db),
) -> DecisionDetail:
    """
    Get decision details.
    """
    decision_service = DecisionService(session)

    try:
        decision = await decision_service.get_decision_by_id(
            decision_id=str(decision_id),
            user_id=str(current_user.id) if current_user else None,
        )
        return decision_service.to_detail(decision)

    except DecisionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put(
    "/{decision_id}",
    response_model=DecisionResponse,
    responses={
        200: {"model": DecisionResponse, "description": "Decision updated"},
        404: {"model": ErrorResponse, "description": "Decision not found"},
    },
    summary="Update decision",
    description="Update decision details.",
)
async def update_decision(
    decision_id: UUID,
    update: DecisionUpdate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DecisionResponse:
    """
    Update decision details.
    """
    decision_service = DecisionService(session)

    try:
        decision = await decision_service.update_decision(
            decision_id=str(decision_id),
            user_id=str(current_user.id),
            question_text=update.question_text,
            answer_text=update.answer_text,
            category=update.category,
            priority=update.priority,
            status=update.status,
            explanation=update.explanation,
            pros=update.pros,
            cons=update.cons,
            notes=update.notes,
            tags=update.tags,
        )
        return decision_service.to_response(decision)

    except DecisionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.delete(
    "/{decision_id}",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse, "description": "Decision deleted"},
        404: {"model": ErrorResponse, "description": "Decision not found"},
    },
    summary="Delete decision",
    description="Delete a decision.",
)
async def delete_decision(
    decision_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """
    Delete a decision.
    """
    decision_service = DecisionService(session)

    try:
        await decision_service.delete_decision(
            decision_id=str(decision_id),
            user_id=str(current_user.id),
        )
        return SuccessResponse(success=True, message="Decision deleted successfully")

    except DecisionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ======================
# Decision Dependencies
# ======================


@router.post(
    "/{decision_id}/dependencies",
    response_model=DecisionDependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add dependency",
    description="Add a dependency between decisions.",
)
async def add_dependency(
    decision_id: UUID,
    dependency_data: DecisionDependencyCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DecisionDependencyResponse:
    """
    Add a dependency to a decision.
    """
    decision_service = DecisionService(session)

    try:
        dependency = await decision_service.add_dependency(
            decision_id=str(decision_id),
            depends_on_decision_id=str(dependency_data.depends_on_decision_id),
            dependency_type=dependency_data.dependency_type,
        )
        return decision_service.to_dependency_response(dependency)

    except DecisionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{decision_id}/dependencies",
    response_model=list[DecisionDependencyDetail],
    summary="List dependencies",
    description="List all dependencies of a decision.",
)
async def list_dependencies(
    decision_id: UUID,
    current_user: Optional[CurrentUser] = None,
    session: AsyncSession = Depends(get_db),
) -> list[DecisionDependencyDetail]:
    """
    List all dependencies of a decision.
    """
    decision_service = DecisionService(session)

    dependencies = await decision_service.list_dependencies(
        decision_id=str(decision_id),
        user_id=str(current_user.id) if current_user else None,
    )

    return [decision_service.to_dependency_detail(d) for d in dependencies]


@router.delete(
    "/{decision_id}/dependencies/{dep_id}",
    response_model=SuccessResponse,
    summary="Remove dependency",
    description="Remove a dependency from a decision.",
)
async def remove_dependency(
    decision_id: UUID,
    dep_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """
    Remove a dependency from a decision.
    """
    decision_service = DecisionService(session)

    try:
        await decision_service.remove_dependency(
            dependency_id=str(dep_id),
            user_id=str(current_user.id),
        )
        return SuccessResponse(success=True, message="Dependency removed successfully")

    except DecisionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ======================
# Decision Templates
# ======================


@router.post(
    "/templates",
    response_model=DecisionTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create template",
    description="Create a decision template.",
)
async def create_template(
    template_data: DecisionTemplateCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DecisionTemplateResponse:
    """
    Create a decision template.
    """
    decision_service = DecisionService(session)

    template = await decision_service.create_template(
        name=template_data.name,
        description=template_data.description,
        category=template_data.category,
        question_template=template_data.question_template,
        default_pros=template_data.default_pros,
        default_cons=template_data.default_cons,
        is_public=template_data.is_public,
        created_by=str(current_user.id),
    )

    return decision_service.to_template_response(template)


@router.get(
    "/templates",
    response_model=list[DecisionTemplateResponse],
    summary="List templates",
    description="List decision templates.",
)
async def list_templates(
    category: Optional[str] = None,
    current_user: Optional[CurrentUser] = None,
    session: AsyncSession = Depends(get_db),
) -> list[DecisionTemplateResponse]:
    """
    List decision templates.
    """
    decision_service = DecisionService(session)

    templates = await decision_service.list_templates(
        category=category,
        user_id=str(current_user.id) if current_user else None,
    )

    return [decision_service.to_template_response(t) for t in templates]


# ======================
# AI-assisted Decision
# ======================


@router.post(
    "/generate",
    response_model=GenerateDecisionResponse,
    summary="Generate decision",
    description="Generate a decision using AI.",
)
async def generate_decision(
    request: GenerateDecisionRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> GenerateDecisionResponse:
    """
    Generate a decision using AI.

    Note: This is a placeholder implementation.
    In production, this would call an AI service.
    """
    decision_service = DecisionService(session)

    try:
        # Placeholder AI generation
        # In production, integrate with LLM API
        return GenerateDecisionResponse(
            question_text=request.question,
            answer_text=f"AI-generated answer for: {request.question}",
            explanation="This is a placeholder AI-generated decision.",
            pros=["Pro 1", "Pro 2"],
            cons=["Con 1", "Con 2"],
            category=request.category if hasattr(request, 'category') else "architecture",
            confidence_score=0.85,
            suggestions=["Consider edge cases", "Review with team"],
        )

    except DecisionServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{decision_id}/improve",
    response_model=GenerateDecisionResponse,
    summary="Improve decision",
    description="Get AI suggestions to improve a decision.",
)
async def improve_decision(
    decision_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> GenerateDecisionResponse:
    """
    Get AI suggestions to improve a decision.

    Note: This is a placeholder implementation.
    """
    decision_service = DecisionService(session)

    try:
        decision = await decision_service.get_decision_by_id(
            decision_id=str(decision_id),
            user_id=str(current_user.id),
        )

        return GenerateDecisionResponse(
            question_text=decision.question_text,
            answer_text=decision.answer_text,
            explanation=f"Improved explanation based on: {decision.explanation}",
            pros=decision.pros or [],
            cons=decision.cons or [],
            category=decision.category,
            confidence_score=0.92,
            suggestions=["Add more context", "Consider alternatives"],
        )

    except DecisionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ======================
# Decision Search
# ======================


@router.get(
    "/search",
    response_model=DecisionListResponse,
    summary="Search decisions",
    description="Search decisions by query.",
)
async def search_decisions(
    q: Optional[str] = None,
    branch_id: Optional[UUID] = None,
    category: Optional[str] = None,
    current_user: Optional[CurrentUser] = None,
    session: AsyncSession = Depends(get_db),
    pagination: PaginationParams = Depends(),
) -> DecisionListResponse:
    """
    Search decisions by query.
    """
    decision_service = DecisionService(session)

    decisions, total = await decision_service.search_decisions(
        query=q,
        branch_id=str(branch_id) if branch_id else None,
        category=category,
        user_id=str(current_user.id) if current_user else None,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return DecisionListResponse(
        decisions=[decision_service.to_response(d) for d in decisions],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
