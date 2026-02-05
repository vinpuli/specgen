"""
SpecGen API Application.

This module provides the main FastAPI application configuration.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.endpoints import auth_router, workspace_router, project_router, artifact_router, comment_router, codebase_router
from backend.db.connection import init_db, close_db
from backend.db.health import get_db_health
from backend.api.schemas.common import HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# CORS allowed origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Sets up and tears down database connections.
    """
    # Startup
    logger.info("Starting up SpecGen API...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down SpecGen API...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="SpecGen API",
    description="""
    SpecGen - AI-Powered Specification Generator API

    This API provides endpoints for:
    - User authentication and management
    - Workspace management
    - Project and branch management
    - Decision tracking
    - Artifact generation
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(workspace_router, prefix="/api/v1")
app.include_router(project_router, prefix="/api/v1")
app.include_router(artifact_router, prefix="/api/v1")
app.include_router(comment_router, prefix="/api/v1")
app.include_router(codebase_router, prefix="/api/v1")


# Health check endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Check the health status of the API and its dependencies.",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns the status of the API and its dependencies.
    """
    db_health = await get_db_health()

    return HealthResponse(
        status="healthy" if db_health["healthy"] else "degraded",
        version="0.1.0",
        database=db_health["status"],
        cache="healthy",  # TODO: Implement cache health check
        timestamp=db_health["timestamp"],
    )


# Root endpoint
@app.get(
    "/",
    tags=["Root"],
    summary="Root endpoint",
    description="API root endpoint with basic information.",
)
async def root():
    """
    Root endpoint.

    Returns basic API information.
    """
    return {
        "name": "SpecGen API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
