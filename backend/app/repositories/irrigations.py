"""IrrigationEvent persistence. Business-rule validation lives in app/services/irrigations.py."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.irrigation_event import IrrigationEvent


def create(db: Session, event: IrrigationEvent) -> IrrigationEvent:
    db.add(event)
    db.flush()
    return event


def list_for_field(
    db: Session, *, field_id: int, limit: int, offset: int
) -> tuple[list[IrrigationEvent], int]:
    stmt = select(IrrigationEvent).where(IrrigationEvent.field_id == field_id)
    count_stmt = (
        select(func.count())
        .select_from(IrrigationEvent)
        .where(IrrigationEvent.field_id == field_id)
    )

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(stmt.order_by(IrrigationEvent.occurred_at.desc()).limit(limit).offset(offset))
    )
    return items, total
