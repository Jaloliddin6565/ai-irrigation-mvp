"""Shared-password gate for controlled pilot deployments.

This is deliberately small and is not a replacement for farmer-level
identity, ownership, or authorization. It only prevents an untrusted public
visitor from opening a pilot deployment while the full authentication layer
is still deferred.
"""

import base64
import secrets

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class PilotBasicAuthMiddleware:
    """Require HTTP Basic credentials for every path except the health check."""

    def __init__(self, app: ASGIApp, *, username: str, password: str) -> None:
        self.app = app
        self.username = username
        self.password = password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return

        credentials = self._parse_basic_credentials(Headers(scope=scope).get("authorization"))
        if credentials is None or not (
            secrets.compare_digest(credentials[0], self.username)
            and secrets.compare_digest(credentials[1], self.password)
        ):
            response = PlainTextResponse(
                "Pilot access credentials are required.",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="AI Irrigation Pilot"'},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _parse_basic_credentials(header: str | None) -> tuple[str, str] | None:
        if not header or not header.startswith("Basic "):
            return None
        try:
            decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return None
        return username, password
