from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.irrigation import (
    IrrigationEventCreate,
    IrrigationEventListResponse,
    IrrigationEventRead,
)
from app.services import irrigations as irrigations_service
from app.settings import get_settings

router = APIRouter(prefix="/api/fields/{field_id}/irrigations", tags=["irrigations"])


@router.post("", response_model=IrrigationEventRead, status_code=status.HTTP_201_CREATED)
def create_irrigation_event(
    field_id: int, payload: IrrigationEventCreate, db: Session = Depends(get_db)
) -> IrrigationEventRead:
    event = irrigations_service.create_irrigation_event(db, field_id, payload)
    return IrrigationEventRead.model_validate(event)


@router.get("", response_model=IrrigationEventListResponse)
def list_irrigation_events(
    field_id: int,
    limit: int | None = Query(default=None, ge=1, description="Defaults to DEFAULT_LIST_LIMIT"),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> IrrigationEventListResponse:
    settings = get_settings()
    effective_limit = min(limit or settings.default_list_limit, settings.max_list_limit)
    items, total = irrigations_service.list_irrigation_events(
        db, field_id, limit=effective_limit, offset=offset
    )
    return IrrigationEventListResponse(
        items=[IrrigationEventRead.model_validate(item) for item in items],
        total=total,
        limit=effective_limit,
        offset=offset,
    )
