"""Repository and service ports for Availability domain."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.availability.domain.entities import Meeting, UserAvailability


@dataclass(frozen=True)
class UserBasicInfo:
    id: str
    name: str
    email: str
    role: str


@dataclass(frozen=True)
class ProjectBasicInfo:
    id: str
    name: str
    manager_id: str | None
    meeting_link: str | None
    member_ids: list[str]


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

    def get_meeting_by_id(self, meeting_id: str) -> Meeting | None: ...

    def list_all_meetings(self) -> list[Meeting]: ...

    def get_meetings_by_projects(self, project_ids: list[str]) -> list[Meeting]: ...

    def get_meetings_by_creator(self, creator_id: str) -> list[Meeting]: ...

    def update_meeting(self, meeting: Meeting) -> None: ...

    def cancel_scheduled_meetings_for_project(self, project_id: str, when: datetime) -> None: ...

    def get_participant_responses(self, meeting_id: str) -> dict[str, str]: ...

    def update_participant_response(self, meeting_id: str, user_id: str, response: str) -> None: ...

    def check_concurrent_meeting(
        self,
        participant_ids: list[str],
        date: str,
        start_time: str,
        end_time: str,
        exclude_meeting_id: str | None = None,
    ) -> bool: ...


class TeamMembersLookup(Protocol):
    """Cross-cutting lookup for visible team members by role (orchestrated, BR-4)."""

    def get_visible_users(self, actor_id: str, role: str) -> list[UserBasicInfo]: ...

    def list_all_active_users(self) -> list[UserBasicInfo]: ...


class ProjectLookup(Protocol):
    """Cross-cutting lookup for projects and project members (orchestrated, BR-4)."""

    def get_project(self, project_id: str) -> ProjectBasicInfo | None: ...

    def get_managed_project_ids(self, manager_id: str) -> list[str]: ...

    def is_user_project_member(self, project_id: str, user_id: str) -> bool: ...

    def list_managed_projects(self, user_id: str, role: str) -> list[ProjectBasicInfo]: ...


class NotificationSender(Protocol):
    """Cross-cutting notification dispatch (orchestrated, BR-4)."""

    def notify_meeting_scheduled(self, meeting: Meeting, participant_ids: list[str]) -> None: ...

    def notify_meeting_cancelled(self, meeting: Meeting, participant_ids: list[str]) -> None: ...


class UserLookup(Protocol):
    """Cross-cutting user details lookup (orchestrated, BR-4)."""

    def get_users_info(self, user_ids: list[str]) -> dict[str, UserBasicInfo]: ...
