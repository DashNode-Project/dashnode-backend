"""Manager-scoped developer invites and extended profile JSON.

Revision ID: 008_mgr_dev_profile
Revises: 007_meeting_fields_and_responses
Create Date: 2026-10-14 05:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_mgr_dev_profile"
down_revision: str | None = "007_meeting_fields_and_responses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("invited_by_user_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_invited_by_user_id",
        "users",
        "users",
        ["invited_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_invited_by_user_id", "users", ["invited_by_user_id"])
    op.add_column(
        "users",
        sa.Column("invitation_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "profile_details",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "profile_details")
    op.drop_column("users", "invitation_accepted_at")
    op.drop_index("ix_users_invited_by_user_id", table_name="users")
    op.drop_constraint("fk_users_invited_by_user_id", "users", type_="foreignkey")
    op.drop_column("users", "invited_by_user_id")
