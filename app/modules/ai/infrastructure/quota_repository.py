"""Daily quota enforcement for Whisper and Gemini (HU 95)."""

from sqlalchemy.orm import Session

from app.config import settings
from app.modules.ai.application.use_cases import QuotaExhaustedError
from app.modules.ai.infrastructure.models import AiDailyUsageModel, SystemConfigModel
from app.shared.application.ports import Clock
from app.shared.infrastructure.clock import SystemClock


class SqlAlchemyQuotaRepository:
    def __init__(self, session: Session, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    def check_and_consume(self, service: str) -> None:
        limit = self._daily_limit(service)
        if limit <= 0:
            raise QuotaExhaustedError(service)
        today = self._clock.now().date()
        row = self._session.get(AiDailyUsageModel, {"service": service, "usage_date": today})
        current = row.count if row else 0
        if current >= limit:
            raise QuotaExhaustedError(service)
        if row is None:
            row = AiDailyUsageModel(service=service, usage_date=today, count=1)
            self._session.add(row)
        else:
            row.count = current + 1
        self._session.flush()

    def _daily_limit(self, service: str) -> int:
        key = "ai_whisper_daily_limit" if service == "WHISPER" else "ai_gemini_daily_limit"
        if service == "WHISPER":
            default = settings.AI_WHISPER_DAILY_LIMIT
        else:
            default = settings.AI_GEMINI_DAILY_LIMIT
        row = self._session.get(SystemConfigModel, key)
        if row is None:
            return default
        try:
            return int(row.value)
        except ValueError:
            return default

    def set_limit(self, key: str, value: int) -> None:
        row = self._session.get(SystemConfigModel, key)
        if row is None:
            self._session.add(SystemConfigModel(key=key, value=str(value)))
        else:
            row.value = str(value)
        self._session.flush()
