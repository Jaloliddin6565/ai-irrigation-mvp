from fastapi.testclient import TestClient

from app.ai.inference import AIInferenceResult
from app.services import analysis as analysis_service

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


def _analyze(client: TestClient, field_id: int, analysis_date: str = "2026-06-01") -> dict:
    response = client.post(f"/api/fields/{field_id}/analyze", json={"analysis_date": analysis_date})
    assert response.status_code == 201
    return response.json()


def test_ai_summary_is_present_and_well_shaped(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    body = _analyze(db_client, field_id)

    ai = body["ai_summary"]
    assert ai["model_name"] == "AI Soil Wetness Index"
    assert ai["status"] in {"available", "unavailable"}
    assert ai["data_basis"] == "public_model_precalibration"
    assert ai["validation_status"] == "not_sensor_validated"
    assert ai["agreement_with_fao"] in {"agree", "partial", "disagree", "unavailable"}
    assert ai["confidence_effect"] in {"agree_bonus", "disagree_penalty", "none"}
    if ai["status"] == "available":
        assert 0.0 <= ai["wetness_index"] <= 1.0
        assert ai["wetness_category"] in {"dry", "moderate", "wet"}
    else:
        assert ai["wetness_index"] is None
        assert ai["wetness_category"] is None


def test_ai_summary_never_claims_direct_soil_moisture_measurement(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    body = _analyze(db_client, field_id)
    ai = body["ai_summary"]

    forbidden_phrases = ["measured soil moisture", "sensor-equivalent soil moisture"]
    haystack = " ".join(
        ai.get("limitations", []) + ai.get("reasons", []) + ai.get("warnings", [])
    ).lower()
    for phrase in forbidden_phrases:
        assert phrase not in haystack


def test_fixture_mode_ai_summary_is_deterministic_across_repeated_calls(
    db_client: TestClient,
) -> None:
    field_id = _create_field(db_client)
    first = _analyze(db_client, field_id, "2026-06-01")
    second = _analyze(db_client, field_id, "2026-06-01")

    assert first["ai_summary"] == second["ai_summary"]


def test_persisted_ai_summary_is_returned_unchanged_on_re_fetch(db_client: TestClient) -> None:
    field_id = _create_field(db_client)
    created = _analyze(db_client, field_id)
    analysis_id = created["id"]

    fetched = db_client.get(f"/api/fields/{field_id}/analyses/{analysis_id}").json()

    assert fetched["ai_summary"] == created["ai_summary"]


def test_ai_unavailable_leaves_recommended_water_depth_taw_raw_and_window_unchanged(
    db_client: TestClient, monkeypatch
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )

    baseline = _analyze(db_client, field_id)

    def _forced_unavailable(**_kwargs) -> AIInferenceResult:
        return AIInferenceResult(
            status="unavailable",
            model_version="unknown",
            wetness_index=None,
            wetness_category=None,
            feature_timestamp=None,
            unavailable_reason_code="forced_unavailable_for_test",
        )

    monkeypatch.setattr(analysis_service, "run_ai_inference", _forced_unavailable)
    forced = _analyze(db_client, field_id)

    # AI availability differs, proving the patch took effect...
    assert forced["ai_summary"]["status"] == "unavailable"
    assert forced["ai_summary"]["agreement_with_fao"] == "unavailable"

    # ...but the FAO-56 deterministic outputs are byte-identical regardless
    # (CLAUDE.md / PHASE 2 section 5: AI must never control water depth).
    rec_a, rec_b = baseline["recommendation"], forced["recommendation"]
    assert rec_a["recommended_min_mm"] == rec_b["recommended_min_mm"]
    assert rec_a["recommended_max_mm"] == rec_b["recommended_max_mm"]
    assert rec_a["recommended_min_m3_per_ha"] == rec_b["recommended_min_m3_per_ha"]
    assert rec_a["recommended_max_m3_per_ha"] == rec_b["recommended_max_m3_per_ha"]
    assert rec_a["window_start_date"] == rec_b["window_start_date"]
    assert rec_a["window_end_date"] == rec_b["window_end_date"]
    assert rec_a["status"] == rec_b["status"]

    wb_a, wb_b = baseline["water_balance_summary"], forced["water_balance_summary"]
    assert wb_a["taw_mm"] == wb_b["taw_mm"]
    assert wb_a["raw_mm"] == wb_b["raw_mm"]
    assert wb_a["depletion_mm"] == wb_b["depletion_mm"]


def test_ai_failure_response_contains_no_secrets_or_stack_traces(
    db_client: TestClient, monkeypatch
) -> None:
    field_id = _create_field(db_client)

    def _raise(**_kwargs):
        raise RuntimeError("Authorization: Bearer should-never-appear-in-response")

    monkeypatch.setattr(analysis_service, "run_ai_inference", _raise)

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    # The deterministic FAO-56 analysis must still succeed even though the
    # AI call raised unexpectedly (CLAUDE.md / PHASE 2 section 8).
    assert response.status_code == 201
    body = response.json()
    assert body["ai_summary"]["status"] == "unavailable"
    raw_text = response.text
    assert "Bearer" not in raw_text
    assert "Traceback" not in raw_text
    assert "should-never-appear-in-response" not in raw_text
