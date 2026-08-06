from datetime import date, timedelta

import pytest

from app.domain.config_loader import get_agronomic_config
from app.domain.water_balance import (
    DailyInputs,
    advance_depletion,
    clamp,
    compute_effective_irrigation,
    compute_effective_precipitation,
    compute_etc,
    compute_raw,
    compute_taw,
    run_daily_water_balance,
)

PLANTING = date(2026, 4, 1)


@pytest.fixture
def cotton():
    return get_agronomic_config().crops.crops["cotton"]


@pytest.fixture
def loam():
    return get_agronomic_config().soils.soils["loam"]


@pytest.fixture
def drip_efficiency():
    return get_agronomic_config().irrigation_methods.irrigation_methods["drip"].efficiency


def test_compute_etc() -> None:
    assert compute_etc(kc=1.0, et0_mm=5.0) == 5.0
    assert compute_etc(kc=0.5, et0_mm=4.0) == 2.0


def test_compute_etc_rejects_negative_et0() -> None:
    with pytest.raises(ValueError, match="et0_mm"):
        compute_etc(kc=1.0, et0_mm=-1.0)


def test_compute_effective_precipitation_rejects_negative() -> None:
    with pytest.raises(ValueError, match="precipitation_mm"):
        compute_effective_precipitation(-1.0, factor=0.8)


def test_compute_effective_irrigation_rejects_negative() -> None:
    with pytest.raises(ValueError, match="irrigation_mm"):
        compute_effective_irrigation(-1.0, efficiency=0.9)


def test_compute_taw() -> None:
    # 1000 * (0.28 - 0.14) * 1.0 = 140
    assert compute_taw(field_capacity=0.28, wilting_point=0.14, root_depth_m=1.0) == pytest.approx(
        140.0
    )


def test_compute_taw_rejects_field_capacity_not_greater_than_wilting_point() -> None:
    with pytest.raises(ValueError, match="field_capacity"):
        compute_taw(field_capacity=0.1, wilting_point=0.2, root_depth_m=1.0)


def test_compute_taw_rejects_non_positive_root_depth() -> None:
    with pytest.raises(ValueError, match="root_depth_m"):
        compute_taw(field_capacity=0.3, wilting_point=0.1, root_depth_m=0.0)


def test_compute_raw() -> None:
    assert compute_raw(taw_mm=140.0, depletion_fraction=0.5) == 70.0


def test_clamp() -> None:
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10


def test_advance_depletion_accumulates() -> None:
    depletion = advance_depletion(
        depletion_previous_mm=10.0,
        etc_mm=5.0,
        effective_precipitation_mm=0.0,
        effective_irrigation_mm=0.0,
        taw_mm=100.0,
    )
    assert depletion == 15.0


def test_advance_depletion_clamps_at_zero() -> None:
    depletion = advance_depletion(
        depletion_previous_mm=5.0,
        etc_mm=0.0,
        effective_precipitation_mm=50.0,
        effective_irrigation_mm=0.0,
        taw_mm=100.0,
    )
    assert depletion == 0.0


def test_advance_depletion_clamps_at_taw() -> None:
    depletion = advance_depletion(
        depletion_previous_mm=90.0,
        etc_mm=50.0,
        effective_precipitation_mm=0.0,
        effective_irrigation_mm=0.0,
        taw_mm=100.0,
    )
    assert depletion == 100.0


def test_daily_loop_accumulates_depletion_with_no_water_input(
    cotton, loam, drip_efficiency
) -> None:
    start = PLANTING + timedelta(days=50)
    end = start + timedelta(days=4)
    daily_inputs = {
        start + timedelta(days=i): DailyInputs(et0_mm=5.0, precipitation_mm=0.0) for i in range(5)
    }

    result = run_daily_water_balance(
        planting_date=PLANTING,
        crop_profile=cotton,
        stage_override=None,
        field_capacity=loam.field_capacity,
        wilting_point=loam.wilting_point,
        root_depth_override_m=None,
        irrigation_efficiency=drip_efficiency,
        effective_precipitation_factor=0.8,
        start_date=start,
        end_date=end,
        initial_depletion_mm=0.0,
        daily_inputs=daily_inputs,
    )

    assert len(result.rows) == 5
    # Depletion should increase monotonically with no rain/irrigation.
    depletions = [row.depletion_end_mm for row in result.rows]
    assert depletions == sorted(depletions)
    assert depletions[-1] > 0
    assert result.final_depletion_mm == depletions[-1]
    assert not result.warnings


def test_irrigation_reduces_depletion(cotton, loam, drip_efficiency) -> None:
    day = PLANTING + timedelta(days=60)
    no_irrigation = run_daily_water_balance(
        planting_date=PLANTING,
        crop_profile=cotton,
        stage_override=None,
        field_capacity=loam.field_capacity,
        wilting_point=loam.wilting_point,
        root_depth_override_m=None,
        irrigation_efficiency=drip_efficiency,
        effective_precipitation_factor=0.8,
        start_date=day,
        end_date=day,
        initial_depletion_mm=20.0,
        daily_inputs={day: DailyInputs(et0_mm=5.0, precipitation_mm=0.0, irrigation_mm=0.0)},
    )
    with_irrigation = run_daily_water_balance(
        planting_date=PLANTING,
        crop_profile=cotton,
        stage_override=None,
        field_capacity=loam.field_capacity,
        wilting_point=loam.wilting_point,
        root_depth_override_m=None,
        irrigation_efficiency=drip_efficiency,
        effective_precipitation_factor=0.8,
        start_date=day,
        end_date=day,
        initial_depletion_mm=20.0,
        daily_inputs={day: DailyInputs(et0_mm=5.0, precipitation_mm=0.0, irrigation_mm=15.0)},
    )
    assert with_irrigation.final_depletion_mm < no_irrigation.final_depletion_mm


def test_root_depth_override_holds_constant_across_all_stages(
    cotton, loam, drip_efficiency
) -> None:
    start = PLANTING  # initial stage
    end = PLANTING + timedelta(days=90)  # well into mid-season
    daily_inputs = {}
    d = start
    while d <= end:
        daily_inputs[d] = DailyInputs(et0_mm=3.0, precipitation_mm=0.0)
        d += timedelta(days=1)

    result = run_daily_water_balance(
        planting_date=PLANTING,
        crop_profile=cotton,
        stage_override=None,
        field_capacity=loam.field_capacity,
        wilting_point=loam.wilting_point,
        root_depth_override_m=0.9,
        irrigation_efficiency=drip_efficiency,
        effective_precipitation_factor=0.8,
        start_date=start,
        end_date=end,
        initial_depletion_mm=0.0,
        daily_inputs=daily_inputs,
    )

    assert all(row.root_depth_m == 0.9 for row in result.rows)


def test_missing_weather_day_is_a_no_op_with_warning(cotton, loam, drip_efficiency) -> None:
    day = PLANTING + timedelta(days=50)
    result = run_daily_water_balance(
        planting_date=PLANTING,
        crop_profile=cotton,
        stage_override=None,
        field_capacity=loam.field_capacity,
        wilting_point=loam.wilting_point,
        root_depth_override_m=None,
        irrigation_efficiency=drip_efficiency,
        effective_precipitation_factor=0.8,
        start_date=day,
        end_date=day,
        initial_depletion_mm=12.0,
        daily_inputs={},
    )
    assert result.rows[0].is_missing_weather is True
    assert result.rows[0].depletion_end_mm == 12.0
    assert result.warnings


def test_end_date_before_start_date_raises(cotton, loam, drip_efficiency) -> None:
    day = PLANTING + timedelta(days=10)
    with pytest.raises(ValueError, match="end_date"):
        run_daily_water_balance(
            planting_date=PLANTING,
            crop_profile=cotton,
            stage_override=None,
            field_capacity=loam.field_capacity,
            wilting_point=loam.wilting_point,
            root_depth_override_m=None,
            irrigation_efficiency=drip_efficiency,
            effective_precipitation_factor=0.8,
            start_date=day,
            end_date=day - timedelta(days=1),
            initial_depletion_mm=0.0,
            daily_inputs={},
        )


def test_deterministic_repeated_runs_produce_identical_output(
    cotton, loam, drip_efficiency
) -> None:
    start = PLANTING + timedelta(days=50)
    end = start + timedelta(days=9)
    daily_inputs = {
        start + timedelta(days=i): DailyInputs(
            et0_mm=4.5, precipitation_mm=1.0 if i % 3 == 0 else 0.0
        )
        for i in range(10)
    }

    kwargs = dict(
        planting_date=PLANTING,
        crop_profile=cotton,
        stage_override=None,
        field_capacity=loam.field_capacity,
        wilting_point=loam.wilting_point,
        root_depth_override_m=None,
        irrigation_efficiency=drip_efficiency,
        effective_precipitation_factor=0.8,
        start_date=start,
        end_date=end,
        initial_depletion_mm=10.0,
        daily_inputs=daily_inputs,
    )

    first = run_daily_water_balance(**kwargs)
    second = run_daily_water_balance(**kwargs)
    assert first == second
