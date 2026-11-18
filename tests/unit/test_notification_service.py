"""Unit tests for EP-14 NotificationService."""

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.modules.notifications.application.catalog import NotificationEventType
from app.modules.notifications.application.notification_service import NotificationEvent, NotificationService
from app.modules.notifications.infrastructure.models import NotificationModel
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator


def test_notify_excludes_actor_and_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    clock = SystemClock()
    id_gen = UuidGenerator()
    with Session(engine) as session:
        service = NotificationService(session, id_gen, clock)
        event = NotificationEvent(
            type=NotificationEventType.TASK_ASSIGNED,
            event_key="TASK_ASSIGNED:t1:1",
            project_id="p1",
            entity_id="t1",
            actor_id="actor",
            context={"task": "Demo", "project": "DashNode"},
        )
        first = service.notify(event=event, recipients=["actor", "dev1"], actor_id="actor")
        second = service.notify(event=event, recipients=["dev1"], actor_id="actor")
        session.commit()
        assert first == 1
        assert second == 0
        rows = session.scalars(select(NotificationModel)).all()
        assert len(rows) == 1
        assert rows[0].recipient_id == "dev1"
        assert rows[0].actor_id == "actor"