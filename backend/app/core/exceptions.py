from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded


class AppException(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", details: dict[str, Any] | None = None):
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            code="not_found",
            message=message,
            details=details,
        )


class ValidationError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="validation_error",
            message=message,
            details=details,
        )


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="authentication_error",
            message=message,
        )


class AuthorizationError(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            status_code=HTTPStatus.FORBIDDEN,
            code="authorization_error",
            message=message,
        )


class ConflictError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            status_code=HTTPStatus.CONFLICT,
            code="conflict_error",
            message=message,
            details=details,
        )


class ExternalServiceError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            status_code=HTTPStatus.BAD_GATEWAY,
            code="external_service_error",
            message=message,
            details=details,
        )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": "Too many requests",
                    "details": {"limit": str(exc.detail)},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected server error occurred",
                    "details": {},
                }
            },
        )

