"""Shared SQLAlchemy column helpers for ORM models."""

from enum import StrEnum
from typing import TypeVar

from sqlalchemy import Enum

E = TypeVar("E", bound=StrEnum)


def str_enum_column(enum_cls: type[E], length: int) -> Enum:
    """A portable (SQLite + PostgreSQL) VARCHAR+CHECK enum column.

    native_enum=False avoids relying on PostgreSQL's native ENUM type (which
    needs its own ALTER TYPE migrations to extend), keeping the same column
    definition valid on both database backends — see
    docs/postgis_migration.md for the broader SQLite->PostgreSQL story.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [member.value for member in e],
    )
