"""Custom exception classes and handlers."""

import logging
from typing import Any, Dict, Optional, Union

from fastapi import HTTPException, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

# Configure logging
logger = logging.getLogger(__name__)


class BaseCustomException(Exception):
    """Base exception class for custom exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(BaseCustomException):
    """Authentication related errors."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationError(BaseCustomException):
    """Authorization related errors."""

    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ValidationError(BaseCustomException):
    """Validation related errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class NotFoundError(BaseCustomException):
    """Resource not found errors."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ConflictError(BaseCustomException):
    """Resource conflict errors."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class BadRequestError(BaseCustomException):
    """Bad request errors."""

    def __init__(
        self,
        message: str = "Bad request",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InternalServerError(BaseCustomException):
    """Internal server errors."""

    def __init__(
        self,
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class FileUploadError(BaseCustomException):
    """File upload related errors."""

    def __init__(
        self,
        message: str = "File upload failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class FileProcessingError(BaseCustomException):
    """File processing related errors."""

    def __init__(
        self,
        message: str = "File processing failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ProjectPermissionError(BaseCustomException):
    """Project permission related errors."""

    def __init__(
        self,
        message: str = "Insufficient project permissions",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class TaskAssignmentError(BaseCustomException):
    """Task assignment related errors."""

    def __init__(
        self,
        message: str = "Task assignment failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AnnotationError(BaseCustomException):
    """Annotation related errors."""

    def __init__(
        self,
        message: str = "Annotation operation failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


# Exception handlers
async def custom_exception_handler(
    request: Request, exc: BaseCustomException
) -> JSONResponse:
    """
    Handle custom exceptions.

    Args:
        request: FastAPI request object
        exc: Custom exception instance

    Returns:
        JSONResponse: Error response
    """
    logger.error(
        f"Custom exception occurred: {exc.__class__.__name__}: {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "details": exc.details,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


async def http_exception_override_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """
    Override default HTTP exception handler for consistent error format.

    Args:
        request: FastAPI request object
        exc: HTTP exception instance

    Returns:
        JSONResponse: Error response
    """
    logger.warning(
        f"HTTP exception occurred: {exc.status_code}: {exc.detail}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "HTTPException",
                "message": exc.detail,
                "details": {},
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Handle validation exceptions.

    Args:
        request: FastAPI request object
        exc: Validation exception instance

    Returns:
        JSONResponse: Error response
    """
    logger.error(
        f"Validation exception occurred: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "ValidationError",
                "message": "Validation failed",
                "details": {"validation_error": str(exc)},
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


async def database_exception_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """
    Handle database integrity errors.

    Args:
        request: FastAPI request object
        exc: Database integrity error instance

    Returns:
        JSONResponse: Error response
    """
    logger.error(
        f"Database integrity error: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )

    # Check for specific integrity constraint violations
    error_message = "Database operation failed"
    if "unique constraint" in str(exc).lower():
        error_message = "Resource already exists"
        status_code = status.HTTP_409_CONFLICT
    elif "foreign key constraint" in str(exc).lower():
        error_message = "Referenced resource does not exist"
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": "DatabaseError",
                "message": error_message,
                "details": {
                    "database_error": (
                        str(exc.orig) if hasattr(exc, "orig") else str(exc)
                    )
                },
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Args:
        request: FastAPI request object
        exc: Exception instance

    Returns:
        JSONResponse: Error response
    """
    logger.error(
        f"Unexpected exception occurred: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "InternalServerError",
                "message": "An unexpected error occurred",
                "details": {},
                "path": request.url.path,
                "method": request.method,
            }
        },
    )
