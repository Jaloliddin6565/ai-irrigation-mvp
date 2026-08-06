"""Field persistence. No business-rule validation here — see app/services/fields.py."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.field import Field


def get_by_id(db: Session, field_id: int) -> Field | None:
    return db.get(Field, field_id)


def create(db: Session, field: Field) -> Field:
    db.add(field)
    db.flush()
    return field


def delete(db: Session, field: Field) -> None:
    db.delete(field)


def list_fields(
    db: Session, *, farmer_id: int | None, limit: int, offset: int
) -> tuple[list[Field], int]:
    stmt = select(Field)
    count_stmt = select(func.count()).select_from(Field)
    if farmer_id is not None:
        stmt = stmt.where(Field.farmer_id == farmer_id)
        count_stmt = count_stmt.where(Field.farmer_id == farmer_id)

    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(Field.id).limit(limit).offset(offset)))
    return items, total
