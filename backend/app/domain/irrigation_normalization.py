"""Converts a farmer-recorded irrigation event into an estimated depth in mm.

Preference order when multiple inputs are present (most to least directly
measured): amount_mm > total_volume_m3 (+ field area) > duration_minutes +
flow_rate_m3_hour > qualitative_amount only. See docs/methodology.md.

    water_depth_mm = total_volume_m3 / field_area_hectares / 10

(1 mm over 1 hectare = 10 m3, so m3/ha already gives mm/10; dividing by the
extra 10 converts m3/ha into mm.)
"""

from dataclasses import dataclass, field
from enum import StrEnum


class IrrigationDepthSource(StrEnum):
    DIRECT_AMOUNT_MM = "direct_amount_mm"
    VOLUME_AND_AREA = "volume_and_area"
    DURATION_AND_FLOW_RATE = "duration_and_flow_rate"
    QUALITATIVE_ESTIMATE = "qualitative_estimate"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NormalizedIrrigation:
    depth_mm: float | None
    source: IrrigationDepthSource
    is_quantitative: bool
    warnings: list[str] = field(default_factory=list)


def volume_and_area_to_mm(total_volume_m3: float, field_area_hectares: float) -> float:
    if field_area_hectares <= 0:
        raise ValueError("field_area_hectares must be positive")
    if total_volume_m3 < 0:
        raise ValueError("total_volume_m3 must be non-negative")
    return total_volume_m3 / field_area_hectares / 10.0


def duration_and_flow_rate_to_mm(
    duration_minutes: float, flow_rate_m3_hour: float, field_area_hectares: float
) -> float:
    if duration_minutes < 0:
        raise ValueError("duration_minutes must be non-negative")
    if flow_rate_m3_hour < 0:
        raise ValueError("flow_rate_m3_hour must be non-negative")
    volume_m3 = flow_rate_m3_hour * (duration_minutes / 60.0)
    return volume_and_area_to_mm(volume_m3, field_area_hectares)


_RELATIVE_DISCREPANCY_THRESHOLD = 0.25


def normalize_irrigation_event(
    *,
    amount_mm: float | None,
    total_volume_m3: float | None,
    duration_minutes: float | None,
    flow_rate_m3_hour: float | None,
    qualitative_amount: str | None,
    field_area_hectares: float,
    qualitative_irrigation_mm: dict[str, float],
) -> NormalizedIrrigation:
    candidates: list[tuple[IrrigationDepthSource, float]] = []

    if amount_mm is not None:
        candidates.append((IrrigationDepthSource.DIRECT_AMOUNT_MM, amount_mm))
    if total_volume_m3 is not None:
        candidates.append(
            (
                IrrigationDepthSource.VOLUME_AND_AREA,
                volume_and_area_to_mm(total_volume_m3, field_area_hectares),
            )
        )
    if duration_minutes is not None and flow_rate_m3_hour is not None:
        candidates.append(
            (
                IrrigationDepthSource.DURATION_AND_FLOW_RATE,
                duration_and_flow_rate_to_mm(
                    duration_minutes, flow_rate_m3_hour, field_area_hectares
                ),
            )
        )

    warnings: list[str] = []

    if candidates:
        if len(candidates) > 1:
            values = [depth for _source, depth in candidates]
            if (
                min(values) > 0
                and (max(values) - min(values)) / min(values) > _RELATIVE_DISCREPANCY_THRESHOLD
            ):
                described = ", ".join(
                    f"{source.value}={depth:.1f}mm" for source, depth in candidates
                )
                warnings.append(
                    f"Irrigation event has inconsistent quantitative inputs ({described}); "
                    "using the most directly measured value."
                )
        # candidates is already in preference order (amount_mm > volume+area > duration+flow).
        chosen_source, chosen_depth = candidates[0]
        return NormalizedIrrigation(
            depth_mm=chosen_depth, source=chosen_source, is_quantitative=True, warnings=warnings
        )

    if qualitative_amount is not None:
        depth = qualitative_irrigation_mm.get(qualitative_amount)
        if depth is not None:
            warnings.append(
                f"Only a qualitative irrigation amount ('{qualitative_amount}') was recorded; "
                f"using a conservative configured estimate ({depth:.1f}mm) — this is a farmer "
                "estimate, not a measurement, and reduces confidence."
            )
            return NormalizedIrrigation(
                depth_mm=depth,
                source=IrrigationDepthSource.QUALITATIVE_ESTIMATE,
                is_quantitative=False,
                warnings=warnings,
            )

    warnings.append("No usable irrigation depth could be determined for this event.")
    return NormalizedIrrigation(
        depth_mm=None,
        source=IrrigationDepthSource.UNKNOWN,
        is_quantitative=False,
        warnings=warnings,
    )
