"""EP-06 backlog: epics, user stories, story tasks

Revision ID: 009_ep06_backlog_tar
Revises: 008_mgr_dev_profile
Create Date: 2026-10-20 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_ep06_backlog_tar"
down_revision: str | None = "008_mgr_dev_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "epics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_epics_project_id", "epics", ["project_id"])

    op.create_table(
        "user_stories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("epic_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("user_role", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("acceptance_criteria", sa.String(8000), nullable=False, server_default=""),
        sa.Column("moscow_priority", sa.String(20), nullable=False, server_default="must_have"),
        sa.Column("story_points", sa.Integer(), nullable=True),
        sa.Column("sprint_id", sa.String(36), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_stories_epic_id", "user_stories", ["epic_id"])
    op.create_index("ix_user_stories_project_id", "user_stories", ["project_id"])

    op.create_table(
        "story_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_story_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(50), nullable=False, server_default="todo"),
        sa.Column("assignee_id", sa.String(36), nullable=True),
        sa.Column("estimated_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_story_tasks_user_story_id", "story_tasks", ["user_story_id"])
    op.create_index("ix_story_tasks_project_id", "story_tasks", ["project_id"])
    op.create_index("ix_story_tasks_assignee_id", "story_tasks", ["assignee_id"])


def downgrade() -> None:
    op.drop_table("story_tasks")
    op.drop_table("user_stories")
    op.drop_table("epics")
