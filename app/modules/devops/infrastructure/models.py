"""DevOps pipeline ORM models (EP-16)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class DevopsPipelineRunModel(Base):
    __tablename__ = "devops_pipeline_runs"
    __table_args__ = (Index("ix_devops_runs_project_latest", "project_id", "created_at", "id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger: Mapped[str] = mapped_column(String(10), nullable=False)
    triggered_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DevopsPipelineStageRunModel(Base):
    __tablename__ = "devops_pipeline_stage_runs"
    __table_args__ = (
        Index("ix_devops_stage_run", "run_id", "position"),
        UniqueConstraint("run_id", "stage", name="uq_devops_stage_run_stage"),
        UniqueConstraint("run_id", "position", name="uq_devops_stage_run_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("devops_pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(10), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
