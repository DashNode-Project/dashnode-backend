"""EP-09 Documentation and Knowledge Base entries.

Revision ID: 015_ep09_documentation_entries
Revises: 014_ep08_kanban_wip_and_blocks
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_ep09_documentation_entries"
down_revision: str | None = "014_ep08_kanban_wip_and_blocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documentation_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("objective", sa.String(2000), nullable=True),
        sa.Column("tags", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("external_url", sa.String(1000), nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_documentation_entries_project_id",
        "documentation_entries",
        ["project_id"],
    )
    op.create_index(
        "ix_documentation_entries_author_id",
        "documentation_entries",
        ["author_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documentation_entries_author_id", table_name="documentation_entries")
    op.drop_index("ix_documentation_entries_project_id", table_name="documentation_entries")
    op.drop_table("documentation_entries")
