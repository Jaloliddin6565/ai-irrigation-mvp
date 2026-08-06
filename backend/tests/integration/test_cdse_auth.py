"""Mocked tests for the CDSE OAuth token-cache client. No real network
calls — respx intercepts httpx at the transport layer.
"""

import asyncio

import httpx
import pytest
import respx

from app.core.http_client import RetryingHttpClient
from app.core.provider_errors import (
    ProviderAuthenticationError,
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.providers.satellite.cdse_auth import CdseTokenClient

TOKEN_URL = "https://identity.test/token"


def _token_client(clock=None, **overrides: object) -> CdseTokenClient:
    defaults: dict = dict(
        client_id="test-id",
        client_secret="test-secret",
        token_url=TOKEN_URL,
        expiry_margin_seconds=10,
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    defaults.update(overrides)
    if clock is not None:
        defaults["clock"] = clock
    return CdseTokenClient(**defaults)


@respx.mock
async def test_successful_token_retrieval() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    token = await _token_client().get_token()
    assert token == "tok-1"


@respx.mock
async def test_cached_token_is_reused_without_a_second_request() -> None:
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    client = _token_client()
    await client.get_token()
    await client.get_token()
    assert route.call_count == 1


@respx.mock
def test_token_client_survives_reuse_across_separate_asyncio_run_calls() -> None:
    """Reproduces the real production call pattern: `CdseTokenClient` is a
    process-lifetime singleton (providers/factory.py, @lru_cache) but each
    provider call is bridged from sync to async via its own `asyncio.run()`
    (see app/providers/satellite/cdse.py) — a fresh event loop every time.
    Found via a Phase 6 live-mode walkthrough: a lock created once in
    __init__ bound to the first loop and then raised `RuntimeError: ...
    is bound to a different event loop` on the second call. Deliberately
    uses asyncio.run() twice on the *same* client instance rather than
    awaiting twice within one test's loop, which would never have caught
    this."""
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    client = _token_client()

    first = asyncio.run(client.get_token())
    second = asyncio.run(client.get_token())

    assert first == "tok-1"
    assert second == "tok-1"
    assert route.call_count == 1


@respx.mock
async def test_token_is_refreshed_once_the_expiry_margin_is_reached() -> None:
    route = respx.post(TOKEN_URL)
    route.side_effect = [
        httpx.Response(200, json={"access_token": "tok-1", "expires_in": 100}),
        httpx.Response(200, json={"access_token": "tok-2", "expires_in": 100}),
    ]
    now = [1000.0]
    client = _token_client(clock=lambda: now[0], expiry_margin_seconds=10)
    token1 = await client.get_token()
    now[0] += 91.0  # usable_ttl = 100 - 10 = 90s, so this is just past it
    token2 = await client.get_token()
    assert token1 == "tok-1"
    assert token2 == "tok-2"
    assert route.call_count == 2


@respx.mock
async def test_token_is_still_reused_just_before_the_expiry_margin_boundary() -> None:
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 100})
    )
    now = [1000.0]
    client = _token_client(clock=lambda: now[0], expiry_margin_seconds=10)
    await client.get_token()
    now[0] += 89.999  # just under the 90s usable window
    await client.get_token()
    assert route.call_count == 1


@respx.mock
async def test_malformed_json_response_raises_malformed_response_error() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, content=b"not json", headers={"content-type": "application/json"}
        )
    )
    with pytest.raises(ProviderMalformedResponseError):
        await _token_client().get_token()


@respx.mock
async def test_missing_access_token_raises_malformed_response_error() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"expires_in": 100}))
    with pytest.raises(ProviderMalformedResponseError):
        await _token_client().get_token()


@respx.mock
async def test_missing_expires_in_raises_malformed_response_error() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok"}))
    with pytest.raises(ProviderMalformedResponseError):
        await _token_client().get_token()


@respx.mock
async def test_non_json_content_type_raises_malformed_response_error() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, content=b"access_token=x", headers={"content-type": "text/plain"}
        )
    )
    with pytest.raises(ProviderMalformedResponseError):
        await _token_client().get_token()


@respx.mock
async def test_400_invalid_client_raises_authentication_error() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_client"}))
    with pytest.raises(ProviderAuthenticationError):
        await _token_client().get_token()


@respx.mock
async def test_401_raises_authentication_error() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderAuthenticationError):
        await _token_client().get_token()


@respx.mock
async def test_429_raises_rate_limit_error() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderRateLimitError):
        await _token_client().get_token()


@respx.mock
async def test_timeout_raises_provider_timeout_error() -> None:
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("boom"))
    with pytest.raises(ProviderTimeoutError):
        await _token_client().get_token()


@respx.mock
async def test_5xx_raises_provider_server_error() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderServerError):
        await _token_client().get_token()


@respx.mock
async def test_no_token_or_secret_in_exception_message_or_details() -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401))
    client = _token_client(client_secret="super-secret-value")  # pragma: allowlist secret
    with pytest.raises(ProviderAuthenticationError) as exc_info:
        await client.get_token()
    assert "super-secret-value" not in str(exc_info.value)
    assert "super-secret-value" not in repr(exc_info.value.details)


@respx.mock
async def test_401_on_protected_request_triggers_exactly_one_refresh_and_retry() -> None:
    token_route = respx.post(TOKEN_URL)
    token_route.side_effect = [
        httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600}),
        httpx.Response(200, json={"access_token": "tok-2", "expires_in": 3600}),
    ]
    protected_route = respx.get("https://api.test/protected")
    protected_route.side_effect = [httpx.Response(401), httpx.Response(200, json={"ok": True})]

    token_client = _token_client()
    async with RetryingHttpClient(
        provider="test",
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    ) as http:
        response = await token_client.request_with_auth(http, "GET", "https://api.test/protected")

    assert response.status_code == 200
    assert token_route.call_count == 2
    assert protected_route.call_count == 2


@respx.mock
async def test_second_401_after_refresh_is_returned_not_looped_forever() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    protected_route = respx.get("https://api.test/protected").mock(return_value=httpx.Response(401))

    token_client = _token_client()
    async with RetryingHttpClient(
        provider="test",
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    ) as http:
        response = await token_client.request_with_auth(http, "GET", "https://api.test/protected")

    assert response.status_code == 401  # returned to the caller, not raised or looped
    assert protected_route.call_count == 2  # exactly one retry
