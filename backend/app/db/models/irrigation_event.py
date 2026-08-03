from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models._helpers import str_enum_column
from app.db.models.enums import QualitativeAmount, ValueSource

if TYPE_CHECKING:
    from app.db.models.field import Field


class IrrigationEvent(Base):
    __tablename__ = "irrigation_events"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_irrigation_duration_positive",
        ),
        CheckConstraint(
            "amount_mm IS NULL OR amount_mm >= 0", name="ck_irrigation_amount_mm_non_negative"
        ),
        CheckConstraint(
            "total_volume_m3 IS NULL OR total_volume_m3 >= 0",
            name="ck_irrigation_total_volume_non_negative",
        ),
        CheckConstraint(
            "flow_rate_m3_hour IS NULL OR flow_rate_m3_hour >= 0",
            name="ck_irrigation_flow_rate_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_volume_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    flow_rate_m3_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualitative_amount: Mapped[QualitativeAmount | None] = mapped_column(
        str_enum_column(QualitativeAmount, 20), nullable=True
    )
    value_source: Mapped[ValueSource] = mapped_column(
        str_enum_column(ValueSource, 20), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    field: Mapped["Field"] = relationship(back_populates="irrigation_events")
