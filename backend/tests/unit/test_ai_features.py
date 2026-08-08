import math
from datetime import date, datetime, timedelta

import pytest

from app.ai.features import (
    FEATURE_ORDER_V0_1,
    FEATURE_ORDER_V0_2,
    RawDailyRecord,
    aggregate_hourly_to_daily,
    aggregate_root_zone_soil_moisture,
    build_feature_vector,
    build_rolling_feature_records,
    calculate_vpd_kpa,
    compute_location_climatology,
    feature_vector_to_array,
    wetness_index_from_value,
)
from app.ai.schemas import AIFeatureVector


def test_calculate_vpd_kpa_matches_manual_fao56_computation() -> None:
    # es(T) = 0.6108 * exp(17.27*T / (T+237.3)); es_day = mean(es(Tmax), es(Tmin))
    def es(t: float) -> float:
        return 0.6108 * math.exp((17.27 * t) / (t + 237.3))

    tmax, tmin, rh = 30.0, 15.0, 50.0
    expected_es = (es(tmax) + es(tmin)) / 2.0
    expected_vpd = expected_es - expected_es * (rh / 100.0)

    assert calculate_vpd_kpa(
        temperature_max_c=tmax, temperature_min_c=tmin, relative_humidity_mean_pct=rh
    ) == pytest.approx(expected_vpd, rel=1e-9)


def test_calculate_vpd_kpa_is_zero_at_100pct_humidity() -> None:
    vpd = calculate_vpd_kpa(
        temperature_max_c=25.0, temperature_min_c=25.0, relative_humidity_mean_pct=100.0
    )
    assert vpd == pytest.approx(0.0, abs=1e-9)


def test_calculate_vpd_kpa_rejects_max_below_min() -> None:
    with pytest.raises(ValueError, match="temperature_max_c"):
        calculate_vpd_kpa(
            temperature_max_c=10.0, temperature_min_c=20.0, relative_humidity_mean_pct=50.0
        )


def test_calculate_vpd_kpa_rejects_humidity_out_of_range() -> None:
    with pytest.raises(ValueError, match="relative_humidity_mean_pct"):
        calculate_vpd_kpa(
            temperature_max_c=20.0, temperature_min_c=10.0, relative_humidity_mean_pct=150.0
        )


def test_aggregate_hourly_to_daily_requires_full_day_by_default() -> None:
    day = date(2025, 6, 1)
    timestamps = [datetime(2025, 6, 1, h) for h in range(24)]
    values = [float(h) for h in range(24)]

    result = aggregate_hourly_to_daily(timestamps, values)

    assert result[day] == pytest.approx(sum(values) / 24)


def test_aggregate_hourly_to_daily_drops_incomplete_day() -> None:
    timestamps = [datetime(2025, 6, 1, h) for h in range(10)]  # only 10 of 24 hours
    values = [1.0] * 10

    result = aggregate_hourly_to_daily(timestamps, values)

    assert result == {}


def test_aggregate_hourly_to_daily_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        aggregate_hourly_to_daily([datetime(2025, 6, 1)], [1.0, 2.0])


def test_aggregate_hourly_to_daily_keeps_multiple_complete_days_separate() -> None:
    day1 = [datetime(2025, 6, 1, h) for h in range(24)]
    day2 = [datetime(2025, 6, 2, h) for h in range(24)]
    values1 = [1.0] * 24
    values2 = [2.0] * 24

    result = aggregate_hourly_to_daily(day1 + day2, values1 + values2)

    assert result[date(2025, 6, 1)] == pytest.approx(1.0)
    assert result[date(2025, 6, 2)] == pytest.approx(2.0)


def test_aggregate_root_zone_soil_moisture_applies_documented_depth_weights() -> None:
    # weights: shallow=19/72, deep=53/72 (see features.py docstring)
    shallow, deep = 0.20, 0.30
    expected = (19.0 / 72.0) * shallow + (53.0 / 72.0) * deep

    result = aggregate_root_zone_soil_moisture(
        soil_moisture_7_to_28cm_m3m3=shallow, soil_moisture_28_to_100cm_m3m3=deep
    )

    assert result == pytest.approx(expected)


def test_aggregate_root_zone_soil_moisture_is_identity_when_layers_equal() -> None:
    result = aggregate_root_zone_soil_moisture(
        soil_moisture_7_to_28cm_m3m3=0.25, soil_moisture_28_to_100cm_m3m3=0.25
    )
    assert result == pytest.approx(0.25)


def test_build_feature_vector_derives_day_of_year_and_month() -> None:
    vector = build_feature_vector(
        day=date(2025, 3, 15),
        latitude=41.3,
        longitude=69.2,
        et0_mm=5.0,
        precipitation_mm=0.0,
        temperature_max_c=20.0,
        temperature_min_c=5.0,
        temperature_mean_c=12.5,
        relative_humidity_mean_pct=45.0,
        wind_speed_ms=2.0,
        shortwave_radiation_mj_m2=18.0,
    )

    assert vector.day_of_year == date(2025, 3, 15).timetuple().tm_yday
    assert vector.month == 3
    assert vector.latitude == 41.3
    assert vector.longitude == 69.2
    assert vector.vpd_kpa > 0


def test_feature_vector_to_array_uses_requested_order() -> None:
    vector = AIFeatureVector(
        et0_mm=1.0,
        precipitation_mm=2.0,
        temperature_max_c=3.0,
        temperature_min_c=4.0,
        temperature_mean_c=5.0,
        relative_humidity_mean_pct=6.0,
        vpd_kpa=7.0,
        wind_speed_ms=8.0,
        shortwave_radiation_mj_m2=9.0,
        day_of_year=10,
        month=11,
        latitude=12.0,
        longitude=13.0,
    )

    array = feature_vector_to_array(vector, feature_order=FEATURE_ORDER_V0_1)

    assert array == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]


def test_feature_vector_to_array_rejects_unknown_field_name() -> None:
    vector = AIFeatureVector(
        et0_mm=1.0,
        precipitation_mm=2.0,
        temperature_max_c=3.0,
        temperature_min_c=4.0,
        temperature_mean_c=5.0,
        relative_humidity_mean_pct=6.0,
        vpd_kpa=7.0,
        wind_speed_ms=8.0,
        shortwave_radiation_mj_m2=9.0,
        day_of_year=10,
        month=11,
        latitude=12.0,
        longitude=13.0,
    )

    with pytest.raises(ValueError, match="missing"):
        feature_vector_to_array(vector, feature_order=["not_a_real_field"])


def _make_records(
    *,
    n_days: int,
    start: date = date(2025, 1, 1),
    precipitation_by_index: dict[int, float] | None = None,
) -> list[RawDailyRecord]:
    precipitation_by_index = precipitation_by_index or {}
    records = []
    for i in range(n_days):
        records.append(
            RawDailyRecord(
                location_id="test",
                date=start + timedelta(days=i),
                latitude=41.0,
                longitude=69.0,
                et0_mm=5.0,
                precipitation_mm=precipitation_by_index.get(i, 0.0),
                temperature_max_c=25.0,
                temperature_min_c=10.0,
                temperature_mean_c=17.5,
                relative_humidity_mean_pct=40.0,
                wind_speed_ms=2.0,
                shortwave_radiation_mj_m2=20.0,
                root_zone_soil_moisture_proxy_m3m3=0.2 + 0.001 * i,
            )
        )
    return records


def test_build_rolling_feature_records_drops_first_29_days() -> None:
    records = _make_records(n_days=40)

    result = build_rolling_feature_records(records)

    assert len(result) == 40 - 29
    assert result[0][0].date == records[29].date


def test_build_rolling_feature_records_computes_correct_sums() -> None:
    # precipitation of 1.0mm every 5th day; et0 fixed at 5.0mm/day.
    records = _make_records(n_days=40, precipitation_by_index={i: 1.0 for i in range(0, 30, 5)})

    first_record, first_vector = build_rolling_feature_records(records)[0]

    assert first_record.date == date(2025, 1, 30)
    # window (today=index29 back to index0) includes rainy day 25 within the
    # last 7 days (indices 23-29), but no rainy day within the last 3 (27-29).
    assert first_vector.precipitation_sum_3d == pytest.approx(0.0)
    assert first_vector.precipitation_sum_7d == pytest.approx(1.0)
    assert first_vector.precipitation_sum_30d == pytest.approx(6.0)  # 6 rainy days in window
    assert first_vector.et0_sum_7d == pytest.approx(35.0)
    assert first_vector.precipitation_minus_et0_7d == pytest.approx(1.0 - 35.0)
    # deficit = max(et0-precip, 0) per day; 6 days at (5-1)=4, 24 days at 5
    assert first_vector.cumulative_water_deficit_30d == pytest.approx(6 * 4.0 + 24 * 5.0)


def test_build_rolling_feature_records_never_uses_future_data() -> None:
    """No-future-leakage: two series identical up to day 29 but diverging
    wildly afterwards must produce IDENTICAL rolling features for day 29."""
    base = _make_records(n_days=40)
    diverged = _make_records(n_days=40, precipitation_by_index={i: 500.0 for i in range(31, 40)})

    base_result = build_rolling_feature_records(base)
    diverged_result = build_rolling_feature_records(diverged)

    base_day29 = next(v for r, v in base_result if r.date == date(2025, 1, 30))
    diverged_day29 = next(v for r, v in diverged_result if r.date == date(2025, 1, 30))

    assert base_day29 == diverged_day29


def test_build_rolling_feature_records_drops_rows_spanning_a_missing_day() -> None:
    records = _make_records(n_days=40)
    # Remove day index 15 entirely -- any 30-day window spanning it must be dropped.
    without_day15 = [r for i, r in enumerate(records) if i != 15]

    result = build_rolling_feature_records(without_day15)

    # No output row's 30-day window may contain the missing date.
    missing_date = records[15].date
    for record, _ in result:
        window = {record.date - timedelta(days=k) for k in range(30)}
        assert missing_date not in window


def test_build_rolling_feature_records_is_deterministic() -> None:
    records = _make_records(n_days=40, precipitation_by_index={5: 3.0, 20: 7.0})

    result_a = build_rolling_feature_records(records)
    result_b = build_rolling_feature_records(records)

    assert [v for _, v in result_a] == [v for _, v in result_b]


def test_feature_order_v0_2_extends_v0_1_and_has_thirty_features() -> None:
    assert FEATURE_ORDER_V0_2[: len(FEATURE_ORDER_V0_1)] == FEATURE_ORDER_V0_1
    assert len(FEATURE_ORDER_V0_2) == 30
    assert len(set(FEATURE_ORDER_V0_2)) == 30  # no duplicate feature names


def test_compute_location_climatology_returns_observed_min_max() -> None:
    records = _make_records(n_days=10)

    lo, hi = compute_location_climatology(records)

    values = [r.root_zone_soil_moisture_proxy_m3m3 for r in records]
    assert lo == pytest.approx(min(values))
    assert hi == pytest.approx(max(values))


def test_compute_location_climatology_rejects_empty_series() -> None:
    with pytest.raises(ValueError, match="empty"):
        compute_location_climatology([])


def test_wetness_index_from_value_maps_range_to_zero_one() -> None:
    bounds = {"location_min": 0.20, "location_max": 0.30}
    assert wetness_index_from_value(0.20, **bounds) == pytest.approx(0.0)
    assert wetness_index_from_value(0.30, **bounds) == pytest.approx(1.0)
    assert wetness_index_from_value(0.25, **bounds) == pytest.approx(0.5)


def test_wetness_index_from_value_clamps_outside_observed_range() -> None:
    bounds = {"location_min": 0.20, "location_max": 0.30}
    assert wetness_index_from_value(0.10, **bounds) == pytest.approx(0.0)
    assert wetness_index_from_value(0.40, **bounds) == pytest.approx(1.0)


def test_wetness_index_from_value_handles_degenerate_zero_range() -> None:
    result = wetness_index_from_value(0.25, location_min=0.25, location_max=0.25)
    assert result == pytest.approx(0.5)
