from sqlalchemy.orm import Session

from app.db.models.irrigation_event import IrrigationEvent
from app.repositories import irrigations as irrigations_repo
from app.schemas.irrigation import IrrigationEventCreate
from app.services.fields import get_field_or_404


def create_irrigation_event(
    db: Session, field_id: int, payload: IrrigationEventCreate
) -> IrrigationEvent:
    get_field_or_404(db, field_id)  # 404s if the field doesn't exist

    event = IrrigationEvent(
        field_id=field_id,
        occurred_at=payload.occurred_at,
        duration_minutes=payload.duration_minutes,
        amount_mm=payload.amount_mm,
        total_volume_m3=payload.total_volume_m3,
        flow_rate_m3_hour=payload.flow_rate_m3_hour,
        qualitative_amount=payload.qualitative_amount,
        value_source=payload.value_source,
        notes=payload.notes,
    )
    irrigations_repo.create(db, event)
    db.commit()
    db.refresh(event)
    return event


def list_irrigation_events(
    db: Session, field_id: int, *, limit: int, offset: int
) -> tuple[list[IrrigationEvent], int]:
    get_field_or_404(db, field_id)
    return irrigations_repo.list_for_field(db, field_id=field_id, limit=limit, offset=offset)
