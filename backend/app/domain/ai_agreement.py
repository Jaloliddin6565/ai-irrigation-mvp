"""Deterministic AI Soil Wetness Index <-> FAO-56 water-balance agreement
engine (Phase 2).

Pure domain logic: no I/O, no randomness (CLAUDE.md rule 1). Compares an
FAO dryness signal — derived from the SAME depletion/RAW thresholds
app/domain/recommendation.py already uses to decide irrigation status, so
this is never a second, competing definition of "dry" — against the AI
Soil Wetness Index's own category, and returns a coarse, explainable
agreement verdict.

This module never computes or returns an irrigation depth, and nothing it
returns feeds back into recommended_min_mm/max_mm, the irrigation window,
TAW, RAW, or FAO depletion — see CLAUDE.md and PHASE 2 section 5. It only
classifies how well two INDEPENDENT signals corroborate each other.
"""

from dataclasses import dataclass
from enum import StrEnum


class DrynessSignal(StrEnum):
    DRY = "dry"
    MODERATE = "moderate"
    WET = "wet"


class AgreementStatus(StrEnum):
    AGREE = "agree"
    PARTIAL = "partial"
    DISAGREE = "disagree"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AgreementResult:
    status: AgreementStatus
    reason_code: str
    reason_text: str


# 3x3 grid over (fao_signal, ai_signal): diagonal = agree, one step apart =
# partial, opposite ends (dry vs wet) = disagree. Matches the PHASE 2
# section 4 examples exactly (FAO dry + AI dry -> agree; FAO wet + AI wet ->
# agree; FAO intermediate + AI dry -> partial; FAO strongly dry + AI wet ->
# disagree).
_GRID: dict[tuple[DrynessSignal, DrynessSignal], AgreementStatus] = {
    (DrynessSignal.DRY, DrynessSignal.DRY): AgreementStatus.AGREE,
    (DrynessSignal.MODERATE, DrynessSignal.MODERATE): AgreementStatus.AGREE,
    (DrynessSignal.WET, DrynessSignal.WET): AgreementStatus.AGREE,
    (DrynessSignal.DRY, DrynessSignal.MODERATE): AgreementStatus.PARTIAL,
    (DrynessSignal.MODERATE, DrynessSignal.DRY): AgreementStatus.PARTIAL,
    (DrynessSignal.MODERATE, DrynessSignal.WET): AgreementStatus.PARTIAL,
    (DrynessSignal.WET, DrynessSignal.MODERATE): AgreementStatus.PARTIAL,
    (DrynessSignal.DRY, DrynessSignal.WET): AgreementStatus.DISAGREE,
    (DrynessSignal.WET, DrynessSignal.DRY): AgreementStatus.DISAGREE,
}


def fao_dryness_signal_from_ratio(
    depletion_raw_ratio: float | None,
    *,
    monitor_threshold: float,
    irrigate_soon_threshold: float,
) -> DrynessSignal | None:
    """Reuses the exact depletion/RAW thresholds recommendation.py already
    applies (monitor_depletion_raw_ratio, irrigate_soon_depletion_raw_ratio)
    so the FAO side of this comparison always matches the recommendation
    the farmer actually sees. None (no water-balance depletion available,
    e.g. insufficient_data) means no FAO signal exists."""
    if depletion_raw_ratio is None:
        return None
    if depletion_raw_ratio < monitor_threshold:
        return DrynessSignal.WET
    if depletion_raw_ratio < irrigate_soon_threshold:
        return DrynessSignal.MODERATE
    return DrynessSignal.DRY


def determine_agreement(
    *,
    fao_signal: DrynessSignal | None,
    ai_status: str,
    ai_wetness_category: str | None,
) -> AgreementResult:
    if ai_status != "available" or ai_wetness_category is None:
        return AgreementResult(
            status=AgreementStatus.UNAVAILABLE,
            reason_code="ai_unavailable",
            reason_text=(
                "AI Soil Wetness Index is unavailable for this analysis; "
                "agreement cannot be computed."
            ),
        )
    if fao_signal is None:
        return AgreementResult(
            status=AgreementStatus.UNAVAILABLE,
            reason_code="fao_signal_unavailable",
            reason_text=(
                "FAO-56 water-balance depletion is unavailable for this analysis; "
                "agreement cannot be computed."
            ),
        )

    ai_signal = DrynessSignal(ai_wetness_category)
    status = _GRID[(fao_signal, ai_signal)]
    reason_code = f"fao_{fao_signal.value}_ai_{ai_signal.value}"
    reason_text = (
        f"FAO-56 water-balance signal is '{fao_signal.value}' and AI Soil Wetness Index "
        f"signal is '{ai_signal.value}' -> {status.value}."
    )
    return AgreementResult(status=status, reason_code=reason_code, reason_text=reason_text)
