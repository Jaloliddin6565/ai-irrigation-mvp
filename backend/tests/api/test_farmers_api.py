from fastapi.testclient import TestClient

FARMER_PAYLOAD = {
    "full_name": "Aliyev Vali",
    "phone": "+998901234567",
    "region": "Toshkent viloyati",
    "district": "Zangiota tumani",
}


def test_create_farmer_success(db_client: TestClient) -> None:
    response = db_client.post("/api/farmers", json=FARMER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Aliyev Vali"
    assert body["phone"] == "+998901234567"
    assert body["preferred_language"] == "uz"
    assert "id" in body
    assert "created_at" in body


def test_create_farmer_invalid_phone_returns_422(db_client: TestClient) -> None:
    response = db_client.post("/api/farmers", json={**FARMER_PAYLOAD, "phone": "not-a-phone"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"


def test_create_farmer_duplicate_phone_returns_409(db_client: TestClient) -> None:
    first = db_client.post("/api/farmers", json=FARMER_PAYLOAD)
    assert first.status_code == 201

    second = db_client.post("/api/farmers", json={**FARMER_PAYLOAD, "full_name": "Boshqa Fermer"})

    assert second.status_code == 409
    assert second.json()["code"] == "farmer_phone_conflict"


def test_session_usable_after_conflict_rollback(db_client: TestClient) -> None:
    """A failed create (IntegrityError -> rollback) must not break the session
    for subsequent, valid operations in the same request/session lifecycle."""
    db_client.post("/api/farmers", json=FARMER_PAYLOAD)
    conflict = db_client.post("/api/farmers", json={**FARMER_PAYLOAD, "full_name": "Boshqa"})
    assert conflict.status_code == 409

    recovered = db_client.post("/api/farmers", json={**FARMER_PAYLOAD, "phone": "+998907654321"})
    assert recovered.status_code == 201


def test_get_farmer_by_id(db_client: TestClient) -> None:
    created = db_client.post("/api/farmers", json=FARMER_PAYLOAD).json()

    response = db_client.get(f"/api/farmers/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_farmer_returns_404(db_client: TestClient) -> None:
    response = db_client.get("/api/farmers/999999")

    assert response.status_code == 404
    assert response.json()["code"] == "farmer_not_found"


def test_get_farmer_by_phone(db_client: TestClient) -> None:
    created = db_client.post("/api/farmers", json=FARMER_PAYLOAD).json()

    response = db_client.get("/api/farmers", params={"phone": FARMER_PAYLOAD["phone"]})

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_farmer_by_phone_no_match_returns_404(db_client: TestClient) -> None:
    response = db_client.get("/api/farmers", params={"phone": "+998900000000"})

    assert response.status_code == 404
    assert response.json()["code"] == "farmer_not_found"


def test_get_farmer_by_invalid_phone_returns_422(db_client: TestClient) -> None:
    response = db_client.get("/api/farmers", params={"phone": "not-a-phone"})

    assert response.status_code == 422
