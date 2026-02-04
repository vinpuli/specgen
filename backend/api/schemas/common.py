"""
Base Pydantic configurations and common schemas.

This module provides:
- Custom base model with shared configurations
- Pagination and search parameters
- Generic response wrappers
- Health check response
"""

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """
    Base schema with shared configurations.

    Attributes:
        model_config: Pydantic model configuration.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""

    created_at: datetime = Field(
        ..., description="Record creation timestamp"
    )
    updated_at: datetime = Field(
        ..., description="Record last update timestamp"
    )


class PaginationParams(BaseModel):
    """
    Pagination parameters for list endpoints.

    Attributes:
        page: Page number (1-indexed).
        page_size: Number of items per page.
    """

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class SearchParams(BaseModel):
    """Search and filter parameters."""

    query: Optional[str] = Field(default=None, description="Search query")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")
    filters: Optional[dict[str, Any]] = None


T = TypeVar("T")


class PaginationResponse(BaseModel, Generic[T]):
    """
    Generic pagination response wrapper.

    Attributes:
        items: List of items in the current page.
        total: Total number of items.
        page: Current page number.
        page_size: Items per page.
        total_pages: Total number of pages.
    """

    items: List[T]
    total: int = Field(..., description="Total item count")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")

    @property
    def total_pages(self) -> int:
        """Calculate total pages."""
        return (self.total + self.page_size - 1) // self.page_size


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    success: bool = False
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: Optional[str] = None
    database: str = Field(..., description="Database health status")
    cache: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UUIDMixin(BaseModel):
    """Mixin for entities with UUID primary key."""

    id: UUID = Field(..., description="Unique identifier")


class IsActiveMixin(BaseModel):
    """Mixin for entities with active status."""

    is_active: bool = Field(True, description="Whether the entity is active")


class SoftDeleteMixin(BaseModel):
    """Mixin for soft delete functionality."""

    deleted_at: Optional[datetime] = None
    deleted_by: Optional[UUID] = None
