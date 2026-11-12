"""User story estimation mode and per-task story points.

Revision ID: 011_ep06_estimation_mode
Revises: 010_ep06_time_status_invites
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_ep06_estimation_mode"
down_revision: str | None = "010_ep06_time_status_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_stories",
        sa.Column("estimation_mode", sa.String(20), nullable=False, server_default="story"),
    )
    op.add_column("story_tasks", sa.Column("story_points", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("story_tasks", "story_points")
    op.drop_column("user_stories", "estimation_mode")
