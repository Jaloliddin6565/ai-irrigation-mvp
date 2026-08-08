"""add ai_summary to analyses

Revision ID: b0319fcd42f7
Revises: 3750513bd3c4
Create Date: 2026-08-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0319fcd42f7"
down_revision: str | None = "3750513bd3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable JSON column, Phase 2 (AI Soil Wetness Index evidence layer).
    # Nullable so existing rows written before this migration keep loading —
    # app/services/analysis.py _response_from_orm synthesizes a
    # status="unavailable" ai_summary for those rather than recomputing them
    # with a newer AI model (CLAUDE.md / PHASE 2 section 11).
    op.add_column("analyses", sa.Column("ai_summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "ai_summary")
