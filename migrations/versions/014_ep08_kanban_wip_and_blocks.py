"""EP-08 Kanban column settings and task block fields.

Revision ID: 014_ep08_kanban_wip_and_blocks
Revises: 013_ep07_sprint_closed_at
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014_ep08_kanban_wip_and_blocks"
down_revision: str | None = "013_ep07_sprint_closed_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add block and dependency tracking to story_tasks
    op.add_column(
        "story_tasks",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "story_tasks",
        sa.Column("blocked_reason", sa.String(500), nullable=True),
    )
    op.add_column(
        "story_tasks",
        sa.Column("blocked_by_task_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "story_tasks_blocked_by_task_id_fkey",
        "story_tasks",
        "story_tasks",
        ["blocked_by_task_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 2. Create kanban_column_settings for WIP limits
    op.create_table(
        "kanban_column_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("column_id", sa.String(50), nullable=False),
        sa.Column("wip_limit", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "column_id", name="uq_kanban_col_settings_proj_col"),
    )
    op.create_index(
        "ix_kanban_column_settings_project_id",
        "kanban_column_settings",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_kanban_column_settings_project_id", "kanban_column_settings")
    op.drop_table("kanban_column_settings")
    op.drop_constraint("story_tasks_blocked_by_task_id_fkey", "story_tasks", type_="foreignkey")
    op.drop_column("story_tasks", "blocked_by_task_id")
    op.drop_column("story_tasks", "blocked_reason")
    op.drop_column("story_tasks", "is_blocked")
