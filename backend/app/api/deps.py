"""Shared FastAPI dependencies.

get_current_farmer_id is the deliberate seam for future authentication.
Today it is a no-op: it trusts a farmer_id supplied by the client (query
param) with no credential check. This MVP has no authentication — see
CLAUDE.md and README.md. Route handlers must go through this dependency
(and check resource ownership against it at the DB layer) rather than
inlining their own "trust the client" logic, so that swapping in real auth
later only means changing this one function.
"""

from collections.abc import Generator

from fastapi import Query
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()


def get_current_farmer_id(
    farmer_id: int = Query(..., description="Active farmer ID (no-auth MVP)"),
) -> int:
    return farmer_id
