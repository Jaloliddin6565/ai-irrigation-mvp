"""Logging configuration.

Rule: never log secrets. Any request/response logging middleware added later
must call redact_headers() on header dicts before logging them.
"""

import logging

_REDACT_HEADER_NAMES = {"authorization", "x-api-key", "cookie", "set-cookie"}
_REDACTED = "***REDACTED***"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: (_REDACTED if key.lower() in _REDACT_HEADER_NAMES else value)
        for key, value in headers.items()
    }


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
