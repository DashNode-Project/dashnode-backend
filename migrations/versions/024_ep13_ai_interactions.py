"""EP-13 AI interaction registry, ratings and metrics access log.

Revision ID: 024_ep13_ai_interactions
Revises: 023_ep12_ai_usage_len
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024_ep13_ai_interactions"
down_revision: str | None = "023_ep12_ai_usage_len"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("request_text", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("model_id", sa.String(length=80), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audio_duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("counts_as_usage", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ai_interactions_user_created", "ai_interactions", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_ai_interactions_project_created", "ai_interactions", ["project_id", "created_at"]
    )
    op.create_index("ix_ai_interactions_source", "ai_interactions", ["source"])

    op.create_table(
        "ai_interaction_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "interaction_id",
            sa.String(length=36),
            sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_id", sa.String(length=80), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audio_duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_interaction_steps_parent", "ai_interaction_steps", ["interaction_id"])

    op.create_table(
        "ai_ratings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "interaction_id",
            sa.String(length=36),
            sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rated_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("interaction_id", name="uq_ai_ratings_interaction"),
    )

    op.create_table(
        "ai_registry_access_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "accessor_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("period_key", sa.String(length=20), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ai_registry_access_user",
        "ai_registry_access_log",
        ["accessor_user_id", "created_at"],
    )

    if not _has_column("ai_analyses", "interaction_id"):
        op.add_column(
            "ai_analyses",
            sa.Column(
                "interaction_id",
                sa.String(length=36),
                sa.ForeignKey("ai_interactions.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if _has_column("ai_analyses", "interaction_id"):
        op.drop_column("ai_analyses", "interaction_id")
    op.drop_index("ix_ai_registry_access_user", table_name="ai_registry_access_log")
    op.drop_table("ai_registry_access_log")
    op.drop_table("ai_ratings")
    op.drop_index("ix_ai_interaction_steps_parent", table_name="ai_interaction_steps")
    op.drop_table("ai_interaction_steps")
    op.drop_index("ix_ai_interactions_source", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_project_created", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_user_created", table_name="ai_interactions")
    op.drop_table("ai_interactions")