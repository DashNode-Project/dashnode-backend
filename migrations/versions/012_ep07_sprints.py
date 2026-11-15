"""EP-07 sprints table, story FK and unique active sprint per project.

Revision ID: 012_ep07_sprints
Revises: 011_ep06_estimation_mode
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_ep07_sprints"
down_revision: str | None = "011_ep06_estimation_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sprints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("goal", sa.String(500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PLANNING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sprints_project_id", "sprints", ["project_id"])
    op.create_foreign_key(
        "user_stories_sprint_id_fkey",
        "user_stories",
        "sprints",
        ["sprint_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "CREATE UNIQUE INDEX unique_active_sprint_per_project "
        "ON sprints (project_id) WHERE status = 'ACTIVE'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS unique_active_sprint_per_project")
    op.drop_constraint("user_stories_sprint_id_fkey", "user_stories", type_="foreignkey")
    op.drop_index("ix_sprints_project_id", "sprints")
    op.drop_table("sprints")
