"""Per-user AI chat history with TTL purge (EP-10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.ai.application.dtos import ChatHistoryMessage
from app.modules.ai.infrastructure.models import AiChatMessageModel
from app.shared.application.ports import Clock
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator


class SqlAlchemyChatHistoryRepository:
    def __init__(self, session: Session, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()
        self._ids = UuidGenerator()

    def purge_expired(self, user_id: str) -> None:
        cutoff = self._clock.now() - timedelta(hours=settings.AI_CHAT_RETENTION_HOURS)
        self._session.execute(
            delete(AiChatMessageModel).where(
                AiChatMessageModel.user_id == user_id,
                AiChatMessageModel.created_at < cutoff,
            )
        )
        self._session.flush()

    def list_for_user(self, user_id: str) -> list[ChatHistoryMessage]:
        self.purge_expired(user_id)
        cutoff = self._clock.now() - timedelta(hours=settings.AI_CHAT_RETENTION_HOURS)
        rows = self._session.scalars(
            select(AiChatMessageModel)
            .where(
                AiChatMessageModel.user_id == user_id,
                AiChatMessageModel.created_at >= cutoff,
            )
            .order_by(AiChatMessageModel.created_at.asc())
        ).all()
        return [_to_dto(row) for row in rows]

    def append(
        self,
        user_id: str,
        *,
        role: str,
        text: str,
        input_source: str | None = None,
    ) -> ChatHistoryMessage:
        self.purge_expired(user_id)
        now = self._clock.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        row = AiChatMessageModel(
            id=self._ids.generate(),
            user_id=user_id,
            role=role,
            text=text,
            input_source=input_source,
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return _to_dto(row)


def _to_dto(row: AiChatMessageModel) -> ChatHistoryMessage:
    return ChatHistoryMessage(
        id=row.id,
        role=row.role,  # type: ignore[arg-type]
        text=row.text,
        input_source=row.input_source,  # type: ignore[arg-type]
        created_at=row.created_at,
    )
