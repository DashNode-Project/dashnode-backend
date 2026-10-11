"""
Use cases for Notifications management.
@sad AD-09, 4.1.4
@origin [SAD-Propuesto]
"""

from app.modules.notifications.application.dtos import (
    NotificationDTO,
    SendNotificationCommand,
)
from app.modules.notifications.domain.entities import Notification
from app.modules.notifications.domain.ports import NotificationRepository
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork


class SendNotificationUseCase:
    """Dispatches a new notification to a recipient."""

    def __init__(
        self,
        repo: NotificationRepository,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = repo
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(self, cmd: SendNotificationCommand) -> NotificationDTO:
        now = self._clock.now()
        notification_id = self._id_gen.generate()

        notification = Notification(
            id=notification_id,
            recipient_id=cmd.recipient_id,
            type=cmd.type,
            title=cmd.title.strip(),
            message=cmd.message.strip(),
            is_read=False,
            created_at=now,
        )

        with self._uow:
            self._repo.save(notification)
            self._uow.commit()

        return NotificationDTO(
            id=notification.id,
            recipient_id=notification.recipient_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )


class ListUserNotificationsUseCase:
    """Retrieves notifications for the recipient."""

    def __init__(self, repo: NotificationRepository) -> None:
        self._repo = repo

    def execute(
        self, recipient_id: str, unread_only: bool = False
    ) -> list[NotificationDTO]:
        items = self._repo.list_by_recipient(
            recipient_id=recipient_id, unread_only=unread_only
        )
        return [
            NotificationDTO(
                id=n.id,
                recipient_id=n.recipient_id,
                type=n.type,
                title=n.title,
                message=n.message,
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in items
        ]


class MarkNotificationAsReadUseCase:
    """Marks a notification as read if owned by the caller."""

    def __init__(
        self,
        repo: NotificationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._repo = repo
        self._uow = uow

    def execute(self, notification_id: str, recipient_id: str) -> NotificationDTO:
        notification = self._repo.get_by_id(notification_id)
        if notification is None:
            raise ValueError("Notificación no encontrada.")

        if notification.recipient_id != recipient_id:
            raise ValueError("No tienes permisos para modificar esta notificación.")

        notification.mark_as_read()

        with self._uow:
            self._repo.update(notification)
            self._uow.commit()

        return NotificationDTO(
            id=notification.id,
            recipient_id=notification.recipient_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
