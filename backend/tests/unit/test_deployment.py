from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.pilot_auth import PilotBasicAuthMiddleware
from app.db.url import normalize_database_url


def test_normalize_render_postgres_urls_for_psycopg() -> None:
    assert (
        normalize_database_url("postgres://user:pass@db:5432/app")
        == "postgresql+psycopg://user:pass@db:5432/app"
    )
    assert (
        normalize_database_url("postgresql://user:pass@db:5432/app")
        == "postgresql+psycopg://user:pass@db:5432/app"
    )


def test_normalize_database_url_preserves_explicit_and_sqlite_urls() -> None:
    assert normalize_database_url("postgresql+psycopg://u:p@db/app") == (
        "postgresql+psycopg://u:p@db/app"
    )
    assert normalize_database_url("sqlite:///./test.db") == "sqlite:///./test.db"


def _pilot_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        PilotBasicAuthMiddleware,
        username="pilot-user",
        password="pilot-secret",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/protected")
    def protected() -> dict[str, str]:
        return {"status": "protected"}

    return app


def test_pilot_auth_requires_valid_credentials() -> None:
    client = TestClient(_pilot_app())

    response = client.get("/protected")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="AI Irrigation Pilot"'

    assert client.get("/protected", auth=("pilot-user", "wrong")).status_code == 401
    assert client.get("/protected", auth=("pilot-user", "pilot-secret")).status_code == 200


def test_pilot_auth_keeps_health_check_public() -> None:
    client = TestClient(_pilot_app())
    assert client.get("/health").status_code == 200
