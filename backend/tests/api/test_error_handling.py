"""Regression coverage for how truly unexpected (non-AppError) exceptions
are turned into responses — see app/core/errors.py::UnhandledExceptionMiddleware.

The key property under test: CORS headers must still be present on a 500
response. A handler registered via app.add_exception_handler(Exception, ...)
is silently promoted by Starlette to ServerErrorMiddleware, which sits
*outside* CORSMiddleware — so the browser's fetch() call sees an opaque
network failure instead of the real error body (found via a live frontend
walkthrough in Phase 6, reproduced here without needing a browser).
"""

from fastapi.testclient import TestClient

from app.api import farmers as farmers_api
from app.services import farmers as farmers_service

FARMER_PAYLOAD = {
    "full_name": "Aliyev Vali",
    "phone": "+998901234567",
    "region": "Toshkent viloyati",
    "district": "Zangiota tumani",
}


def test_unhandled_exception_returns_structured_500_with_cors_headers(
    db_client: TestClient, monkeypatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr(farmers_api.farmers_service, "create_farmer", _boom)

    response = db_client.post(
        "/api/farmers",
        json=FARMER_PAYLOAD,
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert "simulated unexpected failure" not in response.text
    assert "Traceback" not in response.text
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_unhandled_exception_from_a_different_route_also_gets_cors_headers(
    db_client: TestClient, monkeypatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr(farmers_service, "get_farmer_or_404", _boom)

    response = db_client.get(
        "/api/farmers/1",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
