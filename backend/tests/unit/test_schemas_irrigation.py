from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.irrigation import IrrigationEventCreate


def test_valid_irrigation_event() -> None:
    event = IrrigationEventCreate(
        occurred_at=datetime.now(UTC) - timedelta(days=1),
        amount_mm=15.0,
        value_source="farmer_estimate",
    )
    assert event.amount_mm == 15.0


def test_rejects_negative_amount_mm() -> None:
    with pytest.raises(ValidationError):
        IrrigationEventCreate(
            occurred_at=datetime.now(UTC),
            amount_mm=-5.0,
            value_source="measured",
        )


def test_rejects_negative_total_volume() -> None:
    with pytest.raises(ValidationError):
        IrrigationEventCreate(
            occurred_at=datetime.now(UTC),
            total_volume_m3=-1.0,
            value_source="measured",
        )


def test_rejects_non_positive_duration() -> None:
    with pytest.raises(ValidationError):
        IrrigationEventCreate(
            occurred_at=datetime.now(UTC),
            duration_minutes=0,
            value_source="measured",
        )


def test_rejects_far_future_occurred_at() -> None:
    with pytest.raises(ValidationError):
        IrrigationEventCreate(
            occurred_at=datetime.now(UTC) + timedelta(days=10),
            amount_mm=10.0,
            value_source="measured",
        )


def test_rejects_event_with_no_measurement_at_all() -> None:
    with pytest.raises(ValidationError):
        IrrigationEventCreate(
            occurred_at=datetime.now(UTC),
            value_source="measured",
        )


def test_accepts_qualitative_amount_only() -> None:
    event = IrrigationEventCreate(
        occurred_at=datetime.now(UTC),
        qualitative_amount="moderate",
        value_source="farmer_estimate",
    )
    assert event.qualitative_amount == "moderate"
