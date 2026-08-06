from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base
from app.db.models._helpers import str_enum_column
from app.db.models.enums import CropStage, CropType, IrrigationMethod, SoilTexture

if TYPE_CHECKING:
    from app.db.models.analysis import Analysis
    from app.db.models.farmer import Farmer
    from app.db.models.irrigation_event import IrrigationEvent


class Field(Base):
    __tablename__ = "fields"
    __table_args__ = (
        CheckConstraint("area_hectares > 0", name="ck_fields_area_positive"),
        CheckConstraint(
            "centroid_latitude BETWEEN -90 AND 90", name="ck_fields_centroid_lat_range"
        ),
        CheckConstraint(
            "centroid_longitude BETWEEN -180 AND 180", name="ck_fields_centroid_lon_range"
        ),
        CheckConstraint(
            "expected_harvest_date IS NULL OR expected_harvest_date > planting_date",
            name="ck_fields_harvest_after_planting",
        ),
        CheckConstraint(
            "root_depth_override IS NULL OR root_depth_override > 0",
            name="ck_fields_root_depth_positive",
        ),
        CheckConstraint(
            "field_capacity_override IS NULL"
            " OR (field_capacity_override > 0 AND field_capacity_override < 1)",
            name="ck_fields_field_capacity_range",
        ),
        CheckConstraint(
            "wilting_point_override IS NULL"
            " OR (wilting_point_override > 0 AND wilting_point_override < 1)",
            name="ck_fields_wilting_point_range",
        ),
        Index("ix_fields_farmer_id_created_at", "farmer_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(
        ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Validated, normalized GeoJSON Polygon (WGS84) — see app/domain/geo.py.
    # Never trust a client-supplied area/centroid; both are recomputed
    # server-side from this geometry on every write.
    geojson_polygon: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    area_hectares: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_longitude: Mapped[float] = mapped_column(Float, nullable=False)

    crop_type: Mapped[CropType] = mapped_column(str_enum_column(CropType, 20), nullable=False)
    crop_variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    planting_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    crop_stage_override: Mapped[CropStage | None] = mapped_column(
        str_enum_column(CropStage, 20), nullable=True
    )

    irrigation_method: Mapped[IrrigationMethod] = mapped_column(
        str_enum_column(IrrigationMethod, 20), nullable=False
    )
    soil_texture: Mapped[SoilTexture] = mapped_column(
        str_enum_column(SoilTexture, 20), nullable=False
    )

    # Per-field agronomic overrides of the YAML-configured crop/soil
    # defaults. Units match the config: root_depth_override in metres,
    # field_capacity_override/wilting_point_override as volumetric fractions.
    root_depth_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_capacity_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    wilting_point_override: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    farmer: Mapped["Farmer"] = relationship(back_populates="fields")
    irrigation_events: Mapped[list["IrrigationEvent"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )
