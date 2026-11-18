"""EP-12 AI visual evidence analysis table and indexes.

Revision ID: 022_ep12_ai_analyses
Revises: 021_ep11_issue_task_outbox
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022_ep12_ai_analyses"
down_revision: str | None = "021_ep11_issue_task_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "issue_id",
            sa.String(length=36),
            sa.ForeignKey("fixes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.String(length=36),
            sa.ForeignKey("evidences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("progress_stage", sa.String(length=20), nullable=True),
        sa.Column("reuse_key", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=20), nullable=False),
        sa.Column("model_id", sa.String(length=80), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column(
            "validation_status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING_VALIDATION",
        ),
        sa.Column(
            "validated_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "rejected_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deleted_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_ai_analyses_issue_created",
        "ai_analyses",
        ["issue_id", "created_at"],
    )
    op.create_index(
        "ix_ai_analyses_reuse_key",
        "ai_analyses",
        ["reuse_key"],
    )
    op.create_index(
        "ix_ai_analyses_evidence",
        "ai_analyses",
        ["evidence_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_analyses_evidence", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_reuse_key", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_issue_created", table_name="ai_analyses")
    op.drop_table("ai_analyses")
