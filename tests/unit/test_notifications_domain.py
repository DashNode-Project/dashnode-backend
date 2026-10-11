"""
Unit tests for Notifications domain entities.
@sad AD-08, 4.1.4
"""

from datetime import UTC, datetime

from app.modules.notifications.domain.entities import Notification, NotificationType


def test_notification_creation_and_mark_as_read() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    notification = Notification(
        id="notif-1",
        recipient_id="usr-1",
        type=NotificationType.TASK_ASSIGNED,
        title="Task Assigned",
        message="You have been assigned to task #42",
        is_read=False,
        created_at=now,
    )
    assert notification.is_read is False

    notification.mark_as_read()
    assert notification.is_read is True
