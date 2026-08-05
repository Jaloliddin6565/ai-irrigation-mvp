from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyses, config_options, farmers, fields, health, irrigations
from app.core.errors import (
    AppError,
    UnhandledExceptionMiddleware,
    app_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="AI Irrigation MVP API",
    version="0.1.0",
    description=(
        "Sensor-free irrigation decision-support API. Estimates only — this "
        "system does not directly measure soil moisture. No authentication "
        "in this MVP; not suitable for public deployment. See CLAUDE.md."
    ),
)

# Order matters: UnhandledExceptionMiddleware must be added BEFORE
# CORSMiddleware so that CORSMiddleware ends up outermost and still applies
# its headers to the 500 responses this middleware builds. A handler
# registered via app.add_exception_handler(Exception, ...) would instead be
# promoted to Starlette's ServerErrorMiddleware, which always sits outside
# every add_middleware()-registered middleware (including CORS) — see
# UnhandledExceptionMiddleware's docstring.
app.add_middleware(UnhandledExceptionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

app.include_router(health.router)
app.include_router(config_options.router)
app.include_router(farmers.router)
app.include_router(fields.router)
app.include_router(irrigations.router)
app.include_router(analyses.router)
