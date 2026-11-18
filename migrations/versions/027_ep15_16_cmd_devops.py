"""EP-15/16 DevOps pipeline tables and simulator config keys.

Revision ID: 027_ep15_16_cmd_devops
Revises: 026_ep14_notifications
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "027_ep15_16_cmd_devops"
down_revision: str | None = "026_ep14_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devops_pipeline_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(length=10), nullable=False),
        sa.Column(
            "triggered_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_simulated", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("is_simulated IS TRUE", name="ck_devops_runs_simulated_only"),
        sa.CheckConstraint(
            (
                "(trigger = 'SEED' AND triggered_by IS NULL) "
                "OR (trigger <> 'SEED' AND triggered_by IS NOT NULL)"
            ),
            name="ck_devops_runs_trigger_user",
        ),
    )
    op.create_index(
        "ix_devops_runs_project_latest", "devops_pipeline_runs", ["project_id", "created_at", "id"]
    )
    op.create_index(
        op.f("ix_devops_pipeline_runs_project_id"), "devops_pipeline_runs", ["project_id"]
    )

    op.create_table(
        "devops_pipeline_stage_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("devops_pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(length=10), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("outcome", sa.String(length=10), nullable=False),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("planned_end >= planned_start", name="ck_devops_stage_window"),
        sa.CheckConstraint("position BETWEEN 1 AND 4", name="ck_devops_stage_position"),
        sa.UniqueConstraint("run_id", "stage", name="uq_devops_stage_run_stage"),
        sa.UniqueConstraint("run_id", "position", name="uq_devops_stage_run_position"),
    )
    op.create_index("ix_devops_stage_run", "devops_pipeline_stage_runs", ["run_id", "position"])
    op.create_index(
        op.f("ix_devops_pipeline_stage_runs_run_id"), "devops_pipeline_stage_runs", ["run_id"]
    )

    if context.is_offline_mode():
        return

    configs = sa.table(
        "system_configs",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
    )
    op.bulk_insert(
        configs,
        [
            {"key": "devops_sim_success_lint", "value": "0.92"},
            {"key": "devops_sim_success_test", "value": "0.85"},
            {"key": "devops_sim_success_build", "value": "0.95"},
            {"key": "devops_sim_success_deploy", "value": "0.98"},
            {"key": "devops_sim_duration_lint_s", "value": "12"},
            {"key": "devops_sim_duration_test_s", "value": "48"},
            {"key": "devops_sim_duration_build_s", "value": "30"},
            {"key": "devops_sim_duration_deploy_s", "value": "20"},
            {"key": "devops_manual_run_cooldown_s", "value": "300"},
        ],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_devops_pipeline_stage_runs_run_id"), table_name="devops_pipeline_stage_runs"
    )
    op.drop_index("ix_devops_stage_run", table_name="devops_pipeline_stage_runs")
    op.drop_table("devops_pipeline_stage_runs")
    op.drop_index(op.f("ix_devops_pipeline_runs_project_id"), table_name="devops_pipeline_runs")
    op.drop_index("ix_devops_runs_project_latest", table_name="devops_pipeline_runs")
    op.drop_table("devops_pipeline_runs")
    op.execute(sa.text("DELETE FROM system_configs WHERE key LIKE 'devops_%'"))
