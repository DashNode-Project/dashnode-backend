"""Task time logs, status history and developer invitation lifecycle.

Revision ID: 010_ep06_time_status_invites
Revises: 009_ep06_backlog_tar
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_ep06_time_status_invites"
down_revision: str | None = "009_ep06_backlog_tar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("invitation_status", sa.String(20), nullable=False, server_default="accepted"),
    )
    op.add_column("users", sa.Column("invitation_expires_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("invitation_rejected_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users",
        sa.Column("invitation_renewal_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("invitation_code_hash", sa.String(255)))
    op.add_column(
        "users",
        sa.Column("invitation_code_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_stories",
        sa.Column("label", sa.String(80), nullable=False, server_default=""),
    )
    op.add_column(
        "story_tasks",
        sa.Column("logged_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "story_tasks",
        sa.Column("label", sa.String(80), nullable=False, server_default=""),
    )
    op.execute("UPDATE story_tasks SET status = 'TODO' WHERE status = 'todo'")
    op.create_table(
        "task_time_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("story_tasks.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("hours_spent", sa.Numeric(4, 2), nullable=False),
        sa.Column("comment", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_time_logs_task_id", "task_time_logs", ["task_id"])
    op.create_table(
        "task_status_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("story_tasks.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("previous_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_status_history_task_id", "task_status_history", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_status_history_task_id", "task_status_history")
    op.drop_table("task_status_history")
    op.drop_index("ix_task_time_logs_task_id", "task_time_logs")
    op.drop_table("task_time_logs")
    op.drop_column("story_tasks", "label")
    op.drop_column("story_tasks", "logged_hours")
    op.drop_column("user_stories", "label")
    op.drop_column("users", "invitation_code_attempts")
    op.drop_column("users", "invitation_code_hash")
    op.drop_column("users", "invitation_renewal_count")
    op.drop_column("users", "invitation_rejected_at")
    op.drop_column("users", "invitation_expires_at")
    op.drop_column("users", "invitation_status")
