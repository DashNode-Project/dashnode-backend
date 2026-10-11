"""
Repository ports for Notifications domain.
@sad AD-09, 4.1.4
@origin [SAD-Propuesto]
"""

from typing import Protocol

from app.modules.notifications.domain.entities import Notification


class NotificationRepository(Protocol):
    """Port for persisting and querying Notification domain entities."""

    def save(self, notification: Notification) -> None:
        ...

    def get_by_id(self, notification_id: str) -> Notification | None:
        ...

    def list_by_recipient(
        self, recipient_id: str, unread_only: bool = False
    ) -> list[Notification]:
        ...

    def update(self, notification: Notification) -> None:
        ...
