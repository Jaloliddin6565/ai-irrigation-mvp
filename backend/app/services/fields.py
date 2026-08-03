from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.field import Field
from app.domain.geo import ValidatedPolygon, validate_and_normalize_polygon
from app.repositories import fields as fields_repo
from app.schemas.field import FieldCreate, FieldUpdate
from app.services.farmers import get_farmer_or_404
from app.settings import get_settings


def _invalid_dates_error() -> AppError:
    return AppError(
        code="invalid_dates",
        message_uz="Kutilayotgan hosil yig'ish sanasi ekish sanasidan keyin bo'lishi kerak.",
        message_en="expected_harvest_date must be after planting_date.",
        status_code=422,
    )


def _invalid_override_error() -> AppError:
    return AppError(
        code="invalid_override_values",
        message_uz=(
            "field_capacity_override qiymati wilting_point_override dan katta bo'lishi kerak."
        ),
        message_en="field_capacity_override must be greater than wilting_point_override.",
        status_code=422,
    )


def _validate_polygon(geojson_polygon: dict[str, Any]) -> ValidatedPolygon:
    settings = get_settings()
    return validate_and_normalize_polygon(
        geojson_polygon,
        max_vertices=settings.max_polygon_vertices,
        max_area_hectares=settings.max_field_area_hectares,
    )


def get_field_or_404(db: Session, field_id: int) -> Field:
    field = fields_repo.get_by_id(db, field_id)
    if field is None:
        raise AppError(
            code="field_not_found",
            message_uz=f"{field_id} identifikatorli dala topilmadi.",
            message_en=f"Field {field_id} not found.",
            status_code=404,
        )
    return field


def create_field(db: Session, payload: FieldCreate) -> Field:
    get_farmer_or_404(db, payload.farmer_id)  # existence check before any write
    validated = _validate_polygon(payload.geojson_polygon)

    field = Field(
        farmer_id=payload.farmer_id,
        name=payload.name,
        geojson_polygon=validated.normalized_geojson,
        area_hectares=validated.area_hectares,
        centroid_latitude=validated.centroid_latitude,
        centroid_longitude=validated.centroid_longitude,
        crop_type=payload.crop_type,
        crop_variety=payload.crop_variety,
        planting_date=payload.planting_date,
        expected_harvest_date=payload.expected_harvest_date,
        crop_stage_override=payload.crop_stage_override,
        irrigation_method=payload.irrigation_method,
        soil_texture=payload.soil_texture,
        root_depth_override=payload.root_depth_override,
        field_capacity_override=payload.field_capacity_override,
        wilting_point_override=payload.wilting_point_override,
        notes=payload.notes,
    )
    fields_repo.create(db, field)
    db.commit()
    db.refresh(field)
    return field


def list_fields(
    db: Session, *, farmer_id: int | None, limit: int, offset: int
) -> tuple[list[Field], int]:
    if farmer_id is not None:
        get_farmer_or_404(db, farmer_id)
    return fields_repo.list_fields(db, farmer_id=farmer_id, limit=limit, offset=offset)


def update_field(db: Session, field_id: int, payload: FieldUpdate) -> Field:
    field = get_field_or_404(db, field_id)
    data = payload.model_dump(exclude_unset=True)

    validated_polygon: ValidatedPolygon | None = None
    if "geojson_polygon" in data:
        validated_polygon = _validate_polygon(data.pop("geojson_polygon"))

    # Validate cross-field invariants against the MERGED (existing + incoming)
    # state before mutating anything, so a rejected update never leaves the
    # ORM object with partially-applied changes.
    prospective_planting_date = data.get("planting_date", field.planting_date)
    prospective_harvest_date = data.get("expected_harvest_date", field.expected_harvest_date)
    if (
        prospective_harvest_date is not None
        and prospective_harvest_date <= prospective_planting_date
    ):
        raise _invalid_dates_error()

    prospective_field_capacity = data.get("field_capacity_override", field.field_capacity_override)
    prospective_wilting_point = data.get("wilting_point_override", field.wilting_point_override)
    if (
        prospective_field_capacity is not None
        and prospective_wilting_point is not None
        and prospective_field_capacity <= prospective_wilting_point
    ):
        raise _invalid_override_error()

    if validated_polygon is not None:
        field.geojson_polygon = validated_polygon.normalized_geojson
        field.area_hectares = validated_polygon.area_hectares
        field.centroid_latitude = validated_polygon.centroid_latitude
        field.centroid_longitude = validated_polygon.centroid_longitude

    for key, value in data.items():
        setattr(field, key, value)

    db.commit()
    db.refresh(field)
    return field


def delete_field(db: Session, field_id: int) -> None:
    field = get_field_or_404(db, field_id)
    fields_repo.delete(db, field)
    db.commit()
