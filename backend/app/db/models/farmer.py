from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models._helpers import str_enum_column
from app.db.models.enums import PreferredLanguage

if TYPE_CHECKING:
    from app.db.models.field import Field


class Farmer(Base):
    __tablename__ = "farmers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    preferred_language: Mapped[PreferredLanguage] = mapped_column(
        str_enum_column(PreferredLanguage, 8),
        nullable=False,
        default=PreferredLanguage.UZ,
        server_default=PreferredLanguage.UZ.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    fields: Mapped[list["Field"]] = relationship(
        back_populates="farmer", cascade="all, delete-orphan"
    )
