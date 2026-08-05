"""Structured error model shared by all API responses.

Every non-2xx response body follows this shape so the frontend can render
errors consistently instead of guessing at ad-hoc formats.
"""

import logging

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger("app.errors")


class ErrorResponse(BaseModel):
    code: str
    message_uz: str
    message_en: str | None = None
    details: dict | None = None


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message_uz: str,
        message_en: str | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message_uz = message_uz
        self.message_en = message_en
        self.status_code = status_code
        self.details = details
        super().__init__(message_en or message_uz)


class InsufficientDataError(AppError):
    """Raised when a calculation cannot proceed without fabricating data."""

    def __init__(self, code: str, message_uz: str, message_en: str | None = None) -> None:
        super().__init__(
            code=code,
            message_uz=message_uz,
            message_en=message_en,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message_uz=exc.message_uz,
            message_en=exc.message_en,
            details=exc.details,
        ).model_dump(),
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # exc.errors() can contain raw exception instances (e.g. in ctx.error for
    # a model_validator ValueError) that a plain `dict`-typed Pydantic field
    # can't serialize. Drop the non-serializable "ctx" key (msg/type/loc
    # already carry the human-readable content) before embedding.
    safe_errors = jsonable_encoder(
        [{k: v for k, v in error.items() if k != "ctx"} for error in exc.errors()]
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponse(
            code="validation_error",
            message_uz="Kiritilgan ma'lumotlarda xatolik bor.",
            message_en="Request validation failed.",
            details={"errors": safe_errors},
        ).model_dump(),
    )


def _internal_error_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(
            ErrorResponse(
                code="internal_error",
                message_uz="Serverda kutilmagan xatolik yuz berdi.",
                message_en="An unexpected server error occurred.",
            )
        ),
    )


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """Turns any exception that escapes routing/AppError/validation handling
    into the same structured 500 body as every other error response.

    This is deliberately a middleware, not `@app.exception_handler(Exception)`.
    Starlette promotes a handler registered for the bare `Exception` type to
    `ServerErrorMiddleware`, which FastAPI always places *outside* every
    middleware added via `add_middleware` (including CORSMiddleware) — so a
    JSONResponse built there never gets a CORS header, and the browser's
    fetch() call sees an opaque network failure instead of the actual 500
    body. A normal middleware sits inside that stack, so CORSMiddleware
    (added after this one in app/main.py) still applies its headers here.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> JSONResponse:
        try:
            return await call_next(request)  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001 - intentional catch-all, see class docstring
            logger.exception("Unhandled exception", exc_info=exc)
            return _internal_error_response()
