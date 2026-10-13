"""Domain entities and value objects for Availability and Meetings."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TimeSlot:
    """Represents a continuous time slot [start, end) in 'HH:MM' 24-hour format."""

    start: str
    end: str


@dataclass
class UserAvailability:
    """Weekly availability configuration registered by a user."""

    id: str
    user_id: str
    week_start_date: str  # Format: 'YYYY-MM-DD' representing Monday
    slots: dict[str, list[TimeSlot]]  # day_key -> list of TimeSlot
    created_at: datetime
    updated_at: datetime


VALID_MEETING_TYPES: tuple[str, ...] = ("Daily", "Planning", "Review", "Retro", "General")
VALID_PARTICIPANT_RESPONSES: tuple[str, ...] = ("pendiente", "aceptada", "rechazada")


@dataclass
class MeetingParticipant:
    """Participant in a meeting with their response status."""

    user_id: str
    response: str = "pendiente"  # 'pendiente', 'aceptada', 'rechazada'


@dataclass
class Meeting:
    """Scheduled meeting entity."""

    id: str
    project_id: str | None
    title: str
    description: str
    date: str  # Format: 'YYYY-MM-DD'
    start_time: str  # Format: 'HH:MM'
    end_time: str  # Format: 'HH:MM'
    duration: int  # minutes
    link: str | None
    status: str  # 'scheduled', 'completed', 'cancelled'
    creator_id: str
    participant_ids: list[str]
    created_at: datetime
    updated_at: datetime
    type: str = "General"
    summary: str | None = None
    minutes_url: str | None = None
