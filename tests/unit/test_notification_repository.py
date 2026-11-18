"""Legacy notification repository adapter."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.modules.notifications.domain.entities import Notification, NotificationType
from app.modules.notifications.infrastructure.models import NotificationModel
from app.modules.notifications.infrastructure.repositories import SqlAlchemyNotificationRepository
from app.shared.infrastructure.database import Base


def test_sqlalchemy_notification_repository_crud() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    with Session(engine) as session:
        repo = SqlAlchemyNotificationRepository(session)
        notif = Notification(
            id="n1",
            recipient_id="u1",
            type=NotificationType.TASK_ASSIGNED,
            title="Hola",
            message="Mensaje",
            created_at=now,
        )
        repo.save(notif)
        session.commit()

        loaded = repo.get_by_id("n1")
        assert loaded is not None
        assert loaded.title == "Hola"

        listed = repo.list_by_recipient("u1", unread_only=True)
        assert len(listed) == 1

        notif.mark_as_read(now)
        repo.update(notif)
        session.commit()
        assert repo.list_by_recipient("u1", unread_only=True) == []

        row = session.get(NotificationModel, "n1")
        assert row is not None
        assert row.read_at is not None
