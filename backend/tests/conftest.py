import os
from collections.abc import Generator

os.environ.setdefault("DATA_MODE", "fixture")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.db.models  # noqa: E402,F401 — registers all tables on Base.metadata
from app.api.deps import get_db  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Plain app client, no database override — for DB-free endpoints only."""
    return TestClient(app)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """A fresh, isolated in-memory SQLite database for a single test.

    Function-scoped: every test gets its own empty schema, so tests never
    see state left behind by another test (see docs/validation.md's note on
    determinism-as-a-validation-concern, and CLAUDE.md's testing rules).
    """
    engine: Engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient wired to the isolated db_session fixture via dependency override."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
