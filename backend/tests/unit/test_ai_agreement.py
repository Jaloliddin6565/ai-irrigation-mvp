import pytest

from app.domain.ai_agreement import (
    AgreementStatus,
    DrynessSignal,
    determine_agreement,
    fao_dryness_signal_from_ratio,
)

MONITOR_THRESHOLD = 0.5
IRRIGATE_SOON_THRESHOLD = 0.8


@pytest.mark.parametrize(
    "ratio,expected",
    [
        (0.0, DrynessSignal.WET),
        (0.49, DrynessSignal.WET),
        (0.5, DrynessSignal.MODERATE),
        (0.79, DrynessSignal.MODERATE),
        (0.8, DrynessSignal.DRY),
        (1.5, DrynessSignal.DRY),
    ],
)
def test_fao_dryness_signal_reuses_recommendation_thresholds(
    ratio: float, expected: DrynessSignal
) -> None:
    assert (
        fao_dryness_signal_from_ratio(
            ratio,
            monitor_threshold=MONITOR_THRESHOLD,
            irrigate_soon_threshold=IRRIGATE_SOON_THRESHOLD,
        )
        == expected
    )


def test_fao_dryness_signal_is_none_when_ratio_is_none() -> None:
    assert (
        fao_dryness_signal_from_ratio(
            None,
            monitor_threshold=MONITOR_THRESHOLD,
            irrigate_soon_threshold=IRRIGATE_SOON_THRESHOLD,
        )
        is None
    )


@pytest.mark.parametrize(
    "fao_signal,ai_category,expected",
    [
        (DrynessSignal.DRY, "dry", AgreementStatus.AGREE),
        (DrynessSignal.MODERATE, "moderate", AgreementStatus.AGREE),
        (DrynessSignal.WET, "wet", AgreementStatus.AGREE),
        (DrynessSignal.DRY, "moderate", AgreementStatus.PARTIAL),
        (DrynessSignal.MODERATE, "dry", AgreementStatus.PARTIAL),
        (DrynessSignal.MODERATE, "wet", AgreementStatus.PARTIAL),
        (DrynessSignal.WET, "moderate", AgreementStatus.PARTIAL),
        (DrynessSignal.DRY, "wet", AgreementStatus.DISAGREE),
        (DrynessSignal.WET, "dry", AgreementStatus.DISAGREE),
    ],
)
def test_agreement_grid_matches_documented_examples(
    fao_signal: DrynessSignal, ai_category: str, expected: AgreementStatus
) -> None:
    result = determine_agreement(
        fao_signal=fao_signal, ai_status="available", ai_wetness_category=ai_category
    )
    assert result.status == expected
    assert result.reason_code == f"fao_{fao_signal.value}_ai_{ai_category}"


def test_agreement_is_unavailable_when_ai_status_is_unavailable() -> None:
    result = determine_agreement(
        fao_signal=DrynessSignal.DRY, ai_status="unavailable", ai_wetness_category=None
    )
    assert result.status == AgreementStatus.UNAVAILABLE
    assert result.reason_code == "ai_unavailable"


def test_agreement_is_unavailable_when_ai_category_missing_despite_available_status() -> None:
    result = determine_agreement(
        fao_signal=DrynessSignal.DRY, ai_status="available", ai_wetness_category=None
    )
    assert result.status == AgreementStatus.UNAVAILABLE
    assert result.reason_code == "ai_unavailable"


def test_agreement_is_unavailable_when_fao_signal_missing() -> None:
    result = determine_agreement(fao_signal=None, ai_status="available", ai_wetness_category="dry")
    assert result.status == AgreementStatus.UNAVAILABLE
    assert result.reason_code == "fao_signal_unavailable"


def test_agreement_is_unavailable_when_both_signals_missing() -> None:
    result = determine_agreement(fao_signal=None, ai_status="unavailable", ai_wetness_category=None)
    assert result.status == AgreementStatus.UNAVAILABLE
