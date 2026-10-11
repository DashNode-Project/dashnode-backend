"""
SQLAlchemy ORM models for Tasks module.
@sad 5.6
@origin [SAD-Propuesto]
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class TaskModel(Base):
    """Database representation of a Task."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(5000), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    creator_id: Mapped[str] = mapped_column(String(36), nullable=False)
    has_open_fix: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
