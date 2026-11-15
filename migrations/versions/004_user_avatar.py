"""Optional avatar storage key on users (HU_DN_01_21)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_user_avatar"
down_revision: str | None = "003_password_credential_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_key", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_key")
