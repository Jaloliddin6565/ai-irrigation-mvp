from datetime import date

from app.providers.satellite.quality import SatelliteQualityStatus, classify_observation


def _kwargs(**overrides: object) -> dict:
    base = dict(
        valid_pixel_ratio=0.9,
        invalid_pixel_percentage=10.0,
        acquisition_date=date(2026, 6, 1),
        as_of=date(2026, 6, 1),
        index_values=[0.1, 0.2, 0.3],
        min_valid_pixel_ratio=0.6,
        max_observation_age_days=30,
    )
    base.update(overrides)
    return base


def test_usable_observation() -> None:
    result = classify_observation(**_kwargs())
    assert result.status == SatelliteQualityStatus.USABLE
    assert result.is_usable


def test_nan_value_is_rejected() -> None:
    result = classify_observation(**_kwargs(index_values=[0.1, float("nan")]))
    assert result.status == SatelliteQualityStatus.NON_FINITE_VALUES
    assert not result.is_usable


def test_infinite_value_is_rejected() -> None:
    result = classify_observation(**_kwargs(index_values=[float("inf")]))
    assert result.status == SatelliteQualityStatus.NON_FINITE_VALUES


def test_future_acquisition_date_is_malformed() -> None:
    result = classify_observation(
        **_kwargs(acquisition_date=date(2026, 6, 5), as_of=date(2026, 6, 1))
    )
    assert result.status == SatelliteQualityStatus.MALFORMED_RESPONSE


def test_low_valid_pixel_ratio_is_rejected() -> None:
    result = classify_observation(**_kwargs(valid_pixel_ratio=0.3))
    assert result.status == SatelliteQualityStatus.LOW_VALID_PIXEL_RATIO


def test_valid_pixel_ratio_exactly_at_minimum_is_usable() -> None:
    result = classify_observation(**_kwargs(valid_pixel_ratio=0.6, min_valid_pixel_ratio=0.6))
    assert result.status == SatelliteQualityStatus.USABLE


def test_cloud_contaminated_is_rejected() -> None:
    result = classify_observation(**_kwargs(invalid_pixel_percentage=80.0))
    assert result.status == SatelliteQualityStatus.CLOUD_CONTAMINATED


def test_stale_observation_is_rejected() -> None:
    result = classify_observation(
        **_kwargs(
            acquisition_date=date(2026, 4, 1), as_of=date(2026, 6, 1), max_observation_age_days=30
        )
    )
    assert result.status == SatelliteQualityStatus.STALE


def test_no_max_age_configured_means_never_stale() -> None:
    result = classify_observation(
        **_kwargs(
            acquisition_date=date(2025, 1, 1),
            as_of=date(2026, 6, 1),
            max_observation_age_days=None,
        )
    )
    assert result.status == SatelliteQualityStatus.USABLE


def test_non_finite_check_wins_over_low_pixel_ratio() -> None:
    result = classify_observation(**_kwargs(valid_pixel_ratio=0.1, index_values=[float("nan")]))
    assert result.status == SatelliteQualityStatus.NON_FINITE_VALUES


def test_warnings_are_present_on_rejection() -> None:
    result = classify_observation(**_kwargs(valid_pixel_ratio=0.1))
    assert result.warnings
    assert result.rejection_reason == "low_valid_pixel_ratio"


def test_usable_observation_has_no_warnings() -> None:
    result = classify_observation(**_kwargs())
    assert result.warnings == []
    assert result.rejection_reason is None
