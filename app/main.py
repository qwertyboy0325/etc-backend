"""Main FastAPI application module."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import (
    BaseCustomException,
    custom_exception_handler,
    database_exception_handler,
    general_exception_handler,
    http_exception_override_handler,
    validation_exception_handler,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("Starting up ETC Point Cloud Annotation System...")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")

        # Add any other startup tasks here
        # e.g., initialize Redis, MinIO, etc.

        logger.info("Application startup complete")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")

    try:
        # Close database connections
        await close_db()
        logger.info("Database connections closed")

        # Add any other cleanup tasks here

        logger.info("Application shutdown complete")

    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A comprehensive point cloud annotation system for vehicle detection training",
    openapi_url=settings.ENABLE_OPENAPI_URL if settings.ENABLE_DOCS else None,
    docs_url="/api/v1/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/api/v1/redoc" if settings.ENABLE_REDOC else None,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",  # 添加3002端口
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",  # 添加3002端口
        "http://192.168.0.104:3000",
        "http://192.168.0.104:3001",
        "http://192.168.0.104:3002",  # 添加3002端口
    ]
    + [
        str(origin) for origin in settings.BACKEND_CORS_ORIGINS
    ],  # 同時使用config中的設定
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware (security)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["*"]  # Configure properly for production
)


# Custom middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all requests with timing information.

    Args:
        request: FastAPI request object
        call_next: Next middleware/route handler

    Returns:
        Response: HTTP response
    """
    start_time = time.time()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent", "unknown"),
        },
    )

    # Process request
    response = await call_next(request)

    # Calculate processing time
    process_time = time.time() - start_time

    # Log response
    logger.info(
        f"Response: {response.status_code} - {process_time:.3f}s",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": process_time,
            "client_ip": client_ip,
        },
    )

    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)

    return response


# Add exception handlers
app.add_exception_handler(BaseCustomException, custom_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
app.add_exception_handler(IntegrityError, database_exception_handler)
# app.add_exception_handler(HTTPException, http_exception_override_handler)
# app.add_exception_handler(RequestValidationError, validation_exception_handler)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Dict[str, Any]: Health status information
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
    }


# Removed duplicate API health check endpoint
# The health check functionality is now handled by the /api/v1/system/health endpoint
# in the health.py router


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """
    Root endpoint with basic application information.

    Returns:
        Dict[str, Any]: Application information
    """
    return {
        "message": "Welcome to ETC Point Cloud Annotation System",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs_url": "/api/v1/docs" if settings.ENABLE_DOCS else None,
        "health_check": "/health",
    }


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Custom 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> JSONResponse:
    """
    Custom 404 handler.

    Args:
        request: FastAPI request object
        exc: Exception instance

    Returns:
        JSONResponse: 404 error response
    """
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "type": "NotFound",
                "message": "The requested resource was not found",
                "details": {},
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


# Custom 405 handler
@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc) -> JSONResponse:
    """
    Custom 405 handler.

    Args:
        request: FastAPI request object
        exc: Exception instance

    Returns:
        JSONResponse: 405 error response
    """
    return JSONResponse(
        status_code=405,
        content={
            "error": {
                "type": "MethodNotAllowed",
                "message": "The requested method is not allowed for this resource",
                "details": {},
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
