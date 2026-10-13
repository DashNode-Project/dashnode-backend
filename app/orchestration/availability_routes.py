"""Availability and Meetings HTTP routes (EP-04 and EP-05)."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.modules.availability.application.dtos import (
    CreateMeetingCommand,
    MeetingDTO,
    MessageResponse,
    ProjectManagedDTO,
    RespondMeetingCommand,
    SaveAvailabilityCommand,
    SearchMeetingSlotsCommand,
    SearchMeetingSlotsResponse,
    TeamAvailabilityResponse,
    UpdateMeetingSummaryCommand,
    UserAvailabilityResponse,
)
from app.modules.availability.application.use_cases import (
    CancelMeetingUseCase,
    CreateMeetingUseCase,
    GetMeetingDetailUseCase,
    GetTeamAvailabilityUseCase,
    GetUserAvailabilityUseCase,
    ListMeetingsUseCase,
    RespondMeetingUseCase,
    SaveUserAvailabilityUseCase,
    SearchMeetingSlotsUseCase,
    UpdateMeetingSummaryUseCase,
)
from app.modules.availability.infrastructure.repositories import SqlAlchemyAvailabilityRepository
from app.orchestration.meeting_adapters import (
    SqlAlchemyMeetingNotificationSender,
    SqlAlchemyProjectLookup,
    SqlAlchemyUserLookup,
)
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
    summary="Consultar disponibilidad semanal propia",
)
def get_my_availability(
    week: str | None = Query(default=None, description="Lunes de la semana (YYYY-MM-DD)"),
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
    status_code=status.HTTP_200_OK,
    summary="Guardar disponibilidad semanal propia",
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
    summary="Consultar disponibilidad del equipo",
)
def get_team_availability(
    week: str | None = Query(default=None, description="Lunes de la semana (YYYY-MM-DD)"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TeamAvailabilityResponse:
    target_week = week or _get_current_week_monday()
    repo = SqlAlchemyAvailabilityRepository(session=db)
    lookup = SqlAlchemyTeamMembersLookup(session=db)
    use_case = GetTeamAvailabilityUseCase(repo=repo, team_lookup=lookup)
    return use_case.execute(actor=current_user, week_start_date=target_week)


@router.post(
    "/search-slots",
    response_model=SearchMeetingSlotsResponse,
    summary="Buscar franjas disponibles para reunión",
)
def search_meeting_slots(
    cmd: SearchMeetingSlotsCommand,
    current_user: CurrentUser = Depends(require_admin_or_manager),
    db: Session = Depends(get_db_session),
) -> SearchMeetingSlotsResponse:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    use_case = SearchMeetingSlotsUseCase(repo=repo, clock=_clock)
    return use_case.execute(actor=current_user, cmd=cmd)


@router.get(
    "/projects",
    response_model=list[ProjectManagedDTO],
    summary="Listar proyectos gestionados por el usuario para agendamiento",
)
def list_managed_projects(
    current_user: CurrentUser = Depends(require_admin_or_manager),
    db: Session = Depends(get_db_session),
) -> list[ProjectManagedDTO]:
    lookup = SqlAlchemyProjectLookup(session=db)
    projects = lookup.list_managed_projects(user_id=current_user.id, role=current_user.role)
    return [
        ProjectManagedDTO(
            id=p.id,
            name=p.name,
            manager_id=p.manager_id,
            meeting_link=p.meeting_link,
            member_ids=list(dict.fromkeys(([p.manager_id] if p.manager_id else []) + p.member_ids)),
        )
        for p in projects
    ]


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
    project_lookup = SqlAlchemyProjectLookup(session=db)
    notif_sender = SqlAlchemyMeetingNotificationSender(session=db, id_gen=_id_gen, clock=_clock)
    user_lookup = SqlAlchemyUserLookup(session=db)
    use_case = CreateMeetingUseCase(
        repo=repo,
        id_gen=_id_gen,
        clock=_clock,
        uow=uow,
        project_lookup=project_lookup,
        notification_sender=notif_sender,
        user_lookup=user_lookup,
    )
    return use_case.execute(actor=current_user, cmd=cmd)


@router.get(
    "/meetings",
    response_model=list[MeetingDTO],
    summary="Listar reuniones según alcance de rol",
)
def list_meetings(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    filter_type: str | None = Query(
        default=None, description="Filtro opcional: 'proximas' o 'pasadas'"
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[MeetingDTO]:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    project_lookup = SqlAlchemyProjectLookup(session=db)
    user_lookup = SqlAlchemyUserLookup(session=db)
    use_case = ListMeetingsUseCase(
        repo=repo,
        clock=_clock,
        project_lookup=project_lookup,
        user_lookup=user_lookup,
    )
    return use_case.execute(
        actor=current_user,
        date_from=date_from,
        date_to=date_to,
        filter_type=filter_type,
    )


@router.get(
    "/meetings/{meeting_id}",
    response_model=MeetingDTO,
    summary="Consultar detalle de una reunión",
)
def get_meeting_detail(
    meeting_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MeetingDTO:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    project_lookup = SqlAlchemyProjectLookup(session=db)
    user_lookup = SqlAlchemyUserLookup(session=db)
    use_case = GetMeetingDetailUseCase(
        repo=repo,
        project_lookup=project_lookup,
        user_lookup=user_lookup,
        clock=_clock,
    )
    return use_case.execute(actor=current_user, meeting_id=meeting_id)


@router.post(
    "/meetings/{meeting_id}/cancel",
    response_model=MeetingDTO,
    summary="Cancelar una reunión",
)
def cancel_meeting(
    meeting_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MeetingDTO:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    project_lookup = SqlAlchemyProjectLookup(session=db)
    user_lookup = SqlAlchemyUserLookup(session=db)
    notif_sender = SqlAlchemyMeetingNotificationSender(session=db, id_gen=_id_gen, clock=_clock)
    use_case = CancelMeetingUseCase(
        repo=repo,
        clock=_clock,
        uow=uow,
        project_lookup=project_lookup,
        user_lookup=user_lookup,
        notification_sender=notif_sender,
    )
    return use_case.execute(actor=current_user, meeting_id=meeting_id)


@router.post(
    "/meetings/{meeting_id}/respond",
    response_model=MeetingDTO,
    summary="Responder a una reunión (aceptada o rechazada)",
)
def respond_meeting(
    meeting_id: str,
    cmd: RespondMeetingCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MeetingDTO:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    project_lookup = SqlAlchemyProjectLookup(session=db)
    user_lookup = SqlAlchemyUserLookup(session=db)
    use_case = RespondMeetingUseCase(
        repo=repo,
        uow=uow,
        clock=_clock,
        project_lookup=project_lookup,
        user_lookup=user_lookup,
    )
    return use_case.execute(actor=current_user, meeting_id=meeting_id, response=cmd.response)


@router.post(
    "/meetings/{meeting_id}/summary",
    response_model=MeetingDTO,
    summary="Registrar resumen y acta de reunión",
)
def update_meeting_summary(
    meeting_id: str,
    cmd: UpdateMeetingSummaryCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MeetingDTO:
    repo = SqlAlchemyAvailabilityRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    project_lookup = SqlAlchemyProjectLookup(session=db)
    user_lookup = SqlAlchemyUserLookup(session=db)
    use_case = UpdateMeetingSummaryUseCase(
        repo=repo,
        clock=_clock,
        uow=uow,
        project_lookup=project_lookup,
        user_lookup=user_lookup,
    )
    return use_case.execute(
        actor=current_user,
        meeting_id=meeting_id,
        summary=cmd.summary,
        minutes_url=cmd.minutes_url,
    )
