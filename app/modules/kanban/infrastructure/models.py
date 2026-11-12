"""SQLAlchemy models for Kanban (EP-08)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class KanbanColumnSettingsModel(Base):
    __tablename__ = "kanban_column_settings"
    __table_args__ = (
        UniqueConstraint("project_id", "column_id", name="uq_kanban_col_settings_proj_col"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    column_id: Mapped[str] = mapped_column(String(50), nullable=False)
    wip_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
