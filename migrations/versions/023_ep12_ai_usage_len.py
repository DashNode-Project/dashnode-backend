"""Widen ai_daily_usage.service to VARCHAR(100) for per-user tracking.

Revision ID: 023_ep12_ai_usage_len
Revises: 022_ep12_ai_analyses
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_ep12_ai_usage_len"
down_revision: str | None = "022_ep12_ai_analyses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "ai_daily_usage",
        "service",
        existing_type=sa.String(length=20),
        type_=sa.String(length=100),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "ai_daily_usage",
        "service",
        existing_type=sa.String(length=100),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
