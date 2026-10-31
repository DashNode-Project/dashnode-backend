"""Add closed_at timestamp to sprints.

Revision ID: 013_ep07_sprint_closed_at
Revises: 012_ep07_sprints
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_ep07_sprint_closed_at"
down_revision: str | None = "012_ep07_sprints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sprints", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("sprints", "closed_at")
