"""EP-14: align notifications table with transactional delivery contract.

Revision ID: 026_ep14_notifications
Revises: 025_fix01_dor_dod_kb
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "026_ep14_notifications"
down_revision: str | None = "025_fix01_dor_dod_kb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    if context.is_offline_mode():
        return False
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(col["name"] == column for col in insp.get_columns(table))


def _has_index(table: str, name: str) -> bool:
    if context.is_offline_mode():
        return False
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(idx["name"] == name for idx in insp.get_indexes(table))


def upgrade() -> None:
    if not _has_column("notifications", "event_key"):
        op.add_column(
            "notifications",
            sa.Column("event_key", sa.String(length=200), nullable=True),
        )
    if not _has_column("notifications", "actor_id"):
        op.add_column(
            "notifications",
            sa.Column("actor_id", sa.String(length=36), nullable=True),
        )
    if not _has_column("notifications", "project_id"):
        op.add_column(
            "notifications",
            sa.Column("project_id", sa.String(length=36), nullable=True),
        )
    if not _has_column("notifications", "entity_type"):
        op.add_column(
            "notifications",
            sa.Column("entity_type", sa.String(length=30), nullable=True),
        )
    if not _has_column("notifications", "entity_id"):
        op.add_column(
            "notifications",
            sa.Column("entity_id", sa.String(length=36), nullable=True),
        )
    if not _has_column("notifications", "read_at"):
        op.add_column(
            "notifications",
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column("notifications", "expires_at"):
        op.add_column(
            "notifications",
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )

    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else "sqlite"
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE notifications
                SET event_key = COALESCE(event_key, 'legacy:' || id || '\:1'),
                    entity_type = COALESCE(entity_type, 'legacy'),
                    entity_id = COALESCE(entity_id, id),
                    read_at = CASE WHEN is_read THEN created_at ELSE read_at END,
                    expires_at = COALESCE(expires_at, created_at + INTERVAL '180 days')
                """
            )
        )
    else:
        op.execute(
            sa.text(
                """
                UPDATE notifications
                SET event_key = COALESCE(event_key, 'legacy:' || id || '\:1'),
                    entity_type = COALESCE(entity_type, 'legacy'),
                    entity_id = COALESCE(entity_id, id),
                    read_at = CASE WHEN is_read THEN created_at ELSE read_at END,
                    expires_at = COALESCE(expires_at, datetime(created_at, '+180 days'))
                """
            )
        )

    # Normalize historical type strings to EP-14 catalog values.
    op.execute(
        sa.text(
            """
            UPDATE notifications SET type = 'ISSUE_REPORTED'
            WHERE type IN ('issue_created', 'task_fix_reported');
            UPDATE notifications SET type = 'ISSUE_ASSIGNED' WHERE type = 'issue_assigned';
            UPDATE notifications SET type = 'MEETING_SCHEDULED' WHERE type = 'meeting_scheduled';
            UPDATE notifications SET type = 'MEETING_CANCELLED' WHERE type = 'meeting_cancelled';
            UPDATE notifications SET type = UPPER(type)
            WHERE type IN ('task_assigned', 'TASK_ASSIGNED');
            """
        )
    )

    with op.batch_alter_table("notifications") as batch:
        batch.alter_column("event_key", existing_type=sa.String(200), nullable=False)
        batch.alter_column("entity_type", existing_type=sa.String(30), nullable=False)
        batch.alter_column("entity_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("title", existing_type=sa.String(200), type_=sa.String(120))
        batch.alter_column("message", existing_type=sa.String(1000), type_=sa.String(300))

    if _has_index("notifications", "ix_notifications_is_read"):
        op.drop_index("ix_notifications_is_read", table_name="notifications")

    if _has_column("notifications", "is_read"):
        with op.batch_alter_table("notifications") as batch:
            batch.drop_column("is_read")

    if not _has_index("notifications", "uq_notification_event_recipient"):
        op.create_unique_constraint(
            "uq_notification_event_recipient",
            "notifications",
            ["event_key", "recipient_id"],
        )

    if not _has_index("notifications", "ix_notif_recipient_created"):
        op.create_index(
            "ix_notif_recipient_created",
            "notifications",
            ["recipient_id", "created_at", "id"],
        )

    if not _has_index("notifications", "ix_notif_unread"):
        op.create_index("ix_notif_unread", "notifications", ["recipient_id", "read_at"])
    if not _has_index("notifications", "ix_notif_expiry"):
        op.create_index("ix_notif_expiry", "notifications", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_notif_expiry", table_name="notifications")
    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else "sqlite"
    if dialect == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_notif_unread"))
    elif _has_index("notifications", "ix_notif_unread"):
        op.drop_index("ix_notif_unread", table_name="notifications")
    op.drop_index("ix_notif_recipient_created", table_name="notifications")
    op.drop_constraint("uq_notification_event_recipient", "notifications", type_="unique")

    default = sa.false() if dialect == "postgresql" else "0"
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("is_read", sa.Boolean(), nullable=False, server_default=default))
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "UPDATE notifications SET is_read = CASE "
                "WHEN read_at IS NOT NULL THEN TRUE ELSE FALSE END"
            )
        )
    else:
        op.execute(
            sa.text(
                "UPDATE notifications SET is_read = CASE WHEN read_at IS NOT NULL THEN 1 ELSE 0 END"
            )
        )
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("expires_at")
        batch.drop_column("read_at")
        batch.drop_column("entity_id")
        batch.drop_column("entity_type")
        batch.drop_column("project_id")
        batch.drop_column("actor_id")
        batch.drop_column("event_key")
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
