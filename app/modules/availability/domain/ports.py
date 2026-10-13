"""Repository and service ports for Availability domain."""

from dataclasses import dataclass
from typing import Protocol

from app.modules.availability.domain.entities import Meeting, UserAvailability


@dataclass(frozen=True)
class UserBasicInfo:
    id: str
    name: str
    email: str
    role: str


class AvailabilityRepository(Protocol):
    """Port for persisting and querying availability configurations and meetings."""

    def get_user_availability(
        self, user_id: str, week_start_date: str
    ) -> UserAvailability | None: ...

    def get_latest_availability(
        self, user_id: str, before_or_on_week: str
    ) -> UserAvailability | None: ...

    def save_user_availability(self, availability: UserAvailability) -> None: ...

    def list_availabilities_for_users(
        self, user_ids: list[str], week_start_date: str
    ) -> dict[str, UserAvailability]: ...

    def get_meetings_for_participants(
        self, user_ids: list[str], start_date: str, end_date: str
    ) -> list[Meeting]: ...

    def save_meeting(self, meeting: Meeting) -> None: ...


class TeamMembersLookup(Protocol):
    """Cross-cutting lookup for visible team members by role (orchestrated, BR-4)."""

    def get_visible_users(self, actor_id: str, role: str) -> list[UserBasicInfo]: ...

    def list_all_active_users(self) -> list[UserBasicInfo]: ...
