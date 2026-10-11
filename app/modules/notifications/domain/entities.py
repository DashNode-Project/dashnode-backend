"""
Domain entities and value objects for Notifications module.
@sad AD-08, 4.1.4
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NotificationType(StrEnum):
    TASK_ASSIGNED = "task_assigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    PROJECT_MEMBER_ADDED = "project_member_added"


@dataclass
class Notification:
    id: str
    recipient_id: str
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime

    def mark_as_read(self) -> None:
        """Marks the notification as read."""
        self.is_read = True
