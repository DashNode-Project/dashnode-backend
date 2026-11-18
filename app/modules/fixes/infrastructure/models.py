"""SQLAlchemy models for EP-11 Issues and Evidences.

@sad AD-09, 5.6
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure.database import Base


class FixModel(Base):
    __tablename__ = "fixes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True, nullable=False)
    reporter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assignee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("story_tasks.id", ondelete="SET NULL"), index=True, nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evidences = relationship(
        "EvidenceModel",
        back_populates="fix",
        cascade="all, delete-orphan",
        order_by="EvidenceModel.created_at",
    )
    ai_analyses = relationship(
        "AiAnalysisModel",
        back_populates="fix",
        cascade="all, delete-orphan",
        order_by="AiAnalysisModel.created_at.desc()",
    )


class EvidenceModel(Base):
    __tablename__ = "evidences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fix_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fixes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    fix = relationship("FixModel", back_populates="evidences")
    ai_analyses = relationship(
        "AiAnalysisModel",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


class AiAnalysisModel(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        Index("ix_ai_analyses_issue_created", "issue_id", "created_at"),
        Index("ix_ai_analyses_evidence", "evidence_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    issue_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fixes.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evidences.id", ondelete="CASCADE"), nullable=False
    )
    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", server_default="PENDING", nullable=False
    )
    progress_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reuse_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING_VALIDATION",
        server_default="PENDING_VALIDATION",
        nullable=False,
    )
    validated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interaction_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ai_interactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    fix = relationship("FixModel", back_populates="ai_analyses")
    evidence = relationship("EvidenceModel", back_populates="ai_analyses")
