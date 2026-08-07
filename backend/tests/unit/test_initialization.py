from datetime import date, timedelta

from app.domain.initialization import (
    InitializationMethod,
    IrrigationEventInput,
    determine_initialization,
)

QMAP = {"little": 8.0, "moderate": 18.0, "a_lot": 35.0}
PLANTING = date(2026, 4, 1)
ANALYSIS_DATE = date(2026, 6, 1)


def _taw_at(_d: date) -> float:
    return 100.0


def _raw_at(_d: date) -> float:
    return 50.0


def _run(**overrides):
    kwargs = dict(
        planting_date=PLANTING,
        analysis_date=ANALYSIS_DATE,
        irrigation_events=[],
        field_area_hectares=1.0,
        qualitative_irrigation_mm=QMAP,
        irrigation_efficiency=0.9,
        max_anchor_age_days=90,
        conservative_default_fraction_of_raw=0.5,
        weather_available_dates=[],
        taw_at=_taw_at,
        raw_at=_raw_at,
    )
    kwargs.update(overrides)
    return determine_initialization(**kwargs)


def test_tier1_recent_known_amount() -> None:
    events = [IrrigationEventInput(occurred_at=ANALYSIS_DATE - timedelta(days=3), amount_mm=20.0)]
    result = _run(irrigation_events=events)

    assert result.method == InitializationMethod.RECENT_IRRIGATION_KNOWN_AMOUNT
    assert result.start_date == ANALYSIS_DATE - timedelta(days=3)
    assert result.starting_depletion_mm == 100.0 - 20.0 * 0.9
    assert result.uncertainty < 0.3


def test_tier1_picks_most_recent_of_multiple_known_amount_events() -> None:
    events = [
        IrrigationEventInput(occurred_at=ANALYSIS_DATE - timedelta(days=10), amount_mm=20.0),
        IrrigationEventInput(occurred_at=ANALYSIS_DATE - timedelta(days=3), amount_mm=25.0),
    ]
    result = _run(irrigation_events=events)
    assert result.start_date == ANALYSIS_DATE - timedelta(days=3)


def test_tier2_duration_and_flow_rate_only() -> None:
    events = [
        IrrigationEventInput(
            occurred_at=ANALYSIS_DATE - timedelta(days=3),
            duration_minutes=60,
            flow_rate_m3_hour=10.0,
        )
    ]
    result = _run(irrigation_events=events)

    assert result.method == InitializationMethod.RECENT_IRRIGATION_DURATION_FLOW
    assert result.uncertainty > 0.3


def test_tier1_preferred_over_tier2_when_both_present() -> None:
    events = [
        IrrigationEventInput(
            occurred_at=ANALYSIS_DATE - timedelta(days=10),
            duration_minutes=60,
            flow_rate_m3_hour=10.0,
        ),
        IrrigationEventInput(occurred_at=ANALYSIS_DATE - timedelta(days=3), amount_mm=20.0),
    ]
    result = _run(irrigation_events=events)
    assert result.method == InitializationMethod.RECENT_IRRIGATION_KNOWN_AMOUNT
    assert result.start_date == ANALYSIS_DATE - timedelta(days=3)


def test_qualitative_only_event_does_not_qualify_as_anchor() -> None:
    events = [
        IrrigationEventInput(
            occurred_at=ANALYSIS_DATE - timedelta(days=3), qualitative_amount="moderate"
        )
    ]
    result = _run(irrigation_events=events)
    # Falls through to tier 3 (planting date assumption), since planting is in-window.
    assert result.method == InitializationMethod.PLANTING_DATE_ASSUMPTION


def test_irrigation_event_outside_anchor_window_is_ignored() -> None:
    events = [IrrigationEventInput(occurred_at=ANALYSIS_DATE - timedelta(days=200), amount_mm=20.0)]
    result = _run(irrigation_events=events, max_anchor_age_days=90)
    assert result.method == InitializationMethod.PLANTING_DATE_ASSUMPTION


def test_tier3_planting_date_assumption() -> None:
    result = _run()
    assert result.method == InitializationMethod.PLANTING_DATE_ASSUMPTION
    assert result.start_date == PLANTING
    assert result.starting_depletion_mm == 0.0


def test_tier4_conservative_default_anchored_at_earliest_weather_date() -> None:
    old_planting = ANALYSIS_DATE - timedelta(days=200)
    weather_dates = [ANALYSIS_DATE - timedelta(days=10), ANALYSIS_DATE - timedelta(days=9)]
    result = _run(planting_date=old_planting, weather_available_dates=weather_dates)

    assert result.method == InitializationMethod.CONSERVATIVE_DEFAULT
    assert result.start_date == weather_dates[0]
    assert result.starting_depletion_mm == 0.5 * 50.0
    assert result.uncertainty > 0.5


def test_tier4_warning_codes_distinguish_missing_irrigation_from_stale_planting_date() -> None:
    """Regression: the pilot walkthrough found the tier-4 English message
    ("no in-window planting date") reading as if planting_date were missing.
    planting_date is a required field — it can only be present but outside
    the anchor window. The structured codes must say so, as two distinct
    messages, never conflated into one."""
    old_planting = ANALYSIS_DATE - timedelta(days=200)
    weather_dates = [ANALYSIS_DATE - timedelta(days=10), ANALYSIS_DATE - timedelta(days=9)]
    result = _run(planting_date=old_planting, weather_available_dates=weather_dates)

    codes = {m.code for m in result.warning_codes}
    assert "no_recent_irrigation_record" in codes
    assert "planting_date_outside_anchor_window" in codes

    planting_date_message = next(
        m for m in result.warning_codes if m.code == "planting_date_outside_anchor_window"
    )
    assert planting_date_message.params["planting_date"] == old_planting.isoformat()
    assert planting_date_message.params["days_since_planting"] == 200
    assert planting_date_message.params["max_anchor_age_days"] == 90


def test_tier5_insufficient_data_when_nothing_usable() -> None:
    old_planting = ANALYSIS_DATE - timedelta(days=200)
    result = _run(planting_date=old_planting, weather_available_dates=[])

    assert result.method == InitializationMethod.INSUFFICIENT_DATA
    assert result.start_date is None
    assert result.starting_depletion_mm is None
    assert result.uncertainty == 1.0


def test_future_planting_date_does_not_trigger_tier3() -> None:
    # planting_date after analysis_date -> pre-planting, tier 3 must not fire.
    future_planting = ANALYSIS_DATE + timedelta(days=5)
    result = _run(planting_date=future_planting)
    assert result.method != InitializationMethod.PLANTING_DATE_ASSUMPTION


def test_deterministic_repeated_calls() -> None:
    events = [IrrigationEventInput(occurred_at=ANALYSIS_DATE - timedelta(days=3), amount_mm=20.0)]
    first = _run(irrigation_events=events)
    second = _run(irrigation_events=events)
    assert first == second
