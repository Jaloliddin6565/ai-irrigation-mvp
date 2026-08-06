"""Importing this package registers all ORM models on Base.metadata.

Alembic's env.py and test fixtures that call Base.metadata.create_all()
rely on this import happening first.
"""

from app.db.models.analysis import Analysis
from app.db.models.farmer import Farmer
from app.db.models.field import Field
from app.db.models.irrigation_event import IrrigationEvent

__all__ = ["Analysis", "Farmer", "Field", "IrrigationEvent"]
