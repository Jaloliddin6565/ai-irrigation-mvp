"""Structured error model shared by all API responses.

Every non-2xx response body follows this shape so the frontend can render
errors consistently instead of guessing at ad-hoc formats.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
