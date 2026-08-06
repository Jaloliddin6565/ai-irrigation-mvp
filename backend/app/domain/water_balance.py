"""Deterministic daily FAO-56-style root-zone water balance.

All water depths are millimetres (mm) = litres per m². Root depth is
metres (m). field_capacity/wilting_point are volumetric fractions (m3/m3).
Nothing here uses randomness or wall-clock time — see CLAUDE.md. Values are
carried at full float precision through the whole daily loop; rounding
happens only at the API/presentation boundary (see docs/methodology.md for
why plain floats, not Decimal, are precise enough here).

Core equations (see docs/methodology.md for the full derivation):
    ETc = Kc x ET0
    effective_precipitation = precipitation x effective_precipitation_factor
    effective_irrigation = irrigation_mm x irrigation_efficiency
    TAW = 1000 x (field_capacity - wilting_point) x root_depth_m
    RAW = depletion_fraction x TAW
    depletion_today = clamp(depletion_previous + ETc - effective_precipitation
                             - effective_irrigation, 0, TAW)

Kc and root depth are recomputed per day from the crop-stage engine (a crop
growing through development changes both day by day), unless
root_depth_override_m is supplied, in which case root depth is held fixed
at that value for every day. When TAW grows because root depth grows, the
newly available root-zone layer is assumed to enter at field capacity (it
does not retroactively increase yesterday's depletion) — a documented,
conservative simplification for this MVP.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.db.models.enums import CropStage as CropStageOverride
from app.domain.config_loader import CropProfile
from app.domain.crop_stage import determine_crop_stage


def compute_etc(kc: float, et0_mm: float) -> float:
    if et0_mm < 0:
        raise ValueError("et0_mm must be non-negative")
    if kc < 0:
        raise ValueError("kc must be non-negative")
    return kc * et0_mm


def compute_effective_precipitation(precipitation_mm: float, factor: float) -> float:
    if precipitation_mm < 0:
        raise ValueError("precipitation_mm must be non-negative")
    return precipitation_mm * factor


def compute_effective_irrigation(irrigation_mm: float, efficiency: float) -> float:
    if irrigation_mm < 0:
        raise ValueError("irrigation_mm must be non-negative")
    return irrigation_mm * efficiency


def compute_taw(field_capacity: float, wilting_point: float, root_depth_m: float) -> float:
    if field_capacity <= wilting_point:
        raise ValueError("field_capacity must be greater than wilting_point")
    if root_depth_m <= 0:
        raise ValueError("root_depth_m must be positive")
    return 1000.0 * (field_capacity - wilting_point) * root_depth_m


def compute_raw(taw_mm: float, depletion_fraction: float) -> float:
    if not (0.0 < depletion_fraction <= 1.0):
        raise ValueError("depletion_fraction must be in (0, 1]")
    return depletion_fraction * taw_mm


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def advance_depletion(
    *,
    depletion_previous_mm: float,
    etc_mm: float,
    effective_precipitation_mm: float,
    effective_irrigation_mm: float,
    taw_mm: float,
) -> float:
    raw_next = depletion_previous_mm + etc_mm - effective_precipitation_mm - effective_irrigation_mm
    return clamp(raw_next, 0.0, taw_mm)


@dataclass(frozen=True)
class DailyInputs:
    et0_mm: float | None = None
    precipitation_mm: float | None = None
    irrigation_mm: float = 0.0


@dataclass(frozen=True)
class DailyWaterBalanceRow:
    date: date
    stage: str
    kc: float
    root_depth_m: float
    taw_mm: float
    raw_mm: float
    et0_mm: float
    etc_mm: float
    precipitation_mm: float
    effective_precipitation_mm: float
    irrigation_mm: float
    effective_irrigation_mm: float
    depletion_start_mm: float
    depletion_end_mm: float
    is_missing_weather: bool = False


@dataclass(frozen=True)
class WaterBalanceRunResult:
    rows: list[DailyWaterBalanceRow]
    final_depletion_mm: float
    final_taw_mm: float
    final_raw_mm: float
    warnings: list[str] = field(default_factory=list)


def run_daily_water_balance(
    *,
    planting_date: date,
    crop_profile: CropProfile,
    stage_override: CropStageOverride | None,
    field_capacity: float,
    wilting_point: float,
    root_depth_override_m: float | None,
    irrigation_efficiency: float,
    effective_precipitation_factor: float,
    start_date: date,
    end_date: date,
    initial_depletion_mm: float,
    daily_inputs: Mapping[date, DailyInputs],
) -> WaterBalanceRunResult:
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")

    rows: list[DailyWaterBalanceRow] = []
    warnings: list[str] = []
    depletion = initial_depletion_mm
    current = start_date

    while current <= end_date:
        stage_result = determine_crop_stage(
            planting_date=planting_date,
            analysis_date=current,
            crop_profile=crop_profile,
            stage_override=stage_override,
        )
        root_depth_m = (
            root_depth_override_m
            if root_depth_override_m is not None
            else stage_result.root_depth_m
        )
        taw_mm = compute_taw(field_capacity, wilting_point, root_depth_m)
        raw_mm = compute_raw(taw_mm, stage_result.depletion_fraction)
        # Depletion carried over in absolute mm even when TAW grows day over
        # day — see module docstring.
        depletion = clamp(depletion, 0.0, taw_mm)

        day_input = daily_inputs.get(current)
        if day_input is None or day_input.et0_mm is None or day_input.precipitation_mm is None:
            is_missing = True
            warnings.append(
                f"Missing weather data for {current.isoformat()}; treated as zero ET0/"
                "precipitation for that day (conservative approximation — may understate "
                "depletion)."
            )
            et0_mm = 0.0
            precipitation_mm = 0.0
            irrigation_mm = day_input.irrigation_mm if day_input is not None else 0.0
        else:
            is_missing = False
            et0_mm = day_input.et0_mm
            precipitation_mm = day_input.precipitation_mm
            irrigation_mm = day_input.irrigation_mm

        etc_mm = compute_etc(stage_result.kc, et0_mm)
        effective_precipitation_mm = compute_effective_precipitation(
            precipitation_mm, effective_precipitation_factor
        )
        effective_irrigation_mm = compute_effective_irrigation(irrigation_mm, irrigation_efficiency)

        depletion_start = depletion
        depletion_end = advance_depletion(
            depletion_previous_mm=depletion_start,
            etc_mm=etc_mm,
            effective_precipitation_mm=effective_precipitation_mm,
            effective_irrigation_mm=effective_irrigation_mm,
            taw_mm=taw_mm,
        )

        rows.append(
            DailyWaterBalanceRow(
                date=current,
                stage=stage_result.stage.value,
                kc=stage_result.kc,
                root_depth_m=root_depth_m,
                taw_mm=taw_mm,
                raw_mm=raw_mm,
                et0_mm=et0_mm,
                etc_mm=etc_mm,
                precipitation_mm=precipitation_mm,
                effective_precipitation_mm=effective_precipitation_mm,
                irrigation_mm=irrigation_mm,
                effective_irrigation_mm=effective_irrigation_mm,
                depletion_start_mm=depletion_start,
                depletion_end_mm=depletion_end,
                is_missing_weather=is_missing,
            )
        )

        depletion = depletion_end
        current += timedelta(days=1)

    last = rows[-1]
    return WaterBalanceRunResult(
        rows=rows,
        final_depletion_mm=last.depletion_end_mm,
        final_taw_mm=last.taw_mm,
        final_raw_mm=last.raw_mm,
        warnings=warnings,
    )
