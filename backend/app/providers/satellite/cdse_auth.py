"""Backend-only OAuth client-credentials authentication for the Copernicus
Data Space Ecosystem (CDSE) Sentinel Hub APIs.

Security rules (see CLAUDE.md rule 7 and docs/security.md):
- client_id/client_secret come only from `Settings` — never hardcoded, never
  logged.
- The access token is cached in memory only — never persisted to the
  database, never written to a file, never returned in an API response,
  never logged, never embedded in an exception message.
- Refreshed proactively `token_expiry_margin_seconds` before expiry.
- A single `asyncio.Lock` serializes concurrent refreshes so parallel
  callers within one process don't each fire a fresh token request.
- Exactly one automatic re-authentication retry on a 401 from a protected
  request — never an unbounded/looping retry.
"""

import asyncio
import logging
import time
from collections.abc import Callable

import httpx

from app.core.http_client import RetryingHttpClient
from app.core.provider_errors import ProviderAuthenticationError, ProviderMalformedResponseError

logger = logging.getLogger("app.providers.satellite.cdse_auth")

PROVIDER_NAME = "cdse-oauth"


class _CachedToken:
    __slots__ = ("access_token", "expires_at_monotonic")

    def __init__(self, access_token: str, expires_at_monotonic: float) -> None:
        self.access_token = access_token
        self.expires_at_monotonic = expires_at_monotonic


class CdseTokenClient:
    """Fetches and caches a CDSE Sentinel Hub OAuth access token.

    `get_token()` and `request_with_auth()` are the only entry points other
    modules should use. Neither ever returns, logs, or raises an exception
    containing the raw token or the configured client secret.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        expiry_margin_seconds: int,
        timeout_seconds: float,
        max_retries: int,
        retry_base_delay_seconds: float,
        retry_max_delay_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._expiry_margin_seconds = expiry_margin_seconds
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        self._clock = clock
        self._transport = transport
        self._cached: _CachedToken | None = None
        self._lock = asyncio.Lock()

    async def get_token(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            if (
                not force_refresh
                and self._cached is not None
                and self._clock() < self._cached.expires_at_monotonic
            ):
                return self._cached.access_token
            self._cached = await self._fetch_token()
            return self._cached.access_token

    def invalidate(self) -> None:
        self._cached = None

    async def _fetch_token(self) -> _CachedToken:
        async with RetryingHttpClient(
            provider=PROVIDER_NAME,
            timeout_seconds=self._timeout_seconds,
            max_retries=self._max_retries,
            retry_base_delay_seconds=self._retry_base_delay_seconds,
            retry_max_delay_seconds=self._retry_max_delay_seconds,
            transport=self._transport,
        ) as client:
            response = await client.request(
                "POST",
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        # CDSE (RFC 6749 semantics) returns 400 for invalid_client/
        # invalid_grant and 401 for a rejected Authorization header — treat
        # both as a credential rejection. The response body may echo back
        # the client_id we sent, so it is never included in the exception.
        if response.status_code in (400, 401, 403):
            raise ProviderAuthenticationError(
                provider=PROVIDER_NAME,
                message_en="CDSE rejected the configured OAuth client credentials.",
                message_uz="CDSE tomonidan OAuth ma'lumotlari rad etildi.",
            )
        if response.status_code != 200:
            raise ProviderAuthenticationError(
                provider=PROVIDER_NAME,
                message_en=f"CDSE token endpoint returned HTTP {response.status_code}.",
                message_uz="CDSE token xizmatidan kutilmagan javob keldi.",
            )

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="CDSE token endpoint returned a non-JSON content type.",
                message_uz="CDSE token xizmati JSON bo'lmagan javob qaytardi.",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="CDSE token endpoint response was not valid JSON.",
                message_uz="CDSE token xizmati javobi noto'g'ri formatda.",
            ) from exc

        access_token = payload.get("access_token") if isinstance(payload, dict) else None
        expires_in = payload.get("expires_in") if isinstance(payload, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="CDSE token response is missing 'access_token'.",
                message_uz="CDSE javobida 'access_token' mavjud emas.",
            )
        if not isinstance(expires_in, int | float) or expires_in <= 0:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="CDSE token response is missing a valid 'expires_in'.",
                message_uz="CDSE javobida to'g'ri 'expires_in' mavjud emas.",
            )

        usable_ttl = max(0.0, float(expires_in) - self._expiry_margin_seconds)
        logger.info("Obtained a new CDSE access token (expires_in=%ss)", int(expires_in))
        return _CachedToken(
            access_token=access_token, expires_at_monotonic=self._clock() + usable_ttl
        )

    async def request_with_auth(
        self,
        client: RetryingHttpClient,
        method: str,
        url: str,
        *,
        params: dict[str, object] | None = None,
        json: object | None = None,
        data: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Issue a request with a Bearer token, retrying exactly once on a
        401 after invalidating and force-refreshing the cached token —
        never an unbounded loop."""
        extra_headers = headers or {}
        token = await self.get_token()
        response = await client.request(
            method,
            url,
            params=params,
            json=json,
            data=data,
            headers={**extra_headers, "Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            logger.warning("CDSE request got 401 with a cached token; refreshing once and retrying")
            self.invalidate()
            token = await self.get_token(force_refresh=True)
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers={**extra_headers, "Authorization": f"Bearer {token}"},
            )
        return response
