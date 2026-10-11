"""
Composition root for Notifications module use cases.
Maintains modular independence under BR-4.
@sad AD-09, HC-08
@origin [SAD-Propuesto]
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.notifications.application.use_cases import (
    ListUserNotificationsUseCase,
    MarkNotificationAsReadUseCase,
    SendNotificationUseCase,
)
from app.modules.notifications.infrastructure.repositories import (
    SqlAlchemyNotificationRepository,
)
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import (
    SqlAlchemyUnitOfWork,
)
from app.shared.infrastructure.database import (
    get_db_session as get_db,
)
from app.shared.infrastructure.id_generator import UuidGenerator

clock = SystemClock()
id_generator = UuidGenerator()


def get_send_notification_use_case(
    db: Session = Depends(get_db),
) -> SendNotificationUseCase:
    repo = SqlAlchemyNotificationRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return SendNotificationUseCase(
        repo=repo,
        id_gen=id_generator,
        clock=clock,
        uow=uow,
    )


def get_list_user_notifications_use_case(
    db: Session = Depends(get_db),
) -> ListUserNotificationsUseCase:
    repo = SqlAlchemyNotificationRepository(session=db)
    return ListUserNotificationsUseCase(repo=repo)


def get_mark_notification_as_read_use_case(
    db: Session = Depends(get_db),
) -> MarkNotificationAsReadUseCase:
    repo = SqlAlchemyNotificationRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return MarkNotificationAsReadUseCase(
        repo=repo,
        uow=uow,
    )
