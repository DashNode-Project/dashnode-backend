"""Project EP-03 fields, soft delete, audit logs

Revision ID: 005_project_ep03_fields
Revises: 004_user_avatar
Create Date: 2026-10-12 20:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_project_ep03_fields"
down_revision: str | None = "004_user_avatar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "projects",
        "description",
        existing_type=sa.String(1000),
        type_=sa.String(2000),
        existing_nullable=False,
        existing_server_default="",
    )
    op.add_column(
        "projects",
        sa.Column("manager_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("priority", sa.String(20), nullable=False, server_default="media"),
    )
    op.add_column(
        "projects",
        sa.Column("tech_stack", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "projects",
        sa.Column("meeting_link", sa.String(500), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("status", sa.String(30), nullable=False, server_default="planificacion"),
    )
    op.add_column(
        "projects",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE projects SET manager_id = owner_id WHERE manager_id IS NULL")
    op.alter_column("projects", "manager_id", nullable=False)
    op.create_index("ix_projects_manager_id", "projects", ["manager_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_deleted_at", "projects", ["deleted_at"])

    op.add_column(
        "tasks",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_deleted_at", "tasks", ["deleted_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_tasks_deleted_at", table_name="tasks")
    op.drop_column("tasks", "deleted_at")
    op.drop_index("ix_projects_deleted_at", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_manager_id", table_name="projects")
    op.drop_column("projects", "deleted_at")
    op.drop_column("projects", "status")
    op.drop_column("projects", "meeting_link")
    op.drop_column("projects", "tech_stack")
    op.drop_column("projects", "priority")
    op.drop_column("projects", "manager_id")
    op.alter_column(
        "projects",
        "description",
        existing_type=sa.String(2000),
        type_=sa.String(1000),
        existing_nullable=False,
        existing_server_default="",
    )
