"""Availability and meetings schema (EP-04 and EP-05).

Revision ID: 006_availability_and_meetings
Revises: 005_project_ep03_fields
Create Date: 2026-10-12 23:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_availability_and_meetings"
down_revision: str | None = "005_project_ep03_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_availabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("week_start_date", sa.String(10), nullable=False),
        sa.Column("slots_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_availabilities_user_id", "user_availabilities", ["user_id"])
    op.create_index(
        "ix_user_availabilities_user_week",
        "user_availabilities",
        ["user_id", "week_start_date"],
        unique=True,
    )

    op.create_table(
        "meetings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("end_time", sa.String(5), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="scheduled"),
        sa.Column(
            "creator_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_meetings_date", "meetings", ["date"])
    op.create_index("ix_meetings_creator_id", "meetings", ["creator_id"])
    op.create_index("ix_meetings_project_id", "meetings", ["project_id"])

    op.create_table(
        "meeting_participants",
        sa.Column(
            "meeting_id",
            sa.String(36),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_meeting_participants_user_id", "meeting_participants", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_participants_user_id", table_name="meeting_participants")
    op.drop_table("meeting_participants")

    op.drop_index("ix_meetings_project_id", table_name="meetings")
    op.drop_index("ix_meetings_creator_id", table_name="meetings")
    op.drop_index("ix_meetings_date", table_name="meetings")
    op.drop_table("meetings")

    op.drop_index("ix_user_availabilities_user_week", table_name="user_availabilities")
    op.drop_index("ix_user_availabilities_user_id", table_name="user_availabilities")
    op.drop_table("user_availabilities")
