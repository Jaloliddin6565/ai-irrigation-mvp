from datetime import datetime, timedelta
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import QualitativeAmount, ValueSource

# How far into the future an irrigation event may be logged — covers clock
# skew and same-day "just about to irrigate" entries without accepting
# obviously wrong future-dated data.
MAX_FUTURE_SKEW = timedelta(days=1)


class IrrigationEventCreate(BaseModel):
    occurred_at: datetime
    duration_minutes: int | None = Field(default=None, gt=0)
    amount_mm: float | None = Field(default=None, ge=0)
    total_volume_m3: float | None = Field(default=None, ge=0)
    flow_rate_m3_hour: float | None = Field(default=None, ge=0)
    qualitative_amount: QualitativeAmount | None = None
    value_source: ValueSource
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        now = datetime.now(self.occurred_at.tzinfo)
        if self.occurred_at > now + MAX_FUTURE_SKEW:
            raise ValueError("occurred_at cannot be more than 1 day in the future")

        has_any_measurement = any(
            value is not None
            for value in (
                self.duration_minutes,
                self.amount_mm,
                self.total_volume_m3,
                self.flow_rate_m3_hour,
                self.qualitative_amount,
            )
        )
        if not has_any_measurement:
            raise ValueError(
                "at least one of duration_minutes, amount_mm, total_volume_m3, "
                "flow_rate_m3_hour, or qualitative_amount must be provided"
            )
        return self


class IrrigationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field_id: int
    occurred_at: datetime
    duration_minutes: int | None
    amount_mm: float | None
    total_volume_m3: float | None
    flow_rate_m3_hour: float | None
    qualitative_amount: QualitativeAmount | None
    value_source: ValueSource
    notes: str | None
    created_at: datetime


class IrrigationEventListResponse(BaseModel):
    items: list[IrrigationEventRead]
    total: int
    limit: int
    offset: int
