"""Availability and Meetings HTTP routes (EP-04 and EP-05)."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.modules.availability.application.dtos import (
    CreateMeetingCommand,
    MeetingDTO,
    MessageResponse,
    SaveAvailabilityCommand,
    SearchMeetingSlotsCommand,
    SearchMeetingSlotsResponse,
    TeamAvailabilityResponse,
    UserAvailabilityResponse,
)
from app.modules.availability.application.use_cases import (
    CreateMeetingUseCase,
    GetTeamAvailabilityUseCase,
    GetUserAvailabilityUseCase,
    SaveUserAvailabilityUseCase,
    SearchMeetingSlotsUseCase,
)
from app.modules.availability.infrastructure.repositories import SqlAlchemyAvailabilityRepository
from app.orchestration.security import get_current_user, require_admin_or_manager
from app.orchestration.team_members_lookup import SqlAlchemyTeamMembersLookup
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(prefix="/availability", tags=["availability"])
_clock = SystemClock()
_id_gen = UuidGenerator()


def _get_current_week_monday() -> str:
    today = _clock.now().date()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


@router.get(
    "/mine",
    response_model=UserAvailabilityResponse,
    summary="Obtener disponibilidad semanal del usuario actual",
)
def get_my_availability(
    week: str | None = Query(default=None, description="Fecha de lunes (YYYY-MM-DD)"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UserAvailabilityResponse:
    target_week = week or _get_current_week_monday()
    repo = SqlAlchemyAvailabilityRepository(session=db)
    use_case = GetUserAvailabilityUseCase(repo=repo)
    return use_case.execute(user_id=current_user.id, week_start_date=target_week)


@router.post(
    "/mine",
    response_model=MessageResponse,
    summary="Guardar disponibilidad semanal en bloques de 1 hora",
)
def save_my_availability(
    cmd: SaveAvailabilityCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    use_case = SaveUserAvailabilityUseCase(repo=repo, id_gen=_id_gen, clock=_clock, uow=uow)
    return use_case.execute(actor=current_user, cmd=cmd)


@router.get(
    "/team",
    response_model=TeamAvailabilityResponse,
    summary="Obtener rejilla semanal de disponibilidad del equipo",
)
def get_team_availability(
    week: str | None = Query(default=None, description="Fecha de lunes (YYYY-MM-DD)"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TeamAvailabilityResponse:
    target_week = week or _get_current_week_monday()
    repo = SqlAlchemyAvailabilityRepository(session=db)
    team_lookup = SqlAlchemyTeamMembersLookup(session=db)
    use_case = GetTeamAvailabilityUseCase(repo=repo, team_lookup=team_lookup)
    return use_case.execute(actor=current_user, week_start_date=target_week)


@router.post(
    "/search-slots",
    response_model=SearchMeetingSlotsResponse,
    summary="Calcular horarios disponibles para reunión según criterios",
)
def search_meeting_slots(
    cmd: SearchMeetingSlotsCommand,
    current_user: CurrentUser = Depends(require_admin_or_manager),
    db: Session = Depends(get_db_session),
) -> SearchMeetingSlotsResponse:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    use_case = SearchMeetingSlotsUseCase(repo=repo, clock=_clock)
    return use_case.execute(actor=current_user, cmd=cmd)


@router.post(
    "/meetings",
    response_model=MeetingDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Agendar una reunión",
)
def create_meeting(
    cmd: CreateMeetingCommand,
    current_user: CurrentUser = Depends(require_admin_or_manager),
    db: Session = Depends(get_db_session),
) -> MeetingDTO:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    use_case = CreateMeetingUseCase(repo=repo, id_gen=_id_gen, clock=_clock, uow=uow)
    return use_case.execute(actor=current_user, cmd=cmd)


@router.get(
    "/meetings",
    response_model=list[MeetingDTO],
    summary="Listar reuniones agendadas",
)
def list_meetings(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[MeetingDTO]:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    start_d = date_from or "1970-01-01"
    end_d = date_to or "2099-12-31"
    meetings = repo.get_meetings_for_participants(
        user_ids=[current_user.id], start_date=start_d, end_date=end_d
    )
    return [
        MeetingDTO(
            id=m.id,
            project_id=m.project_id,
            title=m.title,
            description=m.description,
            date=m.date,
            start_time=m.start_time,
            end_time=m.end_time,
            duration=m.duration,
            link=m.link,
            status=m.status,
            creator_id=m.creator_id,
            participant_ids=m.participant_ids,
        )
        for m in meetings
    ]
