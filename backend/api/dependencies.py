"""
Shared FastAPI dependencies for API endpoints.

This module provides commonly used dependency injection functions:
- get_current_user: Get authenticated user from JWT token
- get_db_session: Get async database session
"""

from backend.db.connection import get_db_session
from backend.api.endpoints.auth import get_current_user

__all__ = ["get_current_user", "get_db_session"]
