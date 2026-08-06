"""Structured, safe errors raised by external providers (Open-Meteo, CDSE).

These extend the existing app/core/errors.py AppError contract, so no new
FastAPI exception-handler wiring is required — the API layer already turns
any AppError into {code, message_uz, message_en, details} with the right
status code (see app/core/errors.py::app_error_handler). `details` never
contains a token, client secret, or Authorization header value; only
`provider`/`retryable` and other safe context (e.g. an upstream HTTP status
code) may be included.
"""

from app.core.errors import AppError


class ProviderError(AppError):
    def __init__(
        self,
        *,
        code: str,
        message_en: str,
        message_uz: str,
        provider: str,
        status_code: int,
        retryable: bool = False,
        details: dict | None = None,
    ) -> None:
        merged_details: dict = {"provider": provider, "retryable": retryable, **(details or {})}
        super().__init__(
            code=code,
            message_uz=message_uz,
            message_en=message_en,
            status_code=status_code,
            details=merged_details,
        )
        self.provider = provider
        self.retryable = retryable


class ProviderConfigurationError(ProviderError):
    """Missing/invalid credentials or settings. Never retryable, never
    silently substituted with fixture data — see CLAUDE.md rule 5."""

    def __init__(self, *, provider: str, message_en: str, message_uz: str) -> None:
        super().__init__(
            code="provider_configuration_error",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=503,
            retryable=False,
        )


class ProviderAuthenticationError(ProviderError):
    def __init__(self, *, provider: str, message_en: str, message_uz: str) -> None:
        super().__init__(
            code="provider_authentication_error",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=502,
            retryable=False,
        )


class ProviderRateLimitError(ProviderError):
    def __init__(
        self,
        *,
        provider: str,
        message_en: str,
        message_uz: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(
            code="provider_rate_limited",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=503,
            retryable=True,
            details={"retry_after_seconds": retry_after_seconds},
        )


class ProviderTimeoutError(ProviderError):
    def __init__(self, *, provider: str, message_en: str, message_uz: str) -> None:
        super().__init__(
            code="provider_timeout",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=504,
            retryable=True,
        )


class ProviderNetworkError(ProviderError):
    def __init__(self, *, provider: str, message_en: str, message_uz: str) -> None:
        super().__init__(
            code="provider_network_error",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=502,
            retryable=True,
        )


class ProviderServerError(ProviderError):
    def __init__(
        self, *, provider: str, message_en: str, message_uz: str, upstream_status_code: int
    ) -> None:
        super().__init__(
            code="provider_server_error",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=502,
            retryable=True,
            details={"upstream_status_code": upstream_status_code},
        )


class ProviderMalformedResponseError(ProviderError):
    def __init__(self, *, provider: str, message_en: str, message_uz: str) -> None:
        super().__init__(
            code="provider_malformed_response",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=502,
            retryable=False,
        )


class UnsupportedGeometryError(ProviderError):
    def __init__(self, *, provider: str, message_en: str, message_uz: str) -> None:
        super().__init__(
            code="unsupported_geometry",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=422,
            retryable=False,
        )


class InvalidDateRangeError(ProviderError):
    def __init__(self, *, provider: str, message_en: str, message_uz: str) -> None:
        super().__init__(
            code="invalid_date_range",
            message_en=message_en,
            message_uz=message_uz,
            provider=provider,
            status_code=422,
            retryable=False,
        )
