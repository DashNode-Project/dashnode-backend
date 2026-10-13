"""Meeting fields and participant responses schema (EP-05 HU_DN_03_37..41).

Revision ID: 007_meeting_fields_and_responses
Revises: 006_availability_and_meetings
Create Date: 2026-10-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_meeting_fields_and_responses"
down_revision: str | None = "006_availability_and_meetings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("type", sa.String(50), nullable=False, server_default="General"),
    )
    op.add_column(
        "meetings",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "meetings",
        sa.Column("minutes_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "meeting_participants",
        sa.Column("response", sa.String(20), nullable=False, server_default="pendiente"),
    )


def downgrade() -> None:
    op.drop_column("meeting_participants", "response")
    op.drop_column("meetings", "minutes_url")
    op.drop_column("meetings", "summary")
    op.drop_column("meetings", "type")
