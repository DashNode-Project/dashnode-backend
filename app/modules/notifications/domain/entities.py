"""
Domain entities and value objects for Notifications module.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NotificationType(StrEnum):
    TASK_ASSIGNED = "TASK_ASSIGNED"
    SPRINT_STARTED = "SPRINT_STARTED"
    ISSUE_REPORTED = "ISSUE_REPORTED"
    ISSUE_ASSIGNED = "ISSUE_ASSIGNED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    MEETING_CANCELLED = "MEETING_CANCELLED"
    DOC_APPROVED = "DOC_APPROVED"
    DOC_REJECTED = "DOC_REJECTED"


@dataclass
class Notification:
    id: str
    recipient_id: str
    type: NotificationType
    title: str
    message: str
    created_at: datetime
    read_at: datetime | None = None

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_as_read(self, when: datetime) -> None:
        if self.read_at is None:
            self.read_at = when
