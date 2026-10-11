"""
FastAPI router for Notifications module.
Complies strictly with BR-1 (no direct DB/infrastructure imports) and BR-4.
@sad 4.1.4, AD-08
@origin [SAD-Propuesto]
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.notifications.application.dtos import (
    NotificationDTO,
    SendNotificationCommand,
)
from app.modules.notifications.application.use_cases import (
    ListUserNotificationsUseCase,
    MarkNotificationAsReadUseCase,
    SendNotificationUseCase,
)
from app.orchestration.notifications_container import (
    get_list_user_notifications_use_case,
    get_mark_notification_as_read_use_case,
    get_send_notification_use_case,
)
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "",
    response_model=NotificationDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar una nueva notificación",
)
def send_notification(
    cmd: SendNotificationCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: SendNotificationUseCase = Depends(get_send_notification_use_case),
) -> NotificationDTO:
    try:
        return use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "",
    response_model=list[NotificationDTO],
    summary="Listar notificaciones del usuario autenticado",
)
def list_notifications(
    unread_only: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListUserNotificationsUseCase = Depends(
        get_list_user_notifications_use_case
    ),
) -> list[NotificationDTO]:
    return use_case.execute(recipient_id=current_user.id, unread_only=unread_only)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationDTO,
    summary="Marcar notificación como leída",
)
def mark_as_read(
    notification_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: MarkNotificationAsReadUseCase = Depends(
        get_mark_notification_as_read_use_case
    ),
) -> NotificationDTO:
    try:
        return use_case.execute(
            notification_id=notification_id, recipient_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
