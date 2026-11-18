"""
SQLAlchemy repository implementation for Notifications (legacy use cases).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.notifications.domain.entities import Notification, NotificationType
from app.modules.notifications.domain.ports import NotificationRepository
from app.modules.notifications.infrastructure.models import NotificationModel


class SqlAlchemyNotificationRepository(NotificationRepository):
    """SQLAlchemy implementation of the NotificationRepository port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, model: NotificationModel) -> Notification:
        return Notification(
            id=model.id,
            recipient_id=model.recipient_id,
            type=NotificationType(model.type),
            title=model.title,
            message=model.message,
            created_at=model.created_at,
            read_at=model.read_at,
        )

    def save(self, notification: Notification) -> None:
        from datetime import timedelta

        expires = notification.created_at + timedelta(days=180)
        model = NotificationModel(
            id=notification.id,
            recipient_id=notification.recipient_id,
            type=notification.type.value,
            event_key=f"legacy:{notification.id}:1",
            project_id=None,
            entity_type="legacy",
            entity_id=notification.id,
            title=notification.title,
            message=notification.message,
            created_at=notification.created_at,
            read_at=notification.read_at,
            expires_at=expires,
        )
        self._session.add(model)

    def get_by_id(self, notification_id: str) -> Notification | None:
        stmt = select(NotificationModel).where(NotificationModel.id == notification_id)
        result = self._session.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return self._to_domain(result)

    def list_by_recipient(self, recipient_id: str, unread_only: bool = False) -> list[Notification]:
        stmt = select(NotificationModel).where(NotificationModel.recipient_id == recipient_id)
        if unread_only:
            stmt = stmt.where(NotificationModel.read_at.is_(None))
        stmt = stmt.order_by(NotificationModel.created_at.desc())
        results = self._session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in results]

    def update(self, notification: Notification) -> None:
        stmt = select(NotificationModel).where(NotificationModel.id == notification.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is not None:
            model.read_at = notification.read_at
