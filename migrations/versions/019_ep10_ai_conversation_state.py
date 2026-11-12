"""EP-10 assistant conversational state per user.

Revision ID: 019_ep10_ai_conversation_state
Revises: 018_ep10_ai_chat_history
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "019_ep10_ai_conversation_state"
down_revision: str | None = "018_ep10_ai_chat_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_table(
            "ai_conversation_state",
            sa.Column("user_id", sa.String(length=36), primary_key=True),
            sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        )
        return
    op.create_table(
        "ai_conversation_state",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("ai_conversation_state")
