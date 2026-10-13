"""Application use cases for Availability and Meetings."""

from datetime import timedelta

from app.modules.availability.application.dtos import (
    CreateMeetingCommand,
    DayAvailableSlotsDTO,
    MeetingDTO,
    MessageResponse,
    SaveAvailabilityCommand,
    SearchMeetingSlotsCommand,
    SearchMeetingSlotsResponse,
    TeamAvailabilityResponse,
    TeamUserAvailabilityDTO,
    TimeSlotDTO,
    UserAvailabilityResponse,
)
from app.modules.availability.domain import messages
from app.modules.availability.domain.entities import Meeting, TimeSlot, UserAvailability
from app.modules.availability.domain.ports import AvailabilityRepository, TeamMembersLookup
from app.modules.availability.domain.rules import (
    DAYS_OF_WEEK,
    are_slots_equal,
    get_dates_for_week,
    minutes_to_time,
    normalize_and_merge_slots,
    time_to_minutes,
    validate_search_criteria,
)
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


def _dto_slots_to_domain(
    slots_dto: dict[str, list[TimeSlotDTO]],
) -> dict[str, list[TimeSlot]]:
    result: dict[str, list[TimeSlot]] = {}
    for day in DAYS_OF_WEEK:
        raw_list = slots_dto.get(day, [])
        domain_list = [TimeSlot(start=s.start, end=s.end) for s in raw_list]
        result[day] = normalize_and_merge_slots(domain_list)
    return result


def _domain_slots_to_dto(
    slots_domain: dict[str, list[TimeSlot]],
) -> dict[str, list[TimeSlotDTO]]:
    result: dict[str, list[TimeSlotDTO]] = {}
    for day in DAYS_OF_WEEK:
        slot_list = slots_domain.get(day, [])
        result[day] = [TimeSlotDTO(start=s.start, end=s.end) for s in slot_list]
    return result


class SaveUserAvailabilityUseCase:
    """HU_DN_02_32: save 1-hour block availability per week, reject if no changes."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = repo
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(self, actor: CurrentUser, cmd: SaveAvailabilityCommand) -> MessageResponse:
        now = self._clock.now()
        normalized_incoming = _dto_slots_to_domain(cmd.slots)

        existing = self._repo.get_user_availability(actor.id, cmd.week_start_date)
        if existing is not None and are_slots_equal(existing.slots, normalized_incoming):
            raise AppError(
                "NO_CHANGES_TO_SAVE",
                messages.NO_CHANGES_TO_SAVE,
                ErrorKind.VALIDATION,
            )

        avail_id = existing.id if existing is not None else self._id_gen.generate()
        created_at = existing.created_at if existing is not None else now

        entity = UserAvailability(
            id=avail_id,
            user_id=actor.id,
            week_start_date=cmd.week_start_date,
            slots=normalized_incoming,
            created_at=created_at,
            updated_at=now,
        )

        with self._uow:
            self._repo.save_user_availability(entity)
            self._uow.commit()

        return MessageResponse(message=messages.AVAILABILITY_SAVED)


class GetUserAvailabilityUseCase:
    """HU_DN_02_33: get availability, inheriting from previous weeks if unset."""

    def __init__(self, repo: AvailabilityRepository) -> None:
        self._repo = repo

    def execute(self, user_id: str, week_start_date: str) -> UserAvailabilityResponse:
        existing = self._repo.get_user_availability(user_id, week_start_date)
        if existing is not None:
            return UserAvailabilityResponse(
                week_start_date=week_start_date,
                slots=_domain_slots_to_dto(existing.slots),
                is_inherited=False,
            )

        # HU_DN_02_33: reuse latest registered availability from previous weeks
        latest = self._repo.get_latest_availability(user_id, before_or_on_week=week_start_date)
        if latest is not None:
            return UserAvailabilityResponse(
                week_start_date=week_start_date,
                slots=_domain_slots_to_dto(latest.slots),
                is_inherited=True,
            )

        # Empty default
        empty_slots: dict[str, list[TimeSlotDTO]] = {day: [] for day in DAYS_OF_WEEK}
        return UserAvailabilityResponse(
            week_start_date=week_start_date,
            slots=empty_slots,
            is_inherited=False,
        )


class GetTeamAvailabilityUseCase:
    """HU_DN_02_34: team weekly availability grid for managers and admins."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        team_lookup: TeamMembersLookup,
    ) -> None:
        self._repo = repo
        self._team_lookup = team_lookup

    def execute(self, actor: CurrentUser, week_start_date: str) -> TeamAvailabilityResponse:
        # Developer is strictly forbidden
        if actor.role not in ("admin", "manager"):
            raise AccessDeniedError()

        visible_users = self._team_lookup.get_visible_users(actor.id, actor.role)
        user_rows: list[TeamUserAvailabilityDTO] = []

        for user_info in visible_users:
            avail = self._repo.get_user_availability(user_info.id, week_start_date)
            if avail is None:
                avail = self._repo.get_latest_availability(
                    user_info.id, before_or_on_week=week_start_date
                )
            slots_map = (
                _domain_slots_to_dto(avail.slots) if avail else {day: [] for day in DAYS_OF_WEEK}
            )
            user_rows.append(
                TeamUserAvailabilityDTO(
                    user_id=user_info.id,
                    name=user_info.name,
                    email=user_info.email,
                    role=user_info.role,
                    slots=slots_map,
                )
            )

        return TeamAvailabilityResponse(
            week_start_date=week_start_date,
            users=user_rows,
        )


class SearchMeetingSlotsUseCase:
    """HU_DN_03_35 & HU_DN_03_36: search common available meeting slots."""

    def __init__(self, repo: AvailabilityRepository, clock: Clock) -> None:
        self._repo = repo
        self._clock = clock

    def execute(
        self, actor: CurrentUser, cmd: SearchMeetingSlotsCommand
    ) -> SearchMeetingSlotsResponse:
        if actor.role not in ("admin", "manager"):
            raise AccessDeniedError()

        errors = validate_search_criteria(
            interval_start=cmd.interval_start,
            interval_end=cmd.interval_end,
            days=cmd.days,
            participant_ids=cmd.participant_ids,
            duration_hours=cmd.duration_hours,
        )
        if errors:
            raise AppError(
                "CRITERIA_INVALID",
                next(iter(errors.values())),
                ErrorKind.VALIDATION,
                errors,
            )

        # Resolve week start date (current Monday if None)
        if cmd.week_start_date:
            week_monday = cmd.week_start_date
        else:
            now_dt = self._clock.now()
            today = now_dt.date()
            monday = today - timedelta(days=today.weekday())
            week_monday = monday.isoformat()

        dates_by_day = get_dates_for_week(week_monday)
        min_date = min(dates_by_day.values())
        max_date = max(dates_by_day.values())

        # Load meetings for all participants
        existing_meetings = self._repo.get_meetings_for_participants(
            cmd.participant_ids, min_date, max_date
        )

        # Load availabilities for participants
        user_availabilities: dict[str, UserAvailability] = {}
        for uid in cmd.participant_ids:
            av = self._repo.get_user_availability(uid, week_monday)
            if av is None:
                av = self._repo.get_latest_availability(uid, before_or_on_week=week_monday)
            if av is not None:
                user_availabilities[uid] = av

        results: list[DayAvailableSlotsDTO] = []
        int_start_m = time_to_minutes(cmd.interval_start)
        int_end_m = time_to_minutes(cmd.interval_end)
        duration_m = cmd.duration_hours * 60

        total_slots_count = 0

        for day in DAYS_OF_WEEK:
            if day not in cmd.days:
                continue

            day_date = dates_by_day[day]
            meetings_on_day = [
                m
                for m in existing_meetings
                if m.date == day_date and any(p in cmd.participant_ids for p in m.participant_ids)
            ]

            day_slots: list[TimeSlotDTO] = []

            # Step in 60-minute increments
            cur_start_m = int_start_m
            while cur_start_m + duration_m <= int_end_m:
                cur_end_m = cur_start_m + duration_m

                # 1. Check if all participants have availability covering [cur_start_m, cur_end_m]
                all_available = True
                for uid in cmd.participant_ids:
                    u_av = user_availabilities.get(uid)
                    if not u_av:
                        all_available = False
                        break
                    u_slots = u_av.slots.get(day, [])
                    # Check if any slot of user covers this interval
                    covers = any(
                        time_to_minutes(s.start) <= cur_start_m
                        and time_to_minutes(s.end) >= cur_end_m
                        for s in u_slots
                    )
                    if not covers:
                        all_available = False
                        break

                # 2. Check if none of the participants has a conflicting meeting
                no_conflict = True
                if all_available:
                    for m in meetings_on_day:
                        m_start = time_to_minutes(m.start_time)
                        m_end = time_to_minutes(m.end_time)
                        if max(cur_start_m, m_start) < min(cur_end_m, m_end):
                            no_conflict = False
                            break

                if all_available and no_conflict:
                    day_slots.append(
                        TimeSlotDTO(
                            start=minutes_to_time(cur_start_m),
                            end=minutes_to_time(cur_end_m),
                        )
                    )

                cur_start_m += 60

            total_slots_count += len(day_slots)
            results.append(
                DayAvailableSlotsDTO(
                    day=day,
                    date=day_date,
                    slots=day_slots,
                )
            )

        if total_slots_count == 0:
            raise AppError(
                "NO_AVAILABLE_SLOTS",
                messages.NO_AVAILABLE_SLOTS,
                ErrorKind.VALIDATION,
            )

        return SearchMeetingSlotsResponse(results=results)


class CreateMeetingUseCase:
    """Creates and schedules a meeting for participants."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = repo
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(self, actor: CurrentUser, cmd: CreateMeetingCommand) -> MeetingDTO:
        if actor.role not in ("admin", "manager"):
            raise AccessDeniedError()

        now = self._clock.now()
        meeting_id = self._id_gen.generate()

        meeting = Meeting(
            id=meeting_id,
            project_id=cmd.project_id,
            title=cmd.title,
            description=cmd.description,
            date=cmd.date,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
            duration=cmd.duration,
            link=cmd.link,
            status="scheduled",
            creator_id=actor.id,
            participant_ids=cmd.participant_ids,
            created_at=now,
            updated_at=now,
        )

        with self._uow:
            self._repo.save_meeting(meeting)
            self._uow.commit()

        return MeetingDTO(
            id=meeting.id,
            project_id=meeting.project_id,
            title=meeting.title,
            description=meeting.description,
            date=meeting.date,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            duration=meeting.duration,
            link=meeting.link,
            status=meeting.status,
            creator_id=meeting.creator_id,
            participant_ids=meeting.participant_ids,
        )
