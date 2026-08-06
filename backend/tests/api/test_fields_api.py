from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.analysis import Analysis
from app.db.models.irrigation_event import IrrigationEvent

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


def _create_farmer(client: TestClient) -> int:
    payload = {
        "full_name": "Aliyev Vali",
        "phone": "+998901234567",
        "region": "Toshkent viloyati",
        "district": "Zangiota tumani",
    }
    return int(client.post("/api/farmers", json=payload).json()["id"])


def _field_payload(farmer_id: int, **overrides) -> dict:
    payload = {
        "farmer_id": farmer_id,
        "name": "Shimoliy dala",
        "geojson_polygon": VALID_POLYGON,
        "crop_type": "cotton",
        "planting_date": "2026-04-01",
        "irrigation_method": "drip",
        "soil_texture": "loam",
    }
    payload.update(overrides)
    return payload


def test_create_field_success(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)

    response = db_client.post("/api/fields", json=_field_payload(farmer_id))

    assert response.status_code == 201
    body = response.json()
    assert body["farmer_id"] == farmer_id
    assert body["area_hectares"] > 0
    assert -90 <= body["centroid_latitude"] <= 90
    assert -180 <= body["centroid_longitude"] <= 180


def test_create_field_missing_farmer_returns_404(db_client: TestClient) -> None:
    response = db_client.post("/api/fields", json=_field_payload(999999))

    assert response.status_code == 404
    assert response.json()["code"] == "farmer_not_found"


def test_create_field_with_point_geometry_returns_422(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    payload = _field_payload(
        farmer_id, geojson_polygon={"type": "Point", "coordinates": [69.24, 41.30]}
    )

    response = db_client.post("/api/fields", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_geometry"


def test_create_field_with_unclosed_ring_returns_422(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    unclosed = {
        "type": "Polygon",
        "coordinates": [[[69.24, 41.30], [69.25, 41.30], [69.25, 41.31], [69.24, 41.31]]],
    }
    payload = _field_payload(farmer_id, geojson_polygon=unclosed)

    response = db_client.post("/api/fields", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_geometry"


def test_create_field_with_self_intersecting_polygon_returns_422(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
    payload = _field_payload(farmer_id, geojson_polygon=bowtie)

    response = db_client.post("/api/fields", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_geometry"


def test_create_field_with_invalid_dates_returns_422(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    payload = _field_payload(
        farmer_id, planting_date="2026-04-01", expected_harvest_date="2026-03-01"
    )

    response = db_client.post("/api/fields", json=payload)

    assert response.status_code == 422


def test_get_field_by_id(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    created = db_client.post("/api/fields", json=_field_payload(farmer_id)).json()

    response = db_client.get(f"/api/fields/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_field_returns_404(db_client: TestClient) -> None:
    response = db_client.get("/api/fields/999999")

    assert response.status_code == 404
    assert response.json()["code"] == "field_not_found"


def test_list_fields_pagination(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    for i in range(5):
        db_client.post("/api/fields", json=_field_payload(farmer_id, name=f"Dala {i}"))

    response = db_client.get(f"/api/fields?farmer_id={farmer_id}&limit=2&offset=0")
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 5
    assert body["limit"] == 2
    assert len(body["items"]) == 2

    second_page = db_client.get(f"/api/fields?farmer_id={farmer_id}&limit=2&offset=2").json()
    assert len(second_page["items"]) == 2
    assert {item["id"] for item in body["items"]}.isdisjoint(
        {item["id"] for item in second_page["items"]}
    )


def test_update_field_recomputes_area_from_new_polygon(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    created = db_client.post("/api/fields", json=_field_payload(farmer_id)).json()

    bigger_polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [69.2400, 41.3000],
                [69.2450, 41.3000],
                [69.2450, 41.3050],
                [69.2400, 41.3050],
                [69.2400, 41.3000],
            ]
        ],
    }
    response = db_client.patch(
        f"/api/fields/{created['id']}", json={"geojson_polygon": bigger_polygon}
    )

    assert response.status_code == 200
    assert response.json()["area_hectares"] > created["area_hectares"]


def test_update_field_with_invalid_dates_returns_422_and_leaves_field_unchanged(
    db_client: TestClient,
) -> None:
    farmer_id = _create_farmer(db_client)
    created = db_client.post(
        "/api/fields",
        json=_field_payload(farmer_id, planting_date="2026-04-01"),
    ).json()

    response = db_client.patch(
        f"/api/fields/{created['id']}", json={"expected_harvest_date": "2026-01-01"}
    )
    assert response.status_code == 422

    unchanged = db_client.get(f"/api/fields/{created['id']}").json()
    assert unchanged["expected_harvest_date"] is None
    assert unchanged["planting_date"] == "2026-04-01"


def test_delete_field(db_client: TestClient) -> None:
    farmer_id = _create_farmer(db_client)
    created = db_client.post("/api/fields", json=_field_payload(farmer_id)).json()

    delete_response = db_client.delete(f"/api/fields/{created['id']}")
    assert delete_response.status_code == 204

    get_response = db_client.get(f"/api/fields/{created['id']}")
    assert get_response.status_code == 404


def _irrigation_event_count(db_session: Session, field_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(IrrigationEvent)
        .where(IrrigationEvent.field_id == field_id)
    )
    return db_session.scalar(stmt) or 0


def _analysis_count(db_session: Session, field_id: int) -> int:
    stmt = select(func.count()).select_from(Analysis).where(Analysis.field_id == field_id)
    return db_session.scalar(stmt) or 0


def test_delete_field_cascades_to_irrigation_events_and_analyses(
    db_client: TestClient, db_session: Session
) -> None:
    """A deleted field must not leave orphaned irrigation_events/analyses
    rows behind (see backend/app/db/models/*.py ondelete=CASCADE + ORM
    cascade="all, delete-orphan") — verified in Phase 6's database audit."""
    farmer_id = _create_farmer(db_client)
    field_id = db_client.post("/api/fields", json=_field_payload(farmer_id)).json()["id"]

    irrigation_response = db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={
            "occurred_at": "2026-05-01T08:00:00",
            "amount_mm": 20,
            "value_source": "farmer_estimate",
        },
    )
    assert irrigation_response.status_code == 201

    analysis_response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-05-02"}
    )
    assert analysis_response.status_code == 201

    assert _irrigation_event_count(db_session, field_id) == 1
    assert _analysis_count(db_session, field_id) == 1

    delete_response = db_client.delete(f"/api/fields/{field_id}")
    assert delete_response.status_code == 204

    assert _irrigation_event_count(db_session, field_id) == 0
    assert _analysis_count(db_session, field_id) == 0
