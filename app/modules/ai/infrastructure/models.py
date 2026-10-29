"""ORM models for AI quota tracking and chat history (EP-10)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class SystemConfigModel(Base):
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)


class AiDailyUsageModel(Base):
    __tablename__ = "ai_daily_usage"

    service: Mapped[str] = mapped_column(String(20), primary_key=True)
    usage_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)


class AiChatMessageModel(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    input_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
