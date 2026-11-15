"""EP-10 AI quota configuration and daily usage counters (HU 95).

Revision ID: 017_ep10_ai_quotas
Revises: 016_ep09_doc_approvals
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "017_ep10_ai_quotas"
down_revision: str | None = "016_ep09_doc_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_table(
            "system_configs",
            sa.Column("key", sa.String(length=100), primary_key=True),
            sa.Column("value", sa.String(length=500), nullable=False),
        )
        op.create_table(
            "ai_daily_usage",
            sa.Column("service", sa.String(length=20), primary_key=True),
            sa.Column("usage_date", sa.Date(), primary_key=True),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        )
        return

    op.create_table(
        "system_configs",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False),
    )
    op.create_table(
        "ai_daily_usage",
        sa.Column("service", sa.String(length=20), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("service", "usage_date"),
    )
    configs = sa.table(
        "system_configs",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
    )
    op.bulk_insert(
        configs,
        [
            {"key": "ai_whisper_daily_limit", "value": "100"},
            {"key": "ai_gemini_daily_limit", "value": "100"},
        ],
    )


def downgrade() -> None:
    op.drop_table("ai_daily_usage")
    op.drop_table("system_configs")
