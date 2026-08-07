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


class FieldError(BaseModel):
    """One field-specific validation problem, so the frontend can attach the
    message to the exact input instead of only showing a generic banner."""

    field: str
    code: str
    message_uz: str


class ErrorResponse(BaseModel):
    code: str
    message_uz: str
    message_en: str | None = None
    details: dict | None = None
    field_errors: list[FieldError] | None = None


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message_uz: str,
        message_en: str | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict | None = None,
        field_errors: list[FieldError] | None = None,
    ) -> None:
        self.code = code
        self.message_uz = message_uz
        self.message_en = message_en
        self.status_code = status_code
        self.details = details
        self.field_errors = field_errors
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


# Static code -> field_errors tables for domain AppErrors whose raise site
# doesn't already pass field_errors explicitly. Reused across every raise of
# the same code so the message stays consistent regardless of which service
# function raised it.
_INVALID_DATES_FIELD_ERRORS = [
    FieldError(
        field="expected_harvest_date",
        code="invalid_dates",
        message_uz="Hosil yig'ish sanasi ekish sanasidan keyin bo'lishi kerak.",
    )
]

_INVALID_OVERRIDE_FIELD_ERRORS = [
    FieldError(
        field="field_capacity_override",
        code="invalid_override_values",
        message_uz="Dala nam sig'imi so'lish nuqtasidan katta bo'lishi kerak.",
    ),
    FieldError(
        field="wilting_point_override",
        code="invalid_override_values",
        message_uz="So'lish nuqtasi 0 dan katta va dala nam sig'imidan kichik bo'lishi kerak.",
    ),
]

_STATIC_FIELD_ERRORS_BY_CODE: dict[str, list[FieldError]] = {
    "invalid_dates": _INVALID_DATES_FIELD_ERRORS,
    "invalid_override_values": _INVALID_OVERRIDE_FIELD_ERRORS,
}


def _field_errors_for_app_error(exc: AppError) -> list[FieldError] | None:
    if exc.field_errors is not None:
        return exc.field_errors
    if exc.code == "invalid_geometry":
        # geo.py's message_uz is already a precise, per-violation Uzbek
        # sentence (wrong type, self-intersection, area too large, ...) —
        # reuse it verbatim rather than re-deriving a generic one.
        return [FieldError(field="geojson_polygon", code=exc.code, message_uz=exc.message_uz)]
    return _STATIC_FIELD_ERRORS_BY_CODE.get(exc.code)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message_uz=exc.message_uz,
            message_en=exc.message_en,
            details=exc.details,
            field_errors=_field_errors_for_app_error(exc),
        ).model_dump(),
    )


# Human-friendly Uzbek labels for the field names most likely to appear in a
# validation error across the API's write endpoints. Falls back to the raw
# field name for anything not listed here — this handler is shared by every
# endpoint, not just fields, so it must degrade gracefully for names it
# doesn't know about rather than assume a closed set.
_FIELD_LABELS_UZ = {
    "name": "Dala nomi",
    "planting_date": "Ekish sanasi",
    "expected_harvest_date": "Hosil yig'ish sanasi",
    "crop_variety": "Ekin navi",
    "root_depth_override": "Ildiz chuqurligi",
    "field_capacity_override": "Dala nam sig'imi",
    "wilting_point_override": "So'lish nuqtasi",
    "notes": "Izohlar",
    "geojson_polygon": "Dala chegarasi",
    "occurred_at": "Sug'orish sanasi",
    "amount_mm": "Sug'orish miqdori",
    "full_name": "To'liq ism",
    "phone": "Telefon raqami",
}


def _field_name_from_loc(loc: tuple) -> str | None:
    for part in reversed(loc):
        if isinstance(part, str) and part != "body":
            return part
    return None


def _constraint_suffix_uz(error: dict) -> str | None:
    """Uzbek phrasing for Pydantic's built-in Field(...) constraint types.
    Returns None for constraint types not worth a bespoke phrase — those
    fall back to the generic top-level banner instead of a wrong-sounding
    guess."""
    error_type = error.get("type")
    ctx = error.get("ctx") or {}
    if error_type == "greater_than":
        return f"{ctx.get('gt')} dan katta bo'lishi kerak."
    if error_type == "less_than":
        return f"{ctx.get('lt')} dan kichik bo'lishi kerak."
    if error_type == "less_than_equal":
        return f"{ctx.get('le')} dan oshmasligi kerak."
    if error_type == "greater_than_equal":
        return f"{ctx.get('ge')} dan kichik bo'lmasligi kerak."
    if error_type == "missing":
        return "to'ldirilishi shart."
    if error_type == "string_too_long":
        return f"{ctx.get('max_length')} belgidan oshmasligi kerak."
    if error_type == "string_too_short":
        return f"kamida {ctx.get('min_length')} belgidan iborat bo'lishi kerak."
    return None


# Our own model_validator(mode="after") ValueError messages are model-level
# (Pydantic reports loc=("body",), tied to no single field) but we authored
# the English text ourselves in app/schemas/field.py, so matching a known
# substring lets us still attach a proper per-field Uzbek message instead of
# falling back to only the generic banner.
_VALUE_ERROR_FIELD_ERRORS: list[tuple[str, list[FieldError]]] = [
    (
        "expected_harvest_date must be after planting_date",
        _INVALID_DATES_FIELD_ERRORS,
    ),
    (
        "field_capacity_override must be greater than wilting_point_override",
        _INVALID_OVERRIDE_FIELD_ERRORS,
    ),
]


def _field_errors_for_value_error(msg: str) -> list[FieldError] | None:
    for substring, field_errors in _VALUE_ERROR_FIELD_ERRORS:
        if substring in msg:
            return field_errors
    return None


def _translate_validation_errors(errors: list[dict]) -> list[FieldError]:
    field_errors: list[FieldError] = []
    for error in errors:
        if error.get("type") == "value_error":
            matched = _field_errors_for_value_error(str(error.get("msg", "")))
            if matched:
                field_errors.extend(matched)
                continue

        field_name = _field_name_from_loc(tuple(error.get("loc", ())))
        if field_name is None:
            continue
        suffix = _constraint_suffix_uz(error)
        if suffix is None:
            continue
        label = _FIELD_LABELS_UZ.get(field_name, field_name)
        field_errors.append(
            FieldError(field=field_name, code="validation_error", message_uz=f"{label} {suffix}")
        )
    return field_errors


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    raw_errors = exc.errors()

    # exc.errors() can contain raw exception instances (e.g. in ctx.error for
    # a model_validator ValueError) that a plain `dict`-typed Pydantic field
    # can't serialize. Drop the non-serializable "ctx" key (msg/type/loc
    # already carry the human-readable content) before embedding in the
    # secondary debug payload. field_errors is translated from raw_errors
    # (with ctx) directly below, before this stripping — its ctx values
    # (gt/lt/le/ge/max_length/min_length) are always plain, serializable
    # numbers, never the non-serializable exception instance.
    safe_errors = jsonable_encoder(
        [{k: v for k, v in error.items() if k != "ctx"} for error in raw_errors]
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponse(
            code="validation_error",
            message_uz="Kiritilgan ma'lumotlarda xatolik bor.",
            message_en="Request validation failed.",
            details={"errors": safe_errors},
            field_errors=_translate_validation_errors(raw_errors) or None,
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
