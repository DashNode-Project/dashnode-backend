"""
DTOs and Commands for Notifications application layer.
@sad AD-09, 4.1.4
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.notifications.domain.entities import NotificationType


class SendNotificationCommand(BaseModel):
    recipient_id: str
    type: NotificationType
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)


class NotificationDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipient_id: str
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime
