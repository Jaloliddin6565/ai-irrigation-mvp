"""Declarative base for all ORM models.

Domain models (Farmer, Field, IrrigationEvent, Analysis) are added in Phase 2
and register themselves against this Base. Kept empty and dialect-agnostic
so the same models work against SQLite (MVP) and PostgreSQL (documented
future migration, see docs/postgis_migration.md).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
