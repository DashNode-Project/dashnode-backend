"""SQLAlchemy ORM models for Availability and Meetings module."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class UserAvailabilityModel(Base):
    """Database representation of weekly user availability."""

    __tablename__ = "user_availabilities"
    __table_args__ = (
        Index("ix_user_availabilities_user_week", "user_id", "week_start_date", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    week_start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    slots_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MeetingModel(Base):
    """Database representation of a Meeting."""

    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_date", "date"),
        Index("ix_meetings_creator_id", "creator_id"),
        Index("ix_meetings_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="General", nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    minutes_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MeetingParticipantModel(Base):
    """Database representation of meeting participants."""

    __tablename__ = "meeting_participants"

    meeting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    response: Mapped[str] = mapped_column(String(20), default="pendiente", nullable=False)
