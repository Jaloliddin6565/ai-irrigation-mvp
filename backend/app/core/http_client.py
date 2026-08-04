"""Shared async HTTP client for external providers (Open-Meteo, CDSE).

Bounded and safe by construction: explicit timeout, bounded
exponential-backoff retries only on transient failures (HTTP 429/500/502/
503/504, connection errors, timeouts) — never on other 4xx responses, since
those are permanent from the caller's perspective (bad request, invalid
geometry, auth rejected) and retrying them would just repeat the same
failure. Every exhausted-retry failure is normalized into a typed
ProviderError (app/core/provider_errors.py) before leaving this module.

Callers are responsible for interpreting non-retryable status codes (2xx,
and 4xx other than 429) themselves, because the right typed error differs by
context (e.g. a 401 during OAuth token issuance vs. a 401 on an
already-authenticated Catalog request that should trigger one token
refresh+retry — see app/providers/satellite/cdse_auth.py).

Never logs a full response body (may contain volumes of scene/statistics
data, or in error cases provider-specific detail we don't want duplicated in
our own logs) and never logs request headers without redaction.
"""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.provider_errors import (
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)

logger = logging.getLogger("app.http_client")

_REDACT_HEADER_NAMES = {"authorization", "x-api-key", "cookie", "set-cookie"}
_REDACTED = "***REDACTED***"

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: (_REDACTED if key.lower() in _REDACT_HEADER_NAMES else value)
        for key, value in headers.items()
    }


def _parse_retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class RetryingHttpClient:
    """A thin, bounded-retry wrapper around ``httpx.AsyncClient``.

    One instance is safe to reuse across requests within a single provider
    call; construct a fresh one per provider instance (or inject a
    ``transport`` for tests) rather than sharing global mutable state.
    """

    def __init__(
        self,
        *,
        provider: str,
        timeout_seconds: float,
        max_retries: int,
        retry_base_delay_seconds: float,
        retry_max_delay_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._provider = provider
        self._max_retries = max(0, max_retries)
        self._retry_base_delay_seconds = max(0.0, retry_base_delay_seconds)
        self._retry_max_delay_seconds = max(0.0, retry_max_delay_seconds)
        self._client = httpx.AsyncClient(timeout=timeout_seconds, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "RetryingHttpClient":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._client.request(
                    method, url, params=params, json=json, data=data, headers=headers
                )
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise ProviderTimeoutError(
                        provider=self._provider,
                        message_en=f"{self._provider} request timed out after "
                        f"{attempt + 1} attempt(s).",
                        message_uz=f"{self._provider} so'roviga javob berish vaqti tugadi.",
                    ) from exc
                logger.warning(
                    "%s request timed out (attempt %d/%d), retrying",
                    self._provider,
                    attempt + 1,
                    self._max_retries,
                )
                await self._sleep_backoff(attempt)
                attempt += 1
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise ProviderNetworkError(
                        provider=self._provider,
                        message_en=f"{self._provider} request failed: network error.",
                        message_uz=f"{self._provider} bilan tarmoq xatoligi yuz berdi.",
                    ) from exc
                logger.warning(
                    "%s network error (attempt %d/%d), retrying: %s",
                    self._provider,
                    attempt + 1,
                    self._max_retries,
                    type(exc).__name__,
                )
                await self._sleep_backoff(attempt)
                attempt += 1
                continue

            if response.status_code == 429:
                retry_after = _parse_retry_after(response)
                if attempt >= self._max_retries:
                    raise ProviderRateLimitError(
                        provider=self._provider,
                        message_en=f"{self._provider} rate limit exceeded.",
                        message_uz=f"{self._provider} so'rovlar chegarasi oshib ketdi.",
                        retry_after_seconds=retry_after,
                    )
                logger.warning(
                    "%s rate limited (attempt %d/%d), retrying",
                    self._provider,
                    attempt + 1,
                    self._max_retries,
                )
                await self._sleep_backoff(attempt, retry_after=retry_after)
                attempt += 1
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt >= self._max_retries:
                    raise ProviderServerError(
                        provider=self._provider,
                        message_en=f"{self._provider} returned HTTP {response.status_code}.",
                        message_uz=f"{self._provider} serverida xatolik yuz berdi.",
                        upstream_status_code=response.status_code,
                    )
                logger.warning(
                    "%s returned HTTP %d (attempt %d/%d), retrying",
                    self._provider,
                    response.status_code,
                    attempt + 1,
                    self._max_retries,
                )
                await self._sleep_backoff(attempt)
                attempt += 1
                continue

            return response

    async def _sleep_backoff(self, attempt: int, *, retry_after: float | None = None) -> None:
        if retry_after is not None:
            delay = min(retry_after, self._retry_max_delay_seconds)
        else:
            delay = min(
                self._retry_base_delay_seconds * (2**attempt), self._retry_max_delay_seconds
            )
        if delay > 0:
            await asyncio.sleep(delay)
