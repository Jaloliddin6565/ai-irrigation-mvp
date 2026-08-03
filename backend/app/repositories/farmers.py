"""Farmer persistence. No business-rule validation here — see app/services/farmers.py."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.farmer import Farmer


def get_by_id(db: Session, farmer_id: int) -> Farmer | None:
    return db.get(Farmer, farmer_id)


def get_by_phone(db: Session, phone: str) -> Farmer | None:
    return db.scalar(select(Farmer).where(Farmer.phone == phone))


def create(db: Session, farmer: Farmer) -> Farmer:
    db.add(farmer)
    db.flush()
    return farmer
