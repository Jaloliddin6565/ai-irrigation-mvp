from datetime import date, timedelta

from app.domain.satellite_adjustment import (
    SatelliteDataQuality,
    SatelliteObservationInput,
    determine_satellite_adjustment,
)

ANALYSIS_DATE = date(2026, 6, 1)
DEFAULT_KWARGS = dict(
    min_valid_observations_for_trend=2,
    max_observation_age_days_for_trend=20,
    low_valid_pixel_ratio_threshold=0.6,
    trend_adjustment_cap_fraction_of_raw=0.15,
    raw_mm=50.0,
)


def _obs(days_ago: int, valid_pixel_ratio: float, ndmi: float, msi: float, ndvi: float):
    return SatelliteObservationInput(
        acquisition_date=ANALYSIS_DATE - timedelta(days=days_ago),
        valid_pixel_ratio=valid_pixel_ratio,
        ndmi_p50=ndmi,
        msi_p50=msi,
        ndvi_p50=ndvi,
    )


def test_no_observations_is_insufficient() -> None:
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=[], **DEFAULT_KWARGS
    )
    assert result.applied is False
    assert result.data_quality == SatelliteDataQuality.INSUFFICIENT
    assert result.adjustment_mm == 0.0


def test_single_observation_is_insufficient_for_a_trend() -> None:
    observations = [_obs(5, 0.9, 0.2, 1.0, 0.5)]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.applied is False
    assert result.valid_observations_used == 1  # fresh/high-quality, just below the minimum count
    assert result.latest_observation_date == observations[0].acquisition_date


def test_two_observations_agreeing_on_drier_trend_increase_depletion() -> None:
    observations = [
        _obs(14, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),
        _obs(5, 0.9, ndmi=0.15, msi=1.1, ndvi=0.45),
    ]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.applied is True
    assert result.adjustment_mm > 0
    assert result.data_quality == SatelliteDataQuality.OK


def test_two_observations_agreeing_on_wetter_trend_decrease_depletion() -> None:
    observations = [
        _obs(14, 0.9, ndmi=0.15, msi=1.1, ndvi=0.45),
        _obs(5, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),
    ]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.applied is True
    assert result.adjustment_mm < 0


def test_adjustment_is_capped_at_configured_fraction_of_raw() -> None:
    observations = [
        _obs(14, 0.9, ndmi=1.0, msi=0.0, ndvi=1.0),
        _obs(5, 0.9, ndmi=-1.0, msi=2.0, ndvi=-1.0),  # extreme swing
    ]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    cap = DEFAULT_KWARGS["trend_adjustment_cap_fraction_of_raw"] * DEFAULT_KWARGS["raw_mm"]
    assert abs(result.adjustment_mm) <= cap + 1e-9


def test_no_reaction_to_a_single_observation_even_if_extreme() -> None:
    observations = [_obs(5, 0.99, ndmi=-1.0, msi=2.0, ndvi=-1.0)]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.applied is False
    assert result.adjustment_mm == 0.0


def test_disagreeing_indices_produce_no_adjustment() -> None:
    observations = [
        _obs(14, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),
        _obs(5, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),  # identical - no trend at all
    ]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.applied is False
    assert result.data_quality == SatelliteDataQuality.OK


def test_stale_observations_are_excluded_and_flagged() -> None:
    observations = [
        _obs(40, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),
        _obs(30, 0.9, ndmi=0.15, msi=1.1, ndvi=0.45),
    ]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.applied is False
    assert result.data_quality == SatelliteDataQuality.STALE
    assert result.latest_observation_age_days == 30


def test_low_valid_pixel_ratio_excludes_observation() -> None:
    observations = [
        _obs(14, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),
        _obs(5, 0.2, ndmi=0.15, msi=1.1, ndvi=0.45),  # cloudy
    ]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.applied is False
    assert result.data_quality == SatelliteDataQuality.LOW_QUALITY


def test_future_observations_are_ignored() -> None:
    observations = [
        _obs(14, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),
        _obs(-5, 0.9, ndmi=0.99, msi=0.1, ndvi=0.99),  # in the future
    ]
    result = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert result.latest_observation_date == observations[0].acquisition_date


def test_deterministic_repeated_calls() -> None:
    observations = [
        _obs(14, 0.9, ndmi=0.30, msi=0.9, ndvi=0.60),
        _obs(5, 0.9, ndmi=0.15, msi=1.1, ndvi=0.45),
    ]
    first = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    second = determine_satellite_adjustment(
        analysis_date=ANALYSIS_DATE, observations=observations, **DEFAULT_KWARGS
    )
    assert first == second
