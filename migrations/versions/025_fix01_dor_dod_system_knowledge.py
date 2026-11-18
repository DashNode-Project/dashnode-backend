"""FIX-01: DoR/DoD on user stories and system knowledge base.

Revision ID: 025_fix01_dor_dod_kb
Revises: 024_ep13_ai_interactions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_fix01_dor_dod_kb"
down_revision: str | None = "024_ep13_ai_interactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_stories",
        sa.Column("definition_of_ready", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "user_stories",
        sa.Column("definition_of_done", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "system_knowledge_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("answer_md", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(length=500), nullable=False, server_default=""),
        sa.Column(
            "author_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_system_knowledge_question",
        "system_knowledge_entries",
        ["question"],
    )


def downgrade() -> None:
    op.drop_index("ix_system_knowledge_question", table_name="system_knowledge_entries")
    op.drop_table("system_knowledge_entries")
    op.drop_column("user_stories", "definition_of_done")
    op.drop_column("user_stories", "definition_of_ready")
