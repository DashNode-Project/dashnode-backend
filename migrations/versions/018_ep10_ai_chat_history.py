"""EP-10 per-user AI chat history with 24h retention.

Revision ID: 018_ep10_ai_chat_history
Revises: 017_ep10_ai_quotas
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "018_ep10_ai_chat_history"
down_revision: str | None = "017_ep10_ai_quotas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_table(
            "ai_chat_messages",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("input_source", sa.String(length=8), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        return

    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("input_source", sa.String(length=8), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_chat_messages")
