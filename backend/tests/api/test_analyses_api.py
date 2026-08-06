import pytest
from fastapi.testclient import TestClient

from app.domain.initialization import InitializationMethod, InitializationResult
from app.schemas.analysis import DISCLAIMER_UZ

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


def _create_field(client: TestClient, **field_overrides) -> int:
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
    field_payload.update(field_overrides)
    return int(client.post("/api/fields", json=field_payload).json()["id"])


def test_successful_analysis_returns_full_structured_response(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["field_id"] == field_id
    assert body["analysis_date"] == "2026-06-01"
    assert body["data_mode"] == "fixture"
    assert body["recommendation"]["status"] in {
        "no_irrigation_needed",
        "monitor",
        "irrigate_soon",
        "irrigate_now",
        "delay_due_to_forecast_rain",
        "insufficient_data",
    }
    assert body["confidence"]["category"] in {"high", "medium", "low"}
    assert "crop_stage" in body
    assert "weather_summary" in body
    assert "satellite_summary" in body
    assert "water_balance_summary" in body


def test_analysis_never_claims_recommendation_as_a_single_precise_value(
    db_client: TestClient,
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    body = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    ).json()

    rec = body["recommendation"]
    if rec["status"] in ("irrigate_now", "irrigate_soon"):
        assert rec["recommended_max_mm"] > rec["recommended_min_mm"]


def test_analysis_includes_the_uzbek_disclaimer(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    body = db_client.post(f"/api/fields/{field_id}/analyze", json={}).json()
    assert body["disclaimer_uz"] == DISCLAIMER_UZ
    assert "tuproq namligini" in body["disclaimer_uz"]


def test_analyze_missing_field_returns_404(db_client: TestClient) -> None:
    response = db_client.post("/api/fields/999999/analyze", json={})
    assert response.status_code == 404
    assert response.json()["code"] == "field_not_found"


def test_analyze_invalid_analysis_date_returns_422(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "not-a-date"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_analysis_is_persisted_and_retrievable_by_id(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    created = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    ).json()

    retrieved = db_client.get(f"/api/fields/{field_id}/analyses/{created['id']}")

    assert retrieved.status_code == 200
    body = retrieved.json()
    assert body["id"] == created["id"]
    assert body["recommendation"]["status"] == created["recommendation"]["status"]
    assert body["confidence"]["score"] == created["confidence"]["score"]
    assert body["water_balance_summary"]["taw_mm"] == created["water_balance_summary"]["taw_mm"]


def test_get_missing_analysis_returns_404(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    response = db_client.get(f"/api/fields/{field_id}/analyses/999999")
    assert response.status_code == 404
    assert response.json()["code"] == "analysis_not_found"


def test_analysis_history_lists_all_runs_without_overwriting(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    first = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    ).json()
    second = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-02"}
    ).json()

    assert first["id"] != second["id"]

    history = db_client.get(f"/api/fields/{field_id}/analyses").json()
    assert history["total"] == 2
    ids = {item["id"] for item in history["items"]}
    assert ids == {first["id"], second["id"]}

    # Both remain independently retrievable — neither was overwritten.
    assert db_client.get(f"/api/fields/{field_id}/analyses/{first['id']}").status_code == 200
    assert db_client.get(f"/api/fields/{field_id}/analyses/{second['id']}").status_code == 200


def test_identical_analysis_input_produces_identical_calculation_output(
    db_client: TestClient,
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )

    first = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    ).json()
    second = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    ).json()

    assert first["id"] != second["id"]  # separate persisted records
    assert first["recommendation"]["status"] == second["recommendation"]["status"]
    assert (
        first["recommendation"]["recommended_min_mm"]
        == second["recommendation"]["recommended_min_mm"]
    )
    assert (
        first["recommendation"]["recommended_max_mm"]
        == second["recommendation"]["recommended_max_mm"]
    )
    assert first["confidence"]["score"] == second["confidence"]["score"]
    assert (
        first["water_balance_summary"]["depletion_mm"]
        == second["water_balance_summary"]["depletion_mm"]
    )


def test_insufficient_data_is_handled_gracefully_end_to_end(
    db_client: TestClient, monkeypatch
) -> None:
    """Fixture-mode weather always covers the requested window, so
    INSUFFICIENT_DATA can't be triggered through fixture data limitations
    alone — force it via the initialization strategy to verify the API
    still returns a well-formed response instead of a 500."""
    field_id = _create_field(db_client)

    def fake_insufficient(*args, **kwargs):
        return InitializationResult(
            method=InitializationMethod.INSUFFICIENT_DATA,
            start_date=None,
            starting_depletion_mm=None,
            uncertainty=1.0,
            warnings=["forced insufficient data for test"],
        )

    monkeypatch.setattr("app.services.analysis.determine_initialization", fake_insufficient)

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["recommendation"]["status"] == "insufficient_data"
    assert body["recommendation"]["recommended_min_mm"] == 0.0
    assert body["water_balance_summary"]["depletion_mm"] is None
    assert body["water_balance_summary"]["initialization"]["method"] == "insufficient_data"


def test_satellite_timeseries_endpoint_is_labelled_fixture_and_deterministic(
    db_client: TestClient,
) -> None:
    field_id = _create_field(db_client)

    first = db_client.get(f"/api/fields/{field_id}/satellite-timeseries")
    second = db_client.get(f"/api/fields/{field_id}/satellite-timeseries")

    assert first.status_code == 200
    body = first.json()
    assert body["data_mode"] == "fixture"
    assert len(body["observations"]) > 0
    assert first.json() == second.json()


def test_satellite_timeseries_missing_field_returns_404(db_client: TestClient) -> None:
    response = db_client.get("/api/fields/999999/satellite-timeseries")
    assert response.status_code == 404


def test_weather_endpoint_is_labelled_fixture_and_deterministic(db_client: TestClient) -> None:
    field_id = _create_field(db_client)

    first = db_client.get(f"/api/fields/{field_id}/weather")
    second = db_client.get(f"/api/fields/{field_id}/weather")

    assert first.status_code == 200
    body = first.json()
    assert body["data_mode"] == "fixture"
    assert len(body["days"]) > 0
    assert first.json() == second.json()


def test_weather_endpoint_missing_field_returns_404(db_client: TestClient) -> None:
    response = db_client.get("/api/fields/999999/weather")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "crop_type,soil_texture,irrigation_method",
    [
        ("wheat", "clay", "furrow"),
        ("orchard", "sandy_loam", "sprinkler"),
        ("vineyard", "sand", "basin"),
        ("vegetables", "unknown", "unknown"),
    ],
)
def test_analysis_succeeds_across_all_crop_soil_method_combinations(
    db_client: TestClient, crop_type: str, soil_texture: str, irrigation_method: str
) -> None:
    field_id = _create_field(
        db_client,
        crop_type=crop_type,
        soil_texture=soil_texture,
        irrigation_method=irrigation_method,
    )
    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )
    assert response.status_code == 201
