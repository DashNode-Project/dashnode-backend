"""Transactional notification writer (EP-14 DN-14-01 .. DN-14-06)."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.modules.notifications.application.catalog import (
    ENTITY_BY_TYPE,
    TITLE_BY_TYPE,
    NotificationEventType,
)
from app.modules.notifications.infrastructure.models import NotificationModel
from app.shared.application.ports import Clock, IdGenerator

logger = logging.getLogger("dashnode.notifications")

_RETENTION_DAYS = 180
_MAX_NAME_LEN = 60


def _truncate(name: str) -> str:
    clean = (name or "").strip()
    if len(clean) <= _MAX_NAME_LEN:
        return clean
    return clean[: _MAX_NAME_LEN - 1] + "…"


def _escape(value: str) -> str:
    return html.escape(_truncate(value), quote=True)


@dataclass(frozen=True)
class NotificationEvent:
    type: NotificationEventType
    event_key: str
    project_id: str | None
    entity_id: str
    actor_id: str | None
    context: dict[str, str]


class NotificationService:
    """Creates notification rows inside the caller transaction."""

    def __init__(self, session: Session, id_gen: IdGenerator, clock: Clock) -> None:
        self._session = session
        self._id_gen = id_gen
        self._clock = clock

    def notify(
        self,
        *,
        event: NotificationEvent,
        recipients: list[str],
        actor_id: str | None,
    ) -> int:
        unique_recipients = {
            r for r in recipients if r and (actor_id is None or r != actor_id)
        }
        if not unique_recipients:
            return 0

        title = TITLE_BY_TYPE[event.type]
        message = self._render_message(event)
        now = self._clock.now()
        expires_at = now + timedelta(days=_RETENTION_DAYS)
        entity_type = ENTITY_BY_TYPE[event.type]

        rows = [
            {
                "id": self._id_gen.generate(),
                "recipient_id": recipient_id,
                "actor_id": actor_id,
                "type": event.type.value,
                "event_key": event.event_key,
                "project_id": event.project_id,
                "entity_type": entity_type,
                "entity_id": event.entity_id,
                "title": title[:120],
                "message": message[:300],
                "created_at": now,
                "read_at": None,
                "expires_at": expires_at,
            }
            for recipient_id in unique_recipients
        ]

        dialect = self._session.bind.dialect.name if self._session.bind is not None else "sqlite"
        if dialect == "postgresql":
            stmt = (
                pg_insert(NotificationModel)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["event_key", "recipient_id"])
            )
        else:
            stmt = (
                sqlite_insert(NotificationModel)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["event_key", "recipient_id"])
            )
        result = self._session.execute(stmt)
        inserted = int(result.rowcount or 0)
        if recipients and not unique_recipients:
            logger.info(
                "notification_skipped_actor_only type=%s entity=%s",
                event.type.value,
                event.entity_id,
            )
        elif event.type == NotificationEventType.ISSUE_REPORTED and not unique_recipients:
            logger.warning(
                "notification_no_managers project=%s issue=%s",
                event.project_id,
                event.entity_id,
            )
        return inserted

    def _render_message(self, event: NotificationEvent) -> str:
        ctx = {k: _escape(v) for k, v in event.context.items()}
        project = ctx.get("project", "el proyecto")
        if event.type == NotificationEventType.TASK_ASSIGNED:
            task = ctx.get("task", "la tarea")
            return f'Se le asignó la tarea "{task}" en {project}.'
        if event.type == NotificationEventType.SPRINT_STARTED:
            sprint = ctx.get("sprint", "el sprint")
            return f'El sprint "{sprint}" de {project} inició.'
        if event.type == NotificationEventType.ISSUE_REPORTED:
            issue = ctx.get("issue", "un issue")
            severity = ctx.get("severity", "—")
            return f'"{issue}" fue reportado en {project} con severidad {severity}.'
        if event.type == NotificationEventType.ISSUE_ASSIGNED:
            issue = ctx.get("issue", "un issue")
            return f'Se le asignó el issue "{issue}" en {project}.'
        if event.type == NotificationEventType.MEETING_SCHEDULED:
            meeting = ctx.get("meeting", "la reunión")
            when = ctx.get("when", "")
            return f'"{meeting}" el {when}.'
        if event.type == NotificationEventType.MEETING_CANCELLED:
            meeting = ctx.get("meeting", "la reunión")
            when = ctx.get("when", "")
            return f'"{meeting}" del {when} fue cancelada.'
        if event.type == NotificationEventType.DOC_APPROVED:
            entry = ctx.get("entry", "su entrada")
            return f'Su entrada "{entry}" fue aprobada.'
        if event.type == NotificationEventType.DOC_REJECTED:
            entry = ctx.get("entry", "su entrada")
            return f'Su entrada "{entry}" fue rechazada.'
        return "Tiene una nueva notificación."