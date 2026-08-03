"""Deterministic crop-stage determination.

Given planting_date, analysis_date, and a crop profile (backend/config/
crops.yaml), determines days-after-planting, the FAO-56-style growth stage,
the interpolated crop coefficient (Kc, dimensionless), estimated root depth
(metres), and the crop's depletion fraction (FAO-56 "p", dimensionless).
Pure function, no I/O, no randomness — see CLAUDE.md. Values are returned
at full precision; rounding happens only at the API/presentation boundary.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.db.models.enums import CropStage as CropStageOverride
from app.domain.config_loader import CropProfile


class CropGrowthStage(StrEnum):
    PRE_PLANTING = "pre_planting"
    INITIAL = "initial"
    DEVELOPMENT = "development"
    MID_SEASON = "mid_season"
    LATE_SEASON = "late_season"
    POST_SEASON = "post_season"


_OVERRIDE_TO_STAGE: dict[CropStageOverride, CropGrowthStage] = {
    CropStageOverride.INITIAL: CropGrowthStage.INITIAL,
    CropStageOverride.DEVELOPMENT: CropGrowthStage.DEVELOPMENT,
    CropStageOverride.MID: CropGrowthStage.MID_SEASON,
    CropStageOverride.LATE: CropGrowthStage.LATE_SEASON,
}


@dataclass(frozen=True)
class CropStageResult:
    days_after_planting: int
    stage: CropGrowthStage
    kc: float
    root_depth_m: float
    depletion_fraction: float
    stage_overridden: bool
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _stage_boundaries(profile: CropProfile) -> tuple[int, int, int, int]:
    lengths = profile.stage_lengths_days
    end_initial = int(lengths.initial)
    end_development = end_initial + int(lengths.development)
    end_mid = end_development + int(lengths.mid)
    end_late = end_mid + int(lengths.late)
    return end_initial, end_development, end_mid, end_late


def _interpolate(start_value: float, end_value: float, fraction: float) -> float:
    fraction = max(0.0, min(1.0, fraction))
    return start_value + fraction * (end_value - start_value)


def _kc_and_root_depth_for_stage(
    profile: CropProfile, stage: CropGrowthStage, fraction_within_stage: float
) -> tuple[float, float]:
    kc = profile.kc
    if stage is CropGrowthStage.PRE_PLANTING:
        return 0.0, profile.root_depth_initial_m
    if stage is CropGrowthStage.INITIAL:
        return kc.initial, profile.root_depth_initial_m
    if stage is CropGrowthStage.DEVELOPMENT:
        return (
            _interpolate(kc.initial, kc.mid, fraction_within_stage),
            _interpolate(
                profile.root_depth_initial_m, profile.root_depth_max_m, fraction_within_stage
            ),
        )
    if stage is CropGrowthStage.MID_SEASON:
        return kc.mid, profile.root_depth_max_m
    if stage is CropGrowthStage.LATE_SEASON:
        return _interpolate(kc.mid, kc.end, fraction_within_stage), profile.root_depth_max_m
    # POST_SEASON: hold at end-of-cycle values.
    return kc.end, profile.root_depth_max_m


def determine_crop_stage(
    *,
    planting_date: date,
    analysis_date: date,
    crop_profile: CropProfile,
    stage_override: CropStageOverride | None = None,
) -> CropStageResult:
    days_after_planting = (analysis_date - planting_date).days
    end_initial, end_development, end_mid, end_late = _stage_boundaries(crop_profile)

    if stage_override is not None:
        stage = _OVERRIDE_TO_STAGE[stage_override]
        # Day-level position within an overridden stage is unknown, so Kc
        # and root depth use the stage's midpoint as a documented,
        # defensible approximation rather than the calendar-derived
        # fraction.
        kc, root_depth_m = _kc_and_root_depth_for_stage(crop_profile, stage, 0.5)
        return CropStageResult(
            days_after_planting=days_after_planting,
            stage=stage,
            kc=kc,
            root_depth_m=root_depth_m,
            depletion_fraction=crop_profile.depletion_fraction,
            stage_overridden=True,
            assumptions=[
                f"crop_stage_override={stage.value} supplied; Kc and root depth computed at "
                "the stage midpoint rather than from days_after_planting."
            ],
        )

    if days_after_planting < 0:
        kc, root_depth_m = _kc_and_root_depth_for_stage(
            crop_profile, CropGrowthStage.PRE_PLANTING, 0.0
        )
        return CropStageResult(
            days_after_planting=days_after_planting,
            stage=CropGrowthStage.PRE_PLANTING,
            kc=kc,
            root_depth_m=root_depth_m,
            depletion_fraction=crop_profile.depletion_fraction,
            stage_overridden=False,
            warnings=[
                f"analysis_date is {abs(days_after_planting)} day(s) before planting_date; "
                "treating field as pre-planting (no crop water use applied)."
            ],
        )

    warnings: list[str] = []
    if days_after_planting < end_initial:
        stage = CropGrowthStage.INITIAL
        fraction = 0.0
    elif days_after_planting < end_development:
        stage = CropGrowthStage.DEVELOPMENT
        fraction = (days_after_planting - end_initial) / crop_profile.stage_lengths_days.development
    elif days_after_planting < end_mid:
        stage = CropGrowthStage.MID_SEASON
        fraction = 0.0
    elif days_after_planting < end_late:
        stage = CropGrowthStage.LATE_SEASON
        fraction = (days_after_planting - end_mid) / crop_profile.stage_lengths_days.late
    else:
        stage = CropGrowthStage.POST_SEASON
        fraction = 1.0
        warnings.append(
            f"analysis_date is {days_after_planting - end_late} day(s) beyond the documented "
            "crop cycle length; Kc held at Kc_end and root depth at maximum, with reduced "
            "confidence."
        )

    kc, root_depth_m = _kc_and_root_depth_for_stage(crop_profile, stage, fraction)

    return CropStageResult(
        days_after_planting=days_after_planting,
        stage=stage,
        kc=kc,
        root_depth_m=root_depth_m,
        depletion_fraction=crop_profile.depletion_fraction,
        stage_overridden=False,
        warnings=warnings,
    )
