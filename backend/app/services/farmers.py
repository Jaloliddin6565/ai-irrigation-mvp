from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.farmer import Farmer
from app.repositories import farmers as farmers_repo
from app.schemas.farmer import FarmerCreate


def create_farmer(db: Session, payload: FarmerCreate) -> Farmer:
    farmer = Farmer(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        region=payload.region,
        district=payload.district,
        preferred_language=payload.preferred_language,
    )
    try:
        farmers_repo.create(db, farmer)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            code="farmer_phone_conflict",
            message_uz="Bu telefon raqami bilan fermer allaqachon ro'yxatdan o'tgan.",
            message_en="A farmer with this phone number is already registered.",
            status_code=409,
        ) from None
    db.refresh(farmer)
    return farmer


def get_farmer_or_404(db: Session, farmer_id: int) -> Farmer:
    farmer = farmers_repo.get_by_id(db, farmer_id)
    if farmer is None:
        raise AppError(
            code="farmer_not_found",
            message_uz=f"{farmer_id} identifikatorli fermer topilmadi.",
            message_en=f"Farmer {farmer_id} not found.",
            status_code=404,
        )
    return farmer


def get_farmer_by_phone_or_404(db: Session, phone: str) -> Farmer:
    farmer = farmers_repo.get_by_phone(db, phone)
    if farmer is None:
        raise AppError(
            code="farmer_not_found",
            message_uz="Ushbu telefon raqami bilan fermer topilmadi.",
            message_en="No farmer found with this phone number.",
            status_code=404,
        )
    return farmer
