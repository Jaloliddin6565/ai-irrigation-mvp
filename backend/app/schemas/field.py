from datetime import date, datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.enums import CropStage, CropType, IrrigationMethod, SoilTexture

EXAMPLE_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [69.2400, 41.3000],
            [69.2410, 41.3000],
            [69.2410, 41.3010],
            [69.2400, 41.3010],
            [69.2400, 41.3000],
        ]
    ],
}


def _check_dates(planting_date: date | None, expected_harvest_date: date | None) -> None:
    if (
        planting_date is not None
        and expected_harvest_date is not None
        and expected_harvest_date <= planting_date
    ):
        raise ValueError("expected_harvest_date must be after planting_date")


def _check_override_ordering(
    field_capacity_override: float | None, wilting_point_override: float | None
) -> None:
    if (
        field_capacity_override is not None
        and wilting_point_override is not None
        and field_capacity_override <= wilting_point_override
    ):
        raise ValueError("field_capacity_override must be greater than wilting_point_override")


class FieldCreate(BaseModel):
    farmer_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=200, examples=["Shimoliy dala"])
    geojson_polygon: dict[str, Any] = Field(..., examples=[EXAMPLE_POLYGON])
    crop_type: CropType
    crop_variety: str | None = Field(default=None, max_length=100)
    planting_date: date
    expected_harvest_date: date | None = None
    crop_stage_override: CropStage | None = None
    irrigation_method: IrrigationMethod
    soil_texture: SoilTexture
    root_depth_override: float | None = Field(default=None, gt=0, le=5)
    field_capacity_override: float | None = Field(default=None, gt=0, lt=1)
    wilting_point_override: float | None = Field(default=None, gt=0, lt=1)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def _cross_field_checks(self) -> Self:
        _check_dates(self.planting_date, self.expected_harvest_date)
        _check_override_ordering(self.field_capacity_override, self.wilting_point_override)
        return self


class FieldUpdate(BaseModel):
    """All fields optional (PATCH semantics) — only supplied keys are applied."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    geojson_polygon: dict[str, Any] | None = None
    crop_type: CropType | None = None
    crop_variety: str | None = Field(default=None, max_length=100)
    planting_date: date | None = None
    expected_harvest_date: date | None = None
    crop_stage_override: CropStage | None = None
    irrigation_method: IrrigationMethod | None = None
    soil_texture: SoilTexture | None = None
    root_depth_override: float | None = Field(default=None, gt=0, le=5)
    field_capacity_override: float | None = Field(default=None, gt=0, lt=1)
    wilting_point_override: float | None = Field(default=None, gt=0, lt=1)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def _cross_field_checks_if_both_present(self) -> Self:
        # Full cross-field validation against the merged/existing record
        # happens in the service layer (it needs the current DB state for
        # fields not included in this partial update). This only catches
        # the case where both sides of a check are provided together.
        _check_dates(self.planting_date, self.expected_harvest_date)
        _check_override_ordering(self.field_capacity_override, self.wilting_point_override)
        return self


class FieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farmer_id: int
    name: str
    geojson_polygon: dict[str, Any]
    area_hectares: float
    centroid_latitude: float
    centroid_longitude: float
    crop_type: CropType
    crop_variety: str | None
    planting_date: date
    expected_harvest_date: date | None
    crop_stage_override: CropStage | None
    irrigation_method: IrrigationMethod
    soil_texture: SoilTexture
    root_depth_override: float | None
    field_capacity_override: float | None
    wilting_point_override: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class FieldListResponse(BaseModel):
    items: list[FieldRead]
    total: int
    limit: int
    offset: int
