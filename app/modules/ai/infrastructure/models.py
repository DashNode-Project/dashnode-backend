"""ORM models for AI quota tracking (EP-10)."""

from datetime import date

from sqlalchemy import Date, Integer, String
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
