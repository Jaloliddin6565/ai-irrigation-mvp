from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.farmer import PHONE_PATTERN, FarmerCreate, FarmerRead
from app.services import farmers as farmers_service

router = APIRouter(prefix="/api/farmers", tags=["farmers"])


@router.post(
    "",
    response_model=FarmerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a farmer (no auth in this MVP — see CLAUDE.md)",
)
def create_farmer(payload: FarmerCreate, db: Session = Depends(get_db)) -> FarmerRead:
    farmer = farmers_service.create_farmer(db, payload)
    return FarmerRead.model_validate(farmer)


@router.get(
    "",
    response_model=FarmerRead,
    summary="Look up a farmer by exact phone number (trusted-MVP profile selection)",
)
def get_farmer_by_phone(
    phone: str = Query(..., pattern=PHONE_PATTERN.pattern),
    db: Session = Depends(get_db),
) -> FarmerRead:
    farmer = farmers_service.get_farmer_by_phone_or_404(db, phone)
    return FarmerRead.model_validate(farmer)


@router.get("/{farmer_id}", response_model=FarmerRead)
def get_farmer(farmer_id: int, db: Session = Depends(get_db)) -> FarmerRead:
    farmer = farmers_service.get_farmer_or_404(db, farmer_id)
    return FarmerRead.model_validate(farmer)
