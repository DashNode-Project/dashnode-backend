"""ORM models for EP-13 AI interaction registry and metrics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure.database import Base

# v1 deferral: daily rollups table `ai_metrics_daily` is not created; aggregate ad hoc.


class AiInteractionModel(Base):
    __tablename__ = "ai_interactions"
    __table_args__ = (
        Index("ix_ai_interactions_user_created", "user_id", "created_at"),
        Index("ix_ai_interactions_project_created", "project_id", "created_at"),
        Index("ix_ai_interactions_source", "source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    request_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    total_latency_ms: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    audio_duration_ms: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    counts_as_usage: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="1"
    )
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # v1: retention job deferred — column reserved for future purge cron.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps = relationship(
        "AiInteractionStepModel",
        back_populates="interaction",
        cascade="all, delete-orphan",
        order_by="AiInteractionStepModel.step_order",
    )
    rating = relationship(
        "AiRatingModel",
        back_populates="interaction",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AiInteractionStepModel(Base):
    __tablename__ = "ai_interaction_steps"
    __table_args__ = (Index("ix_ai_interaction_steps_parent", "interaction_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_interactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer(), nullable=False)
    step_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    audio_duration_ms: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    latency_ms: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    interaction = relationship("AiInteractionModel", back_populates="steps")


class AiRatingModel(Base):
    __tablename__ = "ai_ratings"
    __table_args__ = (UniqueConstraint("interaction_id", name="uq_ai_ratings_interaction"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_interactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    rated_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer(), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    interaction = relationship("AiInteractionModel", back_populates="rating")


class AiRegistryAccessLogModel(Base):
    __tablename__ = "ai_registry_access_log"
    __table_args__ = (Index("ix_ai_registry_access_user", "accessor_user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    accessor_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    period_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)