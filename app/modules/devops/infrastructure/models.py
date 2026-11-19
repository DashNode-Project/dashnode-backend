"""DevOps practices ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class ProjectDevOpsProfileModel(Base):
    __tablename__ = "project_devops_profiles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_project_devops_profiles_project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ci_cd_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    branching_strategy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    branching_rules_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_stages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    environments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    quality_gates_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_runbook_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_observability_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectDevOpsRevisionModel(Base):
    __tablename__ = "project_devops_revisions"
    __table_args__ = (
        Index("ix_project_devops_revisions_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_devops_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    change_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
