"""Transactional Outbox ORM model and repository helper.

@sad AD-08, AD-09
@origin [User Stories HU_DN_07_102 .. HU_DN_07_105]
"""

import json
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.shared.infrastructure.database import Base


class OutboxEventModel(Base):
    """Durable transactional outbox record for asynchronous domain notifications."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_created", "status", "created_at"),
        Index("ix_outbox_events_aggregate", "aggregate_type", "aggregate_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SqlAlchemyOutboxStore:
    """Enqueues outbox events inside the active database transaction without committing."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue_event(
        self,
        *,
        event_id: str,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, object],
        created_at: datetime,
    ) -> None:
        record = OutboxEventModel(
            id=event_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            status="pending",
            created_at=created_at,
            processed_at=None,
        )
        self._session.add(record)
        self._session.flush()
