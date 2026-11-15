"""One-time password credential tokens (reset / activation)

Revision ID: 003_password_credential_tokens
Revises: 002_sessions_login_attempts
Create Date: 2026-10-12 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_password_credential_tokens"
down_revision: str | None = "002_sessions_login_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_credential_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_password_credential_tokens_user_id",
        "password_credential_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_password_credential_tokens_token_hash",
        "password_credential_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_password_credential_tokens_expires_at",
        "password_credential_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_password_credential_tokens_expires_at", "password_credential_tokens")
    op.drop_index("ix_password_credential_tokens_token_hash", "password_credential_tokens")
    op.drop_index("ix_password_credential_tokens_user_id", "password_credential_tokens")
    op.drop_table("password_credential_tokens")
