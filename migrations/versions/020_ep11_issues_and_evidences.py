"""EP-11 Issues and Evidences tables.

Revision ID: 020_ep11_issues_and_evidences
Revises: 019_ep10_ai_conversation_state
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_ep11_issues_and_evidences"
down_revision: str | None = "019_ep10_ai_conversation_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fixes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False, index=True),
        sa.Column("type", sa.String(length=20), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open", index=True),
        sa.Column(
            "reporter_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assignee_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "evidences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "fix_id",
            sa.String(length=36),
            sa.ForeignKey("fixes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False, index=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column(
            "uploaded_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("evidences")
    op.drop_table("fixes")
