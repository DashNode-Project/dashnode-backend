"""Application use cases for Availability and Meetings."""

from datetime import timedelta
from urllib.parse import urlparse

from app.modules.availability.application.dtos import (
    CreateMeetingCommand,
    DayAvailableSlotsDTO,
    MeetingDTO,
    MessageResponse,
    ParticipantDTO,
    SaveAvailabilityCommand,
    SearchMeetingSlotsCommand,
    SearchMeetingSlotsResponse,
    TeamAvailabilityResponse,
    TeamUserAvailabilityDTO,
    TimeSlotDTO,
    UserAvailabilityResponse,
)
from app.modules.availability.domain import messages
from app.modules.availability.domain.entities import (
    VALID_MEETING_TYPES,
    Meeting,
    TimeSlot,
    UserAvailability,
)
from app.modules.availability.domain.ports import (
    AvailabilityRepository,
    NotificationSender,
    ProjectLookup,
    TeamMembersLookup,
    UserLookup,
)
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


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _build_meeting_dto(
    meeting: Meeting,
    repo: AvailabilityRepository,
    project_lookup: ProjectLookup | None,
    user_lookup: UserLookup | None,
    clock: Clock | None = None,
) -> MeetingDTO:
    project_name: str | None = None
    if meeting.project_id and project_lookup:
        p = project_lookup.get_project(meeting.project_id)
        if p:
            project_name = p.name

    creator_name: str | None = None
    all_needed_uids = list({meeting.creator_id, *meeting.participant_ids})
    user_infos = user_lookup.get_users_info(all_needed_uids) if user_lookup else {}
    if meeting.creator_id in user_infos:
        creator_name = user_infos[meeting.creator_id].name

    responses = repo.get_participant_responses(meeting.id)
    participants_dto = [
        ParticipantDTO(
            user_id=uid,
            name=user_infos[uid].name if uid in user_infos else uid,
            email=user_infos[uid].email if uid in user_infos else "",
            role=user_infos[uid].role if uid in user_infos else "",
            response=responses.get(uid, "pendiente"),
        )
        for uid in meeting.participant_ids
    ]

    effective_status = meeting.status
    if clock is not None and meeting.status == "scheduled":
        now_dt = clock.now()
        now_date = now_dt.strftime("%Y-%m-%d")
        now_time = now_dt.strftime("%H:%M")
        if meeting.date < now_date or (meeting.date == now_date and meeting.end_time <= now_time):
            effective_status = "completed"

    return MeetingDTO(
        id=meeting.id,
        project_id=meeting.project_id,
        project_name=project_name,
        title=meeting.title,
        type=meeting.type,
        description=meeting.description,
        date=meeting.date,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        duration=meeting.duration,
        link=meeting.link,
        status=effective_status,
        creator_id=meeting.creator_id,
        creator_name=creator_name,
        participant_ids=meeting.participant_ids,
        participants=participants_dto,
        summary=meeting.summary,
        minutes_url=meeting.minutes_url,
    )


class CreateMeetingUseCase:
    """Creates and schedules a meeting for participants."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        project_lookup: ProjectLookup | None = None,
        notification_sender: NotificationSender | None = None,
        user_lookup: UserLookup | None = None,
    ) -> None:
        self._repo = repo
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._project_lookup = project_lookup
        self._notification_sender = notification_sender
        self._user_lookup = user_lookup

    def execute(self, actor: CurrentUser, cmd: CreateMeetingCommand) -> MeetingDTO:
        if actor.role not in ("admin", "manager"):
            raise AccessDeniedError()

        # Title validation: obligatorio, max 100 caracteres
        if not cmd.title or not cmd.title.strip():
            raise AppError("TITLE_REQUIRED", messages.MEETING_TITLE_REQUIRED, ErrorKind.VALIDATION)
        if len(cmd.title.strip()) > 100:
            raise AppError(
                "TITLE_TOO_LONG",
                "El título no puede superar los 100 caracteres.",
                ErrorKind.VALIDATION,
            )

        # Type validation: obligatorio entre Daily, Planning, Review, Retro y General
        m_type = cmd.type.strip() if cmd.type else ""
        if self._project_lookup is not None:
            if not m_type or m_type not in VALID_MEETING_TYPES:
                raise AppError(
                    "TYPE_REQUIRED", messages.MEETING_TYPE_REQUIRED, ErrorKind.VALIDATION
                )
        else:
            if not m_type:
                m_type = "General"
            elif m_type not in VALID_MEETING_TYPES:
                raise AppError(
                    "TYPE_REQUIRED", messages.MEETING_TYPE_REQUIRED, ErrorKind.VALIDATION
                )

        # Project validation: obligatorio si project_lookup está configurado
        if self._project_lookup is not None:
            if not cmd.project_id or not cmd.project_id.strip():
                raise AppError("PROJECT_REQUIRED", messages.PROJECT_REQUIRED, ErrorKind.VALIDATION)
            proj = self._project_lookup.get_project(cmd.project_id)
            if proj is None:
                raise AppError("PROJECT_REQUIRED", messages.PROJECT_REQUIRED, ErrorKind.VALIDATION)

            # Si es gerente, debe gestionar el proyecto
            if actor.role == "manager" and proj.manager_id != actor.id:
                raise AccessDeniedError()

            # Todos los participantes deben ser miembros del proyecto seleccionado
            for pid in cmd.participant_ids:
                if pid not in proj.member_ids and pid != proj.manager_id:
                    raise AppError(
                        "PARTICIPANTS_NOT_MEMBERS",
                        messages.PARTICIPANTS_MUST_BE_PROJECT_MEMBERS,
                        ErrorKind.VALIDATION,
                    )

        # Link validation: opcional, pero si existe debe ser URL válida
        if cmd.link and cmd.link.strip() and not _is_valid_url(cmd.link.strip()):
            raise AppError("INVALID_LINK", messages.INVALID_MEETING_LINK, ErrorKind.VALIDATION)

        # Concurrency check: rechazo si algún participante ya tiene reunión en ese horario
        has_conflict = self._repo.check_concurrent_meeting(
            participant_ids=cmd.participant_ids,
            date=cmd.date,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
        )
        if has_conflict:
            raise AppError(
                "PARTICIPANT_MEETING_CONFLICT",
                messages.PARTICIPANT_MEETING_CONFLICT,
                ErrorKind.CONFLICT,
            )

        now = self._clock.now()
        meeting_id = self._id_gen.generate()

        meeting = Meeting(
            id=meeting_id,
            project_id=cmd.project_id,
            title=cmd.title.strip(),
            type=m_type,
            description=cmd.description,
            date=cmd.date,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
            duration=cmd.duration,
            link=cmd.link.strip() if cmd.link else None,
            status="scheduled",
            creator_id=actor.id,
            participant_ids=cmd.participant_ids,
            created_at=now,
            updated_at=now,
        )

        with self._uow:
            self._repo.save_meeting(meeting)
            if self._notification_sender is not None:
                self._notification_sender.notify_meeting_scheduled(meeting, cmd.participant_ids)
            self._uow.commit()

        return _build_meeting_dto(meeting, self._repo, self._project_lookup, self._user_lookup)


class ListMeetingsUseCase:
    """Lists meetings scoped by user role (admin, manager, developer)."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        clock: Clock,
        project_lookup: ProjectLookup | None = None,
        user_lookup: UserLookup | None = None,
    ) -> None:
        self._repo = repo
        self._clock = clock
        self._project_lookup = project_lookup
        self._user_lookup = user_lookup

    def execute(
        self,
        actor: CurrentUser,
        date_from: str | None = None,
        date_to: str | None = None,
        filter_type: str | None = None,
    ) -> list[MeetingDTO]:
        if actor.role == "admin":
            meetings = self._repo.list_all_meetings()
        elif actor.role == "manager":
            managed_pids = (
                self._project_lookup.get_managed_project_ids(actor.id)
                if self._project_lookup
                else []
            )
            created_meetings = self._repo.get_meetings_by_creator(actor.id)
            project_meetings = self._repo.get_meetings_by_projects(managed_pids)
            participating_meetings = self._repo.get_meetings_for_participants(
                [actor.id], "1970-01-01", "2099-12-31"
            )
            by_id = {
                m.id: m
                for m in (
                    *created_meetings,
                    *project_meetings,
                    *participating_meetings,
                )
            }
            meetings = list(by_id.values())
        else:
            # developer: only meetings where they participate
            meetings = self._repo.get_meetings_for_participants(
                [actor.id], "1970-01-01", "2099-12-31"
            )

        if date_from:
            meetings = [m for m in meetings if m.date >= date_from]
        if date_to:
            meetings = [m for m in meetings if m.date <= date_to]

        now_dt = self._clock.now()
        now_date = now_dt.strftime("%Y-%m-%d")
        now_time = now_dt.strftime("%H:%M")

        if filter_type in ("proximas", "upcoming"):
            meetings = [
                m
                for m in meetings
                if m.status != "cancelled"
                and (m.date > now_date or (m.date == now_date and m.start_time >= now_time))
            ]
            meetings.sort(key=lambda m: (m.date, m.start_time))
        elif filter_type in ("pasadas", "past"):
            meetings = [
                m
                for m in meetings
                if m.status == "completed"
                or (m.date < now_date or (m.date == now_date and m.start_time < now_time))
                or m.status == "cancelled"
            ]
            meetings.sort(key=lambda m: (m.date, m.start_time), reverse=True)
        else:
            meetings.sort(key=lambda m: (m.date, m.start_time))

        return [
            _build_meeting_dto(m, self._repo, self._project_lookup, self._user_lookup, self._clock)
            for m in meetings
        ]


class GetMeetingDetailUseCase:
    """Gets meeting details with role-based access control."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        project_lookup: ProjectLookup | None = None,
        user_lookup: UserLookup | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._repo = repo
        self._project_lookup = project_lookup
        self._user_lookup = user_lookup
        self._clock = clock

    def execute(self, actor: CurrentUser, meeting_id: str) -> MeetingDTO:
        meeting = self._repo.get_meeting_by_id(meeting_id)
        if meeting is None:
            raise AppError("MEETING_NOT_FOUND", messages.MEETING_NOT_FOUND, ErrorKind.NOT_FOUND)

        if actor.role == "admin":
            pass
        elif actor.role == "manager":
            managed_pids = (
                self._project_lookup.get_managed_project_ids(actor.id)
                if self._project_lookup
                else []
            )
            is_creator = meeting.creator_id == actor.id
            is_manager_of_project = meeting.project_id in managed_pids
            is_participant = actor.id in meeting.participant_ids
            if not (is_creator or is_manager_of_project or is_participant):
                raise AccessDeniedError()
        else:
            # developer
            if actor.id not in meeting.participant_ids:
                raise AccessDeniedError()

        return _build_meeting_dto(
            meeting, self._repo, self._project_lookup, self._user_lookup, self._clock
        )


class CancelMeetingUseCase:
    """Cancels a scheduled meeting. Only creator can cancel (RN-AGE-05)."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        clock: Clock,
        uow: UnitOfWork,
        project_lookup: ProjectLookup | None = None,
        user_lookup: UserLookup | None = None,
        notification_sender: NotificationSender | None = None,
    ) -> None:
        self._repo = repo
        self._clock = clock
        self._uow = uow
        self._project_lookup = project_lookup
        self._user_lookup = user_lookup
        self._notification_sender = notification_sender

    def execute(self, actor: CurrentUser, meeting_id: str) -> MeetingDTO:
        meeting = self._repo.get_meeting_by_id(meeting_id)
        if meeting is None:
            raise AppError("MEETING_NOT_FOUND", messages.MEETING_NOT_FOUND, ErrorKind.NOT_FOUND)

        # RN-AGE-05: Solo el creador de la reunión puede cancelarla, sin importar su rol
        if meeting.creator_id != actor.id:
            raise AppError(
                "ONLY_CREATOR_CAN_CANCEL",
                messages.ONLY_CREATOR_CAN_CANCEL,
                ErrorKind.FORBIDDEN,
            )

        meeting.status = "cancelled"
        meeting.updated_at = self._clock.now()

        with self._uow:
            self._repo.update_meeting(meeting)
            if self._notification_sender is not None:
                self._notification_sender.notify_meeting_cancelled(meeting, meeting.participant_ids)
            self._uow.commit()

        return _build_meeting_dto(
            meeting, self._repo, self._project_lookup, self._user_lookup, self._clock
        )


class RespondMeetingUseCase:
    """Records participant response (aceptada / rechazada)."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        uow: UnitOfWork,
        clock: Clock | None = None,
        project_lookup: ProjectLookup | None = None,
        user_lookup: UserLookup | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._clock = clock
        self._project_lookup = project_lookup
        self._user_lookup = user_lookup

    def execute(self, actor: CurrentUser, meeting_id: str, response: str) -> MeetingDTO:
        meeting = self._repo.get_meeting_by_id(meeting_id)
        if meeting is None:
            raise AppError("MEETING_NOT_FOUND", messages.MEETING_NOT_FOUND, ErrorKind.NOT_FOUND)

        if actor.id not in meeting.participant_ids:
            raise AccessDeniedError()

        # Restricción: no se puede responder una reunión cancelada ni ya realizada
        if meeting.status == "cancelled":
            raise AppError(
                "MEETING_CANCELLED",
                messages.MEETING_CANCELLED_CANNOT_RESPOND,
                ErrorKind.VALIDATION,
            )

        if self._clock is not None:
            now_dt = self._clock.now()
            now_date = now_dt.strftime("%Y-%m-%d")
            now_time = now_dt.strftime("%H:%M")
            is_past = meeting.status == "completed" or (
                meeting.date < now_date
                or (meeting.date == now_date and meeting.end_time <= now_time)
            )
            if is_past:
                raise AppError(
                    "MEETING_ALREADY_PAST",
                    messages.MEETING_ALREADY_PAST,
                    ErrorKind.VALIDATION,
                )

        normalized_resp = response.lower().strip()
        if normalized_resp not in ("aceptada", "rechazada"):
            raise AppError("INVALID_RESPONSE", "Respuesta no válida.", ErrorKind.VALIDATION)

        with self._uow:
            self._repo.update_participant_response(meeting_id, actor.id, normalized_resp)
            self._uow.commit()

        return _build_meeting_dto(
            meeting, self._repo, self._project_lookup, self._user_lookup, self._clock
        )


class UpdateMeetingSummaryUseCase:
    """Registers or updates meeting summary and minutes URL for completed meetings."""

    def __init__(
        self,
        repo: AvailabilityRepository,
        clock: Clock,
        uow: UnitOfWork,
        project_lookup: ProjectLookup | None = None,
        user_lookup: UserLookup | None = None,
    ) -> None:
        self._repo = repo
        self._clock = clock
        self._uow = uow
        self._project_lookup = project_lookup
        self._user_lookup = user_lookup

    def execute(
        self,
        actor: CurrentUser,
        meeting_id: str,
        summary: str | None,
        minutes_url: str | None,
    ) -> MeetingDTO:
        meeting = self._repo.get_meeting_by_id(meeting_id)
        if meeting is None:
            raise AppError("MEETING_NOT_FOUND", messages.MEETING_NOT_FOUND, ErrorKind.NOT_FOUND)

        if actor.role == "admin":
            pass
        elif actor.role == "manager":
            managed_pids = (
                self._project_lookup.get_managed_project_ids(actor.id)
                if self._project_lookup
                else []
            )
            if meeting.creator_id != actor.id and meeting.project_id not in managed_pids:
                raise AccessDeniedError()
        else:
            raise AccessDeniedError()

        # Restricción: solo aplica a reuniones realizadas
        now_dt = self._clock.now()
        now_date = now_dt.strftime("%Y-%m-%d")
        now_time = now_dt.strftime("%H:%M")
        is_past = meeting.status == "completed" or (
            meeting.status != "cancelled"
            and (
                meeting.date < now_date
                or (meeting.date == now_date and meeting.end_time <= now_time)
            )
        )
        if not is_past:
            raise AppError(
                "MEETING_NOT_COMPLETED",
                messages.MEETING_NOT_COMPLETED,
                ErrorKind.VALIDATION,
            )

        if not summary or not summary.strip():
            raise AppError("SUMMARY_REQUIRED", messages.SUMMARY_REQUIRED, ErrorKind.VALIDATION)

        if len(summary.strip()) > 2000:
            raise AppError("SUMMARY_TOO_LONG", messages.SUMMARY_TOO_LONG, ErrorKind.VALIDATION)

        if minutes_url and minutes_url.strip() and not _is_valid_url(minutes_url.strip()):
            raise AppError(
                "INVALID_MINUTES_URL",
                messages.INVALID_MINUTES_URL,
                ErrorKind.VALIDATION,
            )

        meeting.summary = summary.strip()
        meeting.minutes_url = minutes_url.strip() if minutes_url else None
        meeting.status = "completed"
        meeting.updated_at = self._clock.now()

        with self._uow:
            self._repo.update_meeting(meeting)
            self._uow.commit()

        return _build_meeting_dto(
            meeting, self._repo, self._project_lookup, self._user_lookup, self._clock
        )
