"""Analysis model.

This table is created in Phase 2 so the schema exists ahead of time, but
nothing populates it yet — the water-balance engine, recommendation engine,
and confidence calculations are Phase 3 work, and no `/analyze` endpoint
exists in this phase. See CLAUDE.md and docs/methodology.md.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base
from app.db.models._helpers import str_enum_column
from app.db.models.enums import AnalysisDataMode

if TYPE_CHECKING:
    from app.db.models.field import Field


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_mode: Mapped[AnalysisDataMode] = mapped_column(
        str_enum_column(AnalysisDataMode, 10), nullable=False
    )

    satellite_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    weather_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    water_balance_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Phase 2 addition, nullable for backward compatibility with rows written
    # before this column existed — _response_from_orm (app/services/analysis.py)
    # synthesizes a status="unavailable" AISummarySchema for those rows rather
    # than recomputing them with a newer AI model (CLAUDE.md/PHASE 2 section 11:
    # persisted analyses must stay reproducible, never silently re-scored).
    ai_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(20), nullable=False)

    field: Mapped["Field"] = relationship(back_populates="analyses")
