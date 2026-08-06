"""Explicit checks that the db_session/db_client fixtures give each test a
fresh, empty database — nothing from a previous test can leak in, and a
failed write (IntegrityError) doesn't corrupt the session for later use.
"""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.farmer import Farmer

FARMER_PAYLOAD = {
    "full_name": "Aliyev Vali",
    "phone": "+998901234567",
    "region": "Toshkent viloyati",
    "district": "Zangiota tumani",
}


def test_database_starts_empty_a(db_session: Session) -> None:
    db_session.add(Farmer(**FARMER_PAYLOAD))
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(Farmer)) == 1


def test_database_starts_empty_b(db_session: Session) -> None:
    """Runs independently of test_database_starts_empty_a — if fixtures leaked
    state between tests, this would see the farmer created above."""
    assert db_session.scalar(select(func.count()).select_from(Farmer)) == 0


def test_rollback_after_conflict_does_not_persist_partial_state(db_client: TestClient) -> None:
    db_client.post("/api/farmers", json=FARMER_PAYLOAD)
    conflict = db_client.post("/api/farmers", json={**FARMER_PAYLOAD, "full_name": "Ikkinchi"})
    assert conflict.status_code == 409

    # Exactly one farmer should exist — the failed attempt left no row behind.
    response = db_client.get("/api/farmers/1")
    assert response.status_code == 200
    assert response.json()["full_name"] == "Aliyev Vali"

    missing = db_client.get("/api/farmers/2")
    assert missing.status_code == 404
