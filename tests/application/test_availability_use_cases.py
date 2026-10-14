"""Application tests for availability and meetings use cases."""

from datetime import UTC, datetime

import pytest

from app.modules.availability.application.dtos import (
    CreateMeetingCommand,
    SaveAvailabilityCommand,
    SearchMeetingSlotsCommand,
    TimeSlotDTO,
)
from app.modules.availability.application.use_cases import (
    CreateMeetingUseCase,
    GetTeamAvailabilityUseCase,
    GetUserAvailabilityUseCase,
    SaveUserAvailabilityUseCase,
    SearchMeetingSlotsUseCase,
)
from app.modules.availability.domain import messages
from app.modules.availability.domain.entities import Meeting, TimeSlot, UserAvailability
from app.modules.availability.domain.ports import TeamMembersLookup, UserBasicInfo
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError


class FakeClock(Clock):
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeIdGenerator(IdGenerator):
    def __init__(self, ids: list[str] | None = None) -> None:
        self._ids = ids or [f"id-{i}" for i in range(100)]
        self._idx = 0

    def generate(self) -> str:
        val = self._ids[self._idx]
        self._idx += 1
        return val


class FakeUnitOfWork(UnitOfWork):
    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class FakeAvailabilityRepository:
    def __init__(self) -> None:
        self.availabilities: dict[tuple[str, str], UserAvailability] = {}
        self.meetings: list[Meeting] = []

    def get_user_availability(self, user_id: str, week_start_date: str) -> UserAvailability | None:
        return self.availabilities.get((user_id, week_start_date))

    def get_latest_availability(
        self, user_id: str, before_or_on_week: str
    ) -> UserAvailability | None:
        matches = [
            a
            for (uid, w), a in self.availabilities.items()
            if uid == user_id and w <= before_or_on_week
        ]
        if not matches:
            return None
        matches.sort(key=lambda x: x.week_start_date, reverse=True)
        return matches[0]

    def save_user_availability(self, availability: UserAvailability) -> None:
        self.availabilities[(availability.user_id, availability.week_start_date)] = availability

    def list_availabilities_for_users(
        self, user_ids: list[str], week_start_date: str
    ) -> dict[str, UserAvailability]:
        return {
            uid: a
            for (uid, w), a in self.availabilities.items()
            if uid in user_ids and w == week_start_date
        }

    def get_meetings_for_participants(
        self, user_ids: list[str], start_date: str, end_date: str
    ) -> list[Meeting]:
        return [
            m
            for m in self.meetings
            if m.date >= start_date
            and m.date <= end_date
            and any(p in user_ids for p in m.participant_ids)
            and m.status != "cancelled"
        ]

    def save_meeting(self, meeting: Meeting) -> None:
        self.meetings.append(meeting)

    def get_meeting_by_id(self, meeting_id: str) -> Meeting | None:
        for m in self.meetings:
            if m.id == meeting_id:
                return m
        return None

    def list_all_meetings(self) -> list[Meeting]:
        return list(self.meetings)

    def get_meetings_by_projects(self, project_ids: list[str]) -> list[Meeting]:
        return [m for m in self.meetings if m.project_id in project_ids]

    def get_meetings_by_creator(self, creator_id: str) -> list[Meeting]:
        return [m for m in self.meetings if m.creator_id == creator_id]

    def update_meeting(self, meeting: Meeting) -> None:
        for idx, m in enumerate(self.meetings):
            if m.id == meeting.id:
                self.meetings[idx] = meeting
                return

    def cancel_scheduled_meetings_for_project(self, project_id: str, when: object) -> None:
        from dataclasses import replace
        from datetime import datetime

        assert isinstance(when, datetime)
        for idx, meeting in enumerate(self.meetings):
            if meeting.project_id == project_id and meeting.status == "scheduled":
                self.meetings[idx] = replace(meeting, status="cancelled", updated_at=when)

    def get_participant_responses(self, meeting_id: str) -> dict[str, str]:
        return {}

    def update_participant_response(self, meeting_id: str, user_id: str, response: str) -> None:
        pass

    def check_concurrent_meeting(
        self,
        participant_ids: list[str],
        date: str,
        start_time: str,
        end_time: str,
        exclude_meeting_id: str | None = None,
    ) -> bool:
        for m in self.meetings:
            if exclude_meeting_id and m.id == exclude_meeting_id:
                continue
            if m.date != date or m.status == "cancelled":
                continue
            if (
                any(pid in m.participant_ids for pid in participant_ids)
                and m.start_time < end_time
                and m.end_time > start_time
            ):
                return True
        return False


class FakeTeamMembersLookup(TeamMembersLookup):
    def __init__(self, visible: list[UserBasicInfo]) -> None:
        self._visible = visible

    def get_visible_users(self, actor_id: str, role: str) -> list[UserBasicInfo]:
        return self._visible

    def list_all_active_users(self) -> list[UserBasicInfo]:
        return self._visible


NOW = datetime(2026, 10, 12, 10, 0, 0, tzinfo=UTC)


def make_actor(id: str, email: str, role: str) -> CurrentUser:
    return CurrentUser(
        id=id,
        email=email,
        name="Test User",
        role=role,
        is_active=True,
        created_at=NOW,
    )


def test_save_user_availability_success_and_no_changes() -> None:
    repo = FakeAvailabilityRepository()
    clock = FakeClock(NOW)
    id_gen = FakeIdGenerator(["avail-1", "avail-2"])
    uow = FakeUnitOfWork()
    use_case = SaveUserAvailabilityUseCase(repo=repo, id_gen=id_gen, clock=clock, uow=uow)

    actor = make_actor(id="user-1", email="dev@dashnode.local", role="developer")
    cmd = SaveAvailabilityCommand(
        week_start_date="2026-10-12",
        slots={
            "monday": [
                TimeSlotDTO(start="09:00", end="10:00"),
                TimeSlotDTO(start="10:00", end="11:00"),
            ],
            "tuesday": [TimeSlotDTO(start="14:00", end="16:00")],
        },
    )

    res = use_case.execute(actor, cmd)
    assert res.message == messages.AVAILABILITY_SAVED

    # Merged contiguous blocks
    saved = repo.get_user_availability("user-1", "2026-10-12")
    assert saved is not None
    assert len(saved.slots["monday"]) == 1
    assert saved.slots["monday"][0].start == "09:00"
    assert saved.slots["monday"][0].end == "11:00"

    # Saving again with same slots -> NO_CHANGES_TO_SAVE
    with pytest.raises(AppError) as exc_info:
        use_case.execute(actor, cmd)
    assert exc_info.value.code == "NO_CHANGES_TO_SAVE"
    assert exc_info.value.message == messages.NO_CHANGES_TO_SAVE


def test_get_user_availability_inheritance() -> None:
    repo = FakeAvailabilityRepository()
    use_case = GetUserAvailabilityUseCase(repo=repo)

    # Initially empty
    empty_res = use_case.execute("user-1", "2026-10-12")
    assert empty_res.is_inherited is False
    assert empty_res.slots["monday"] == []

    # Save week 2026-10-12
    repo.save_user_availability(
        UserAvailability(
            id="a-1",
            user_id="user-1",
            week_start_date="2026-10-12",
            slots={"monday": [TimeSlot(start="09:00", end="12:00")]},
            created_at=NOW,
            updated_at=NOW,
        )
    )

    # Query week 2026-10-12 -> direct, not inherited
    direct_res = use_case.execute("user-1", "2026-10-12")
    assert direct_res.is_inherited is False
    assert len(direct_res.slots["monday"]) == 1

    # Query future week 2026-10-19 without record -> inherited from 2026-10-12
    inherited_res = use_case.execute("user-1", "2026-10-19")
    assert inherited_res.is_inherited is True
    assert len(inherited_res.slots["monday"]) == 1
    assert inherited_res.slots["monday"][0].start == "09:00"
    assert inherited_res.slots["monday"][0].end == "12:00"


def test_get_team_availability_permissions() -> None:
    repo = FakeAvailabilityRepository()
    lookup = FakeTeamMembersLookup(
        [UserBasicInfo(id="u1", name="Alice", email="alice@test.com", role="developer")]
    )
    use_case = GetTeamAvailabilityUseCase(repo=repo, team_lookup=lookup)

    dev = make_actor(id="dev1", email="dev@test.com", role="developer")
    with pytest.raises(AccessDeniedError):
        use_case.execute(dev, "2026-10-12")

    mgr = make_actor(id="mgr1", email="mgr@test.com", role="manager")
    team_res = use_case.execute(mgr, "2026-10-12")
    assert len(team_res.users) == 1
    assert team_res.users[0].name == "Alice"


def test_search_meeting_slots_and_create_meeting() -> None:
    repo = FakeAvailabilityRepository()
    clock = FakeClock(NOW)
    uow = FakeUnitOfWork()
    id_gen = FakeIdGenerator(["m-1"])

    search_case = SearchMeetingSlotsUseCase(repo=repo, clock=clock)
    create_case = CreateMeetingUseCase(repo=repo, id_gen=id_gen, clock=clock, uow=uow)

    mgr = make_actor(id="mgr1", email="mgr@test.com", role="manager")
    dev = make_actor(id="dev1", email="dev@test.com", role="developer")

    # Developer cannot search
    with pytest.raises(AccessDeniedError):
        search_case.execute(
            dev,
            SearchMeetingSlotsCommand(
                interval_start="09:00",
                interval_end="12:00",
                days=["monday"],
                participant_ids=["u1"],
                duration_hours=1,
            ),
        )

    # Set availability for u1 and u2 on Monday
    repo.save_user_availability(
        UserAvailability(
            id="a-1",
            user_id="u1",
            week_start_date="2026-10-12",
            slots={"monday": [TimeSlot(start="09:00", end="12:00")]},
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo.save_user_availability(
        UserAvailability(
            id="a-2",
            user_id="u2",
            week_start_date="2026-10-12",
            slots={"monday": [TimeSlot(start="10:00", end="13:00")]},
            created_at=NOW,
            updated_at=NOW,
        )
    )

    # Search with duration 1h in [08:00, 18:00] for monday ->
    # common intersection is 10:00-11:00 and 11:00-12:00
    search_cmd = SearchMeetingSlotsCommand(
        interval_start="08:00",
        interval_end="18:00",
        days=["monday"],
        participant_ids=["u1", "u2"],
        duration_hours=1,
        week_start_date="2026-10-12",
    )
    res = search_case.execute(mgr, search_cmd)
    monday_res = next(r for r in res.results if r.day == "monday")
    slot_starts = [s.start for s in monday_res.slots]
    assert "10:00" in slot_starts
    assert "11:00" in slot_starts
    assert "09:00" not in slot_starts  # u2 not available at 09:00

    # If meeting is scheduled at 10:00-11:00 for u1, that slot should be excluded
    m_cmd = CreateMeetingCommand(
        project_id=None,
        title="Sync",
        date="2026-10-12",
        start_time="10:00",
        end_time="11:00",
        duration=60,
        participant_ids=["u1"],
    )
    created = create_case.execute(mgr, m_cmd)
    assert created.id == "m-1"

    # Re-search -> 10:00 is now excluded because of scheduled meeting!
    res_after = search_case.execute(mgr, search_cmd)
    monday_res_after = next(r for r in res_after.results if r.day == "monday")
    slot_starts_after = [s.start for s in monday_res_after.slots]
    assert "10:00" not in slot_starts_after
    assert "11:00" in slot_starts_after


def test_search_meeting_slots_no_slots_found() -> None:
    repo = FakeAvailabilityRepository()
    clock = FakeClock(NOW)
    search_case = SearchMeetingSlotsUseCase(repo=repo, clock=clock)
    mgr = make_actor(id="mgr1", email="mgr@test.com", role="manager")

    search_cmd = SearchMeetingSlotsCommand(
        interval_start="09:00",
        interval_end="12:00",
        days=["friday"],
        participant_ids=["nonexistent"],
        duration_hours=1,
        week_start_date="2026-10-12",
    )
    with pytest.raises(AppError) as exc_info:
        search_case.execute(mgr, search_cmd)
    assert exc_info.value.code == "NO_AVAILABLE_SLOTS"
    assert exc_info.value.message == messages.NO_AVAILABLE_SLOTS
