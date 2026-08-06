"""Mocked tests for the shared retrying HTTP client. No real network calls —
respx intercepts httpx at the transport layer (DATA_MODE stays fixture for
all other tests; this module tests the live-provider infrastructure in
isolation without touching DATA_MODE at all).
"""

import httpx
import pytest
import respx

from app.core.http_client import RetryingHttpClient, redact_headers
from app.core.provider_errors import (
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)


def _client(**overrides: object) -> RetryingHttpClient:
    defaults: dict = dict(
        provider="test-provider",
        timeout_seconds=5.0,
        max_retries=2,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    defaults.update(overrides)
    return RetryingHttpClient(**defaults)


@respx.mock
async def test_successful_request_returns_response() -> None:
    respx.get("https://example.test/ok").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with _client() as client:
        response = await client.request("GET", "https://example.test/ok")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@respx.mock
async def test_non_retryable_4xx_is_returned_immediately_without_retrying() -> None:
    route = respx.get("https://example.test/bad").mock(return_value=httpx.Response(400))
    async with _client() as client:
        response = await client.request("GET", "https://example.test/bad")
    assert response.status_code == 400
    assert route.call_count == 1


@respx.mock
async def test_5xx_is_retried_up_to_max_retries_then_raises() -> None:
    route = respx.get("https://example.test/err").mock(return_value=httpx.Response(503))
    async with _client(max_retries=2) as client:
        with pytest.raises(ProviderServerError) as exc_info:
            await client.request("GET", "https://example.test/err")
    assert route.call_count == 3  # initial attempt + 2 retries
    assert exc_info.value.details["upstream_status_code"] == 503
    assert exc_info.value.retryable is True


@respx.mock
async def test_5xx_then_success_returns_the_eventual_success() -> None:
    route = respx.get("https://example.test/flaky")
    route.side_effect = [httpx.Response(502), httpx.Response(200, json={"ok": True})]
    async with _client(max_retries=2) as client:
        response = await client.request("GET", "https://example.test/flaky")
    assert response.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_429_is_retried_then_raises_rate_limit_error() -> None:
    route = respx.get("https://example.test/limited").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"})
    )
    async with _client(max_retries=1) as client:
        with pytest.raises(ProviderRateLimitError):
            await client.request("GET", "https://example.test/limited")
    assert route.call_count == 2


@respx.mock
async def test_timeout_is_retried_then_raises_provider_timeout_error() -> None:
    route = respx.get("https://example.test/slow").mock(side_effect=httpx.ConnectTimeout("boom"))
    async with _client(max_retries=1) as client:
        with pytest.raises(ProviderTimeoutError):
            await client.request("GET", "https://example.test/slow")
    assert route.call_count == 2


@respx.mock
async def test_network_error_is_retried_then_raises_provider_network_error() -> None:
    route = respx.get("https://example.test/down").mock(side_effect=httpx.ConnectError("boom"))
    async with _client(max_retries=1) as client:
        with pytest.raises(ProviderNetworkError):
            await client.request("GET", "https://example.test/down")
    assert route.call_count == 2


@respx.mock
async def test_zero_max_retries_fails_immediately_on_5xx() -> None:
    route = respx.get("https://example.test/err").mock(return_value=httpx.Response(500))
    async with _client(max_retries=0) as client:
        with pytest.raises(ProviderServerError):
            await client.request("GET", "https://example.test/err")
    assert route.call_count == 1


def test_redact_headers_masks_sensitive_keys_case_insensitively() -> None:
    headers = {
        "Authorization": "Bearer secret",
        "x-api-key": "abc",
        "Cookie": "session=1",
        "Set-Cookie": "session=1",
        "X-Other": "kept",
    }
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "***REDACTED***"
    assert redacted["x-api-key"] == "***REDACTED***"
    assert redacted["Cookie"] == "***REDACTED***"
    assert redacted["Set-Cookie"] == "***REDACTED***"
    assert redacted["X-Other"] == "kept"
