"""Analysis persistence. No business-rule validation here — see app/services/analysis.py."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.analysis import Analysis


def get_by_id_for_field(db: Session, field_id: int, analysis_id: int) -> Analysis | None:
    return db.scalar(
        select(Analysis).where(Analysis.id == analysis_id, Analysis.field_id == field_id)
    )


def create(db: Session, analysis: Analysis) -> Analysis:
    db.add(analysis)
    db.flush()
    return analysis


def list_for_field(
    db: Session, *, field_id: int, limit: int, offset: int
) -> tuple[list[Analysis], int]:
    stmt = select(Analysis).where(Analysis.field_id == field_id)
    count_stmt = select(func.count()).select_from(Analysis).where(Analysis.field_id == field_id)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(stmt.order_by(Analysis.requested_at.desc()).limit(limit).offset(offset))
    )
    return items, total
