"""EP-11 issue-task linking, optimistic lock versioning, and transactional outbox.

Revision ID: 021_ep11_issue_task_outbox
Revises: 020_ep11_issues_and_evidences
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_ep11_issue_task_outbox"
down_revision: str | None = "020_ep11_issues_and_evidences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("fixes") as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("resolved_by", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_foreign_key(
            "fk_fixes_task_id", "story_tasks", ["task_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_foreign_key(
            "fk_fixes_resolved_by", "users", ["resolved_by"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_fixes_task_id", ["task_id"])

    with op.batch_alter_table("story_tasks") as batch_op:
        batch_op.add_column(
            sa.Column("status_before_correction", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_status_created",
        "outbox_events",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_created", table_name="outbox_events")
    op.drop_table("outbox_events")

    with op.batch_alter_table("story_tasks") as batch_op:
        batch_op.drop_column("version")
        batch_op.drop_column("status_before_correction")

    with op.batch_alter_table("fixes") as batch_op:
        batch_op.drop_index("ix_fixes_task_id")
        batch_op.drop_constraint("fk_fixes_resolved_by", type_="foreignkey")
        batch_op.drop_constraint("fk_fixes_task_id", type_="foreignkey")
        batch_op.drop_column("version")
        batch_op.drop_column("resolved_by")
        batch_op.drop_column("task_id")
