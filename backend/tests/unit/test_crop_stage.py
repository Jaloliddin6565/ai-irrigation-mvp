from datetime import date, timedelta

import pytest

from app.db.models.enums import CropStage as CropStageOverride
from app.domain.config_loader import get_agronomic_config
from app.domain.crop_stage import CropGrowthStage, determine_crop_stage

PLANTING = date(2026, 4, 1)


@pytest.fixture
def cotton():
    return get_agronomic_config().crops.crops["cotton"]


def test_pre_planting(cotton) -> None:
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=PLANTING - timedelta(days=7), crop_profile=cotton
    )
    assert result.stage == CropGrowthStage.PRE_PLANTING
    assert result.kc == 0.0
    assert result.days_after_planting == -7
    assert result.warnings


def test_planting_day_is_initial_stage(cotton) -> None:
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=PLANTING, crop_profile=cotton
    )
    assert result.stage == CropGrowthStage.INITIAL
    assert result.kc == cotton.kc.initial
    assert result.root_depth_m == cotton.root_depth_initial_m


def test_last_day_of_initial_stage_is_still_initial(cotton) -> None:
    last_initial_day = PLANTING + timedelta(days=int(cotton.stage_lengths_days.initial) - 1)
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=last_initial_day, crop_profile=cotton
    )
    assert result.stage == CropGrowthStage.INITIAL
    assert result.kc == cotton.kc.initial


def test_first_day_of_development_starts_at_kc_initial(cotton) -> None:
    first_dev_day = PLANTING + timedelta(days=int(cotton.stage_lengths_days.initial))
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=first_dev_day, crop_profile=cotton
    )
    assert result.stage == CropGrowthStage.DEVELOPMENT
    assert result.kc == pytest.approx(cotton.kc.initial)
    assert result.root_depth_m == pytest.approx(cotton.root_depth_initial_m)


def test_development_stage_interpolates_kc_and_root_depth_linearly(cotton) -> None:
    dev_length = int(cotton.stage_lengths_days.development)
    midpoint_day = PLANTING + timedelta(
        days=int(cotton.stage_lengths_days.initial) + dev_length // 2
    )
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=midpoint_day, crop_profile=cotton
    )
    expected_kc = (cotton.kc.initial + cotton.kc.mid) / 2
    expected_root_depth = (cotton.root_depth_initial_m + cotton.root_depth_max_m) / 2
    assert result.kc == pytest.approx(expected_kc, rel=0.05)
    assert result.root_depth_m == pytest.approx(expected_root_depth, rel=0.05)


def test_mid_season_kc_is_constant_and_root_depth_is_max(cotton) -> None:
    start_mid = PLANTING + timedelta(
        days=int(cotton.stage_lengths_days.initial) + int(cotton.stage_lengths_days.development)
    )
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=start_mid, crop_profile=cotton
    )
    assert result.stage == CropGrowthStage.MID_SEASON
    assert result.kc == cotton.kc.mid
    assert result.root_depth_m == cotton.root_depth_max_m


def test_late_season_interpolates_kc_from_mid_to_end(cotton) -> None:
    lengths = cotton.stage_lengths_days
    late_start = PLANTING + timedelta(days=int(lengths.initial + lengths.development + lengths.mid))
    late_midpoint = late_start + timedelta(days=int(lengths.late) // 2)
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=late_midpoint, crop_profile=cotton
    )
    assert result.stage == CropGrowthStage.LATE_SEASON
    expected_kc = (cotton.kc.mid + cotton.kc.end) / 2
    assert result.kc == pytest.approx(expected_kc, rel=0.05)
    assert result.root_depth_m == cotton.root_depth_max_m


def test_post_season_holds_kc_end_and_warns(cotton) -> None:
    lengths = cotton.stage_lengths_days
    total_days = int(lengths.initial + lengths.development + lengths.mid + lengths.late)
    after_cycle = PLANTING + timedelta(days=total_days + 15)
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=after_cycle, crop_profile=cotton
    )
    assert result.stage == CropGrowthStage.POST_SEASON
    assert result.kc == cotton.kc.end
    assert result.root_depth_m == cotton.root_depth_max_m
    assert result.warnings


@pytest.mark.parametrize(
    "override,expected_stage",
    [
        (CropStageOverride.INITIAL, CropGrowthStage.INITIAL),
        (CropStageOverride.DEVELOPMENT, CropGrowthStage.DEVELOPMENT),
        (CropStageOverride.MID, CropGrowthStage.MID_SEASON),
        (CropStageOverride.LATE, CropGrowthStage.LATE_SEASON),
    ],
)
def test_stage_override_replaces_calendar_derived_stage(cotton, override, expected_stage) -> None:
    # Pick an analysis date whose calendar-derived stage would normally be
    # "initial", to prove the override actually takes effect.
    result = determine_crop_stage(
        planting_date=PLANTING,
        analysis_date=PLANTING + timedelta(days=5),
        crop_profile=cotton,
        stage_override=override,
    )
    assert result.stage == expected_stage
    assert result.stage_overridden is True
    assert result.assumptions


def test_depletion_fraction_passes_through_from_crop_profile(cotton) -> None:
    result = determine_crop_stage(
        planting_date=PLANTING, analysis_date=PLANTING, crop_profile=cotton
    )
    assert result.depletion_fraction == cotton.depletion_fraction


def test_deterministic_repeated_calls_produce_identical_results(cotton) -> None:
    analysis_date = PLANTING + timedelta(days=40)
    first = determine_crop_stage(
        planting_date=PLANTING, analysis_date=analysis_date, crop_profile=cotton
    )
    second = determine_crop_stage(
        planting_date=PLANTING, analysis_date=analysis_date, crop_profile=cotton
    )
    assert first == second
