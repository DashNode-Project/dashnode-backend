"""
SQLAlchemy repository implementation for Notifications.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
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
            is_read=model.is_read,
            created_at=model.created_at,
        )

    def save(self, notification: Notification) -> None:
        model = NotificationModel(
            id=notification.id,
            recipient_id=notification.recipient_id,
            type=notification.type.value,
            title=notification.title,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
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
            stmt = stmt.where(NotificationModel.is_read.is_(False))
        stmt = stmt.order_by(NotificationModel.created_at.desc())
        results = self._session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in results]

    def update(self, notification: Notification) -> None:
        stmt = select(NotificationModel).where(NotificationModel.id == notification.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is not None:
            model.is_read = notification.is_read
