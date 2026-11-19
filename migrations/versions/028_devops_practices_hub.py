"""EP-16 DevOps practices hub — drop pipeline simulator, add profile + revisions.

Revision ID: 028_devops_practices_hub
Revises: 027_ep15_16_cmd_devops
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_devops_practices_hub"
down_revision: str | None = "027_ep15_16_cmd_devops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS devops_pipeline_stage_runs CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS devops_pipeline_runs CASCADE"))
    op.execute(sa.text("DELETE FROM system_configs WHERE key LIKE 'devops_%'"))

    op.create_table(
        "project_devops_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repository_url", sa.String(length=500), nullable=True),
        sa.Column("ci_cd_provider", sa.String(length=100), nullable=True),
        sa.Column("branching_strategy", sa.String(length=100), nullable=True),
        sa.Column("branching_rules_md", sa.Text(), nullable=True),
        sa.Column(
            "pipeline_stages",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "environments",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("quality_gates_md", sa.Text(), nullable=True),
        sa.Column("deployment_runbook_md", sa.Text(), nullable=True),
        sa.Column("rollback_observability_md", sa.Text(), nullable=True),
        sa.Column(
            "updated_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("project_id", name="uq_project_devops_profiles_project_id"),
    )

    op.create_table(
        "project_devops_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "profile_id",
            sa.String(length=36),
            sa.ForeignKey("project_devops_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "changed_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("change_summary", sa.String(length=255), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_project_devops_revisions_project_created",
        "project_devops_revisions",
        ["project_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_devops_revisions_project_created",
        table_name="project_devops_revisions",
    )
    op.drop_table("project_devops_revisions")
    op.drop_table("project_devops_profiles")
    # Simulator tables are not restored on downgrade (EP-16 replaced simulation).
