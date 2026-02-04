"""
Comment and ConversationTurn Pydantic schemas.

This module provides:
- Comment creation, update, and response schemas
- Conversation turn schemas for Q&A tracking
- Threaded comment support
"""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from backend.api.schemas.common import BaseSchema, TimestampSchema, UUIDMixin
from backend.api.schemas.user import UserResponse


# ======================
# Comment Schemas
# ======================


class CommentCreate(BaseSchema):
    """Comment creation request schema."""

    content: str = Field(..., min_length=1, max_length=10000, description="Comment content")
    parent_comment_id: Optional[UUID] = Field(
        default=None, description="Parent comment ID for threaded replies"
    )
    resource_type: str = Field(..., description="Type of resource (artifact, decision, etc.)")
    resource_id: UUID = Field(..., description="ID of the resource being commented on")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Additional metadata")


class CommentUpdate(BaseSchema):
    """Comment update request schema."""

    content: str = Field(..., min_length=1, max_length=10000)


class CommentResponse(UUIDMixin, TimestampSchema):
    """Comment response schema."""

    content: str
    author_id: UUID
    parent_comment_id: Optional[UUID] = None
    resource_type: str
    resource_id: UUID
    is_resolved: bool = False
    metadata: Optional[dict[str, Any]] = None


class CommentDetail(CommentResponse):
    """Comment detail with full relationships."""

    author: Optional[UserResponse] = None
    replies: Optional[List["CommentResponse"]] = None
    reply_count: int = 0


class CommentListResponse(BaseModel):
    """Comment list response."""

    comments: List[CommentResponse]
    total: int
    page: int
    page_size: int


class CommentFilter(BaseModel):
    """Comment filter parameters."""

    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    author_id: Optional[UUID] = None
    parent_comment_id: Optional[UUID] = None
    is_resolved: Optional[bool] = None


class CommentResolve(BaseSchema):
    """Resolve comment request schema."""

    resolved: bool = Field(..., description="Whether the comment is resolved")


class BulkCommentCreate(BaseSchema):
    """Bulk comment creation request."""

    comments: List[CommentCreate]


# ======================
# Conversation Turn Schemas (Q&A Tracking)
# ======================


class ConversationTurnCreate(BaseSchema):
    """Conversation turn creation request schema."""

    question_text: str = Field(..., min_length=1, description="The user's question")
    answer_text: Optional[str] = Field(default=None, description="The assistant's answer")
    context: Optional[dict[str, Any]] = Field(
        default=None, description="Context for the conversation"
    )
    resource_type: Optional[str] = Field(
        default=None, description="Related resource type"
    )
    resource_id: Optional[UUID] = Field(
        default=None, description="Related resource ID"
    )
    turn_number: int = Field(..., description="Order of turn in conversation")


class ConversationTurnUpdate(BaseSchema):
    """Conversation turn update request schema."""

    answer_text: Optional[str] = None
    is_helpful: Optional[bool] = None
    feedback: Optional[str] = None


class ConversationTurnResponse(UUIDMixin, TimestampSchema):
    """Conversation turn response schema."""

    user_id: UUID
    question_text: str
    answer_text: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    turn_number: int
    is_helpful: Optional[bool] = None
    feedback: Optional[str] = None


class ConversationTurnDetail(ConversationTurnResponse):
    """Conversation turn with full info."""

    user: Optional[UserResponse] = None


class ConversationResponse(BaseModel):
    """Full conversation response with all turns."""

    conversation_id: UUID
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    turns: List[ConversationTurnResponse]
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Conversation list response."""

    conversations: List[ConversationResponse]
    total: int
    page: int
    page_size: int


class ConversationFeedback(BaseSchema):
    """Conversation feedback request schema."""

    is_helpful: bool = Field(..., description="Was the answer helpful?")
    feedback: Optional[str] = Field(default=None, description="Additional feedback")


# ======================
# Mentions and Notifications
# ======================


class MentionCreate(BaseSchema):
    """Create a mention notification."""

    user_id: UUID = Field(..., description="User being mentioned")
    resource_type: str = Field(..., description="Type of resource")
    resource_id: UUID = Field(..., description="ID of the resource")
    comment_id: Optional[UUID] = Field(default=None, description="Comment containing mention")


class MentionResponse(BaseSchema):
    """Mention response schema."""

    id: UUID
    mentioned_user_id: UUID
    mentioned_by_user_id: UUID
    resource_type: str
    resource_id: UUID
    comment_id: Optional[UUID]
    is_read: bool
    created_at: datetime


class NotificationPreferences(BaseSchema):
    """User notification preferences."""

    email_on_mention: bool = True
    email_on_comment: bool = True
    email_on_decision: bool = True
    email_on_artifact: bool = True
    browser_notifications: bool = True
