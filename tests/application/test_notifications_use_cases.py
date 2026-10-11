"""
Application tests for Notifications use cases.
@sad AD-09, 4.1.4
"""

from datetime import UTC, datetime

import pytest

from app.modules.notifications.application.dtos import SendNotificationCommand
from app.modules.notifications.application.use_cases import (
    ListUserNotificationsUseCase,
    MarkNotificationAsReadUseCase,
    SendNotificationUseCase,
)
from app.modules.notifications.domain.entities import Notification, NotificationType
from app.shared.application.ports import UnitOfWork


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[str, Notification] = {}

    def save(self, notification: Notification) -> None:
        self.notifications[notification.id] = notification

    def get_by_id(self, notification_id: str) -> Notification | None:
        return self.notifications.get(notification_id)

    def list_by_recipient(
        self, recipient_id: str, unread_only: bool = False
    ) -> list[Notification]:
        return [
            n for n in self.notifications.values()
            if n.recipient_id == recipient_id and (not unread_only or not n.is_read)
        ]

    def update(self, notification: Notification) -> None:
        self.notifications[notification.id] = notification


class FakeClock:
    def __init__(self, now_time: datetime) -> None:
        self._now = now_time

    def now(self) -> datetime:
        return self._now


class FakeIdGenerator:
    def __init__(self, fixed_id: str = "notif-999") -> None:
        self.fixed_id = fixed_id

    def generate(self) -> str:
        return self.fixed_id


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


def test_send_notification_use_case() -> None:
    repo = FakeNotificationRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    id_gen = FakeIdGenerator("notif-1")
    uow = FakeUnitOfWork()

    uc = SendNotificationUseCase(repo=repo, id_gen=id_gen, clock=clock, uow=uow)
    cmd = SendNotificationCommand(
        recipient_id="usr-1",
        type=NotificationType.TASK_ASSIGNED,
        title="New Task",
        message="Task assigned to you",
    )
    result = uc.execute(cmd)

    assert result.id == "notif-1"
    assert result.is_read is False
    assert uow.committed is True


def test_list_and_mark_notification() -> None:
    repo = FakeNotificationRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()

    notif = Notification(
        id="notif-1",
        recipient_id="usr-1",
        type=NotificationType.TASK_STATUS_CHANGED,
        title="Status Changed",
        message="Status updated to in-progress",
        is_read=False,
        created_at=clock.now(),
    )
    repo.save(notif)

    list_uc = ListUserNotificationsUseCase(repo=repo)
    user_notifs = list_uc.execute("usr-1", unread_only=True)
    assert len(user_notifs) == 1

    mark_uc = MarkNotificationAsReadUseCase(repo=repo, uow=uow)
    updated = mark_uc.execute(notification_id="notif-1", recipient_id="usr-1")
    assert updated.is_read is True
    assert uow.committed is True

    # Unauthorized mark attempt
    with pytest.raises(ValueError, match="No tienes permisos"):
        mark_uc.execute(notification_id="notif-1", recipient_id="other-user")
