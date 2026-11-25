"""Custom domain exceptions and RFC 7807-style global exception handlers."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ai_routeranker.api")


class AppException(Exception):
    """Base application exception mapped to structured RFC 7807-style JSON responses."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class EntityNotFoundError(AppException):
    """Raised when a requested route or explanation does not exist."""

    def __init__(
        self,
        code: str = "ENTITY_NOT_FOUND",
        message: str = "Requested resource was not found.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class InvalidParameterError(AppException):
    """Raised when query or path parameters fail domain validation."""

    def __init__(
        self,
        code: str = "INVALID_PARAMETER",
        message: str = "One or more request parameters are invalid.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class ArtifactUnavailableError(AppException):
    """Raised when a required analytical artifact is missing, unreadable, or corrupt."""

    def __init__(
        self,
        code: str = "ARTIFACT_UNAVAILABLE",
        message: str = "Analytical data artifact is temporarily unavailable.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


def _build_error_payload(
    status_code: int,
    code: str,
    title: str,
    detail: str,
    instance: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a safe RFC 7807-style problem details payload."""
    payload: Dict[str, Any] = {
        "type": f"https://ai-routeranker.local/errors/{code.lower()}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "code": code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details:
        payload["errors"] = details
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_payload(
                status_code=exc.status_code,
                code=exc.code,
                title=exc.code.replace("_", " ").title(),
                detail=exc.message,
                instance=str(request.url.path),
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        sanitized_errors = [
            {
                "loc": [str(part) for part in err.get("loc", [])],
                "msg": str(err.get("msg", "Invalid value")),
                "type": str(err.get("type", "value_error")),
            }
            for err in exc.errors()
        ]
        status_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        return JSONResponse(
            status_code=status_422,
            content=_build_error_payload(
                status_code=status_422,
                code="VALIDATION_ERROR",
                title="Request Validation Failed",
                detail="One or more request parameters failed validation.",
                instance=str(request.url.path),
                details={"fields": sanitized_errors},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_payload(
                status_code=exc.status_code,
                code=f"HTTP_{exc.status_code}",
                title="HTTP Error",
                detail=str(exc.detail),
                instance=str(request.url.path),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error on path %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error_payload(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_SERVER_ERROR",
                title="Internal Server Error",
                detail="An unexpected internal error occurred.",
                instance=str(request.url.path),
            ),
        )
