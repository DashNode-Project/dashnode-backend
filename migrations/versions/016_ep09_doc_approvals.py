"""EP-09 Documentation visibility and approval workflow (HU 82-86).

Revision ID: 016_ep09_doc_approvals
Revises: 015_ep09_documentation_entries
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "016_ep09_doc_approvals"
down_revision: str | None = "015_ep09_documentation_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column(
            "documentation_entries",
            sa.Column(
                "is_visible_to_devs",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
        op.add_column(
            "documentation_entries",
            sa.Column("rejection_reason", sa.Text(), nullable=True),
        )
        return

    # Check if columns already exist (in case partial transaction)
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_cols = [c["name"] for c in insp.get_columns("documentation_entries")]

    if "is_visible_to_devs" not in existing_cols:
        op.add_column(
            "documentation_entries",
            sa.Column(
                "is_visible_to_devs",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
    if "rejection_reason" not in existing_cols:
        op.add_column(
            "documentation_entries",
            sa.Column("rejection_reason", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("documentation_entries", "rejection_reason")
    op.drop_column("documentation_entries", "is_visible_to_devs")
