from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.field import EXAMPLE_POLYGON, FieldCreate, FieldUpdate

BASE_KWARGS = dict(
    farmer_id=1,
    name="Shimoliy dala",
    geojson_polygon=EXAMPLE_POLYGON,
    crop_type="cotton",
    planting_date=date(2026, 4, 1),
    irrigation_method="drip",
    soil_texture="loam",
)


def test_valid_field_create() -> None:
    field = FieldCreate(**BASE_KWARGS)
    assert field.crop_type == "cotton"


def test_rejects_harvest_date_before_planting_date() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(**{**BASE_KWARGS, "expected_harvest_date": date(2026, 3, 1)})


def test_rejects_harvest_date_equal_to_planting_date() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(**{**BASE_KWARGS, "expected_harvest_date": date(2026, 4, 1)})


def test_accepts_harvest_date_after_planting_date() -> None:
    field = FieldCreate(**{**BASE_KWARGS, "expected_harvest_date": date(2026, 9, 1)})
    assert field.expected_harvest_date == date(2026, 9, 1)


def test_rejects_field_capacity_not_greater_than_wilting_point() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(
            **{
                **BASE_KWARGS,
                "field_capacity_override": 0.2,
                "wilting_point_override": 0.2,
            }
        )


def test_rejects_root_depth_override_out_of_range() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(**{**BASE_KWARGS, "root_depth_override": 10.0})

    with pytest.raises(ValidationError):
        FieldCreate(**{**BASE_KWARGS, "root_depth_override": 0.0})


@pytest.mark.parametrize("blank", ["", "   "])
def test_rejects_blank_name(blank: str) -> None:
    with pytest.raises(ValidationError):
        FieldCreate(**{**BASE_KWARGS, "name": blank})


def test_field_update_all_optional() -> None:
    update = FieldUpdate()
    assert update.model_dump(exclude_unset=True) == {}


def test_field_update_rejects_harvest_before_planting_when_both_given() -> None:
    with pytest.raises(ValidationError):
        FieldUpdate(planting_date=date(2026, 5, 1), expected_harvest_date=date(2026, 4, 1))
