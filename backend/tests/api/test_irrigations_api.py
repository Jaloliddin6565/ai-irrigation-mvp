from fastapi.testclient import TestClient

VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [69.2400, 41.3000],
            [69.2410, 41.3000],
            [69.2410, 41.3010],
            [69.2400, 41.3010],
            [69.2400, 41.3000],
        ]
    ],
}


def _create_field(client: TestClient) -> int:
    farmer_payload = {
        "full_name": "Aliyev Vali",
        "phone": "+998901234567",
        "region": "Toshkent viloyati",
        "district": "Zangiota tumani",
    }
    farmer_id = client.post("/api/farmers", json=farmer_payload).json()["id"]

    field_payload = {
        "farmer_id": farmer_id,
        "name": "Shimoliy dala",
        "geojson_polygon": VALID_POLYGON,
        "crop_type": "cotton",
        "planting_date": "2026-04-01",
        "irrigation_method": "drip",
        "soil_texture": "loam",
    }
    return int(client.post("/api/fields", json=field_payload).json()["id"])


def test_create_irrigation_event_success(db_client: TestClient) -> None:
    field_id = _create_field(db_client)

    response = db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={
            "occurred_at": "2026-05-01T08:00:00Z",
            "amount_mm": 20.0,
            "value_source": "measured",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["field_id"] == field_id
    assert body["amount_mm"] == 20.0


def test_create_irrigation_event_missing_field_returns_404(db_client: TestClient) -> None:
    response = db_client.post(
        "/api/fields/999999/irrigations",
        json={"occurred_at": "2026-05-01T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "field_not_found"


def test_create_irrigation_event_negative_amount_returns_422(db_client: TestClient) -> None:
    field_id = _create_field(db_client)

    response = db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={
            "occurred_at": "2026-05-01T08:00:00Z",
            "amount_mm": -5.0,
            "value_source": "measured",
        },
    )

    assert response.status_code == 422


def test_list_irrigation_events_ordered_by_occurred_at_desc(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    for day in ("01", "10", "05"):
        db_client.post(
            f"/api/fields/{field_id}/irrigations",
            json={
                "occurred_at": f"2026-05-{day}T08:00:00Z",
                "amount_mm": 10.0,
                "value_source": "measured",
            },
        )

    response = db_client.get(f"/api/fields/{field_id}/irrigations")
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3
    days = [item["occurred_at"][:10] for item in body["items"]]
    assert days == sorted(days, reverse=True)
