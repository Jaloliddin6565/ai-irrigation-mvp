from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.farmer import Farmer
from app.db.models.field import Field
from app.db.models.irrigation_event import IrrigationEvent

VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [[69.24, 41.30], [69.25, 41.30], [69.25, 41.31], [69.24, 41.31], [69.24, 41.30]]
    ],
}


def _make_farmer(**overrides) -> Farmer:
    defaults = dict(
        full_name="Aliyev Vali",
        phone="+998901234567",
        region="Toshkent",
        district="Zangiota",
    )
    defaults.update(overrides)
    return Farmer(**defaults)


def _make_field(farmer_id: int, **overrides) -> Field:
    defaults = dict(
        farmer_id=farmer_id,
        name="Dala 1",
        geojson_polygon=VALID_POLYGON,
        area_hectares=1.5,
        centroid_latitude=41.305,
        centroid_longitude=69.245,
        crop_type="cotton",
        planting_date=date(2026, 4, 1),
        irrigation_method="drip",
        soil_texture="loam",
    )
    defaults.update(overrides)
    return Field(**defaults)


def test_farmer_phone_must_be_unique(db_session: Session) -> None:
    db_session.add(_make_farmer())
    db_session.commit()

    db_session.add(_make_farmer(full_name="Boshqa Fermer"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_field_area_must_be_positive(db_session: Session) -> None:
    farmer = _make_farmer()
    db_session.add(farmer)
    db_session.commit()

    db_session.add(_make_field(farmer.id, area_hectares=0))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_field_harvest_date_must_be_after_planting_date(db_session: Session) -> None:
    farmer = _make_farmer()
    db_session.add(farmer)
    db_session.commit()

    db_session.add(
        _make_field(
            farmer.id,
            planting_date=date(2026, 4, 1),
            expected_harvest_date=date(2026, 3, 1),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_field_centroid_latitude_out_of_range_rejected(db_session: Session) -> None:
    farmer = _make_farmer()
    db_session.add(farmer)
    db_session.commit()

    db_session.add(_make_field(farmer.id, centroid_latitude=95.0))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_irrigation_amount_mm_must_be_non_negative(db_session: Session) -> None:
    farmer = _make_farmer()
    db_session.add(farmer)
    db_session.commit()
    field = _make_field(farmer.id)
    db_session.add(field)
    db_session.commit()

    db_session.add(
        IrrigationEvent(
            field_id=field.id,
            occurred_at=datetime.now(UTC),
            amount_mm=-1.0,
            value_source="measured",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_farmer_cascades_to_fields(db_session: Session) -> None:
    farmer = _make_farmer()
    db_session.add(farmer)
    db_session.commit()
    field = _make_field(farmer.id)
    db_session.add(field)
    db_session.commit()
    field_id = field.id

    db_session.delete(farmer)
    db_session.commit()

    assert db_session.get(Field, field_id) is None


def test_deleting_field_cascades_to_irrigation_events(db_session: Session) -> None:
    farmer = _make_farmer()
    db_session.add(farmer)
    db_session.commit()
    field = _make_field(farmer.id)
    db_session.add(field)
    db_session.commit()

    event = IrrigationEvent(
        field_id=field.id,
        occurred_at=datetime.now(UTC),
        amount_mm=10.0,
        value_source="measured",
    )
    db_session.add(event)
    db_session.commit()
    event_id = event.id

    db_session.delete(field)
    db_session.commit()

    assert db_session.get(IrrigationEvent, event_id) is None
