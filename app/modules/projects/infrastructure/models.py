"""
SQLAlchemy ORM models for Projects module.
@sad 5.6
@origin [SAD-Propuesto]
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class ProjectModel(Base):
    """Database representation of a Project."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_status", "status"),
        Index("ix_projects_deleted_at", "deleted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    manager_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="media")
    tech_stack: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planificacion")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectMemberModel(Base):
    """Database representation of a Project Member."""

    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLogModel(Base):
    """Append-only audit trail (RNF-SEG-07)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_resource", "resource_type", "resource_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
