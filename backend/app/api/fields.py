from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.field import FieldCreate, FieldListResponse, FieldRead, FieldUpdate
from app.services import fields as fields_service
from app.settings import get_settings

router = APIRouter(prefix="/api/fields", tags=["fields"])


@router.post(
    "",
    response_model=FieldRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a field (area/centroid are always server-computed, never client-trusted)",
)
def create_field(payload: FieldCreate, db: Session = Depends(get_db)) -> FieldRead:
    field = fields_service.create_field(db, payload)
    return FieldRead.model_validate(field)


@router.get("", response_model=FieldListResponse)
def list_fields(
    farmer_id: int | None = Query(default=None, description="Filter to a single farmer's fields"),
    limit: int | None = Query(default=None, ge=1, description="Defaults to DEFAULT_LIST_LIMIT"),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> FieldListResponse:
    settings = get_settings()
    effective_limit = min(limit or settings.default_list_limit, settings.max_list_limit)
    items, total = fields_service.list_fields(
        db, farmer_id=farmer_id, limit=effective_limit, offset=offset
    )
    return FieldListResponse(
        items=[FieldRead.model_validate(item) for item in items],
        total=total,
        limit=effective_limit,
        offset=offset,
    )


@router.get("/{field_id}", response_model=FieldRead)
def get_field(field_id: int, db: Session = Depends(get_db)) -> FieldRead:
    field = fields_service.get_field_or_404(db, field_id)
    return FieldRead.model_validate(field)


@router.patch("/{field_id}", response_model=FieldRead)
def update_field(field_id: int, payload: FieldUpdate, db: Session = Depends(get_db)) -> FieldRead:
    field = fields_service.update_field(db, field_id, payload)
    return FieldRead.model_validate(field)


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(field_id: int, db: Session = Depends(get_db)) -> None:
    fields_service.delete_field(db, field_id)
