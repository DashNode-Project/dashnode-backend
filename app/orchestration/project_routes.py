"""Project HTTP routes (EP-03). Wiring lives here to satisfy BR-4 module isolation."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.projects.application.dtos import (
    AddMemberCommand,
    AssignProjectManagerCommand,
    CreateProjectCommand,
    MessageResponse,
    ProjectDTO,
    ProjectHealthDTO,
    ProjectMemberDTO,
    UpdateProjectCommand,
    UpdateProjectStatusCommand,
)
from app.modules.projects.application.use_cases import (
    AddProjectMemberUseCase,
    AssignProjectManagerUseCase,
    CreateProjectUseCase,
    DeleteProjectUseCase,
    GetProjectHealthUseCase,
    GetProjectUseCase,
    ListProjectMembersUseCase,
    ListProjectsUseCase,
    RemoveProjectMemberUseCase,
    UpdateProjectStatusUseCase,
    UpdateProjectUseCase,
)
from app.modules.projects.domain.ports import ManagerLookup
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.orchestration.project_manager_lookup import SqlAlchemyManagerLookup
from app.orchestration.projects_container import (
    get_add_project_member_use_case,
    get_delete_project_use_case,
    get_list_project_members_use_case,
    get_list_projects_use_case,
    get_project_health_use_case,
    get_project_use_case,
    get_remove_project_member_use_case,
    get_update_project_status_use_case,
    get_update_project_use_case,
)
from app.orchestration.security import get_current_user, require_admin, require_admin_or_manager
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(prefix="/projects", tags=["projects"])
_clock = SystemClock()
_id_gen = UuidGenerator()


def get_manager_lookup(db: Session = Depends(get_db_session)) -> ManagerLookup:
    return SqlAlchemyManagerLookup(SqlAlchemyUserRepository(session=db))


def get_create_project_use_case(
    db: Session = Depends(get_db_session),
    manager_lookup: ManagerLookup = Depends(get_manager_lookup),
) -> CreateProjectUseCase:
    return CreateProjectUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        manager_lookup=manager_lookup,
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def get_assign_project_manager_use_case(
    db: Session = Depends(get_db_session),
    manager_lookup: ManagerLookup = Depends(get_manager_lookup),
) -> AssignProjectManagerUseCase:
    return AssignProjectManagerUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        manager_lookup=manager_lookup,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


@router.post(
    "",
    response_model=ProjectDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo proyecto",
)
def create_project(
    cmd: CreateProjectCommand,
    current_user: CurrentUser = Depends(require_admin_or_manager),
    use_case: CreateProjectUseCase = Depends(get_create_project_use_case),
) -> ProjectDTO:
    return use_case.execute(cmd=cmd, actor=current_user)


@router.get(
    "",
    response_model=list[ProjectDTO],
    summary="Listar proyectos del usuario autenticado",
)
def list_projects(
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListProjectsUseCase = Depends(get_list_projects_use_case),
) -> list[ProjectDTO]:
    return use_case.execute(user=current_user)


@router.get(
    "/{project_id}",
    response_model=ProjectDTO,
    summary="Obtener detalles de un proyecto",
)
def get_project(
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: GetProjectUseCase = Depends(get_project_use_case),
) -> ProjectDTO:
    return use_case.execute(project_id=project_id, user=current_user)


@router.patch(
    "/{project_id}",
    response_model=ProjectDTO,
    summary="Actualizar datos del proyecto",
)
def update_project(
    project_id: str,
    cmd: UpdateProjectCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: UpdateProjectUseCase = Depends(get_update_project_use_case),
) -> ProjectDTO:
    return use_case.execute(project_id=project_id, cmd=cmd, actor=current_user)


@router.patch(
    "/{project_id}/status",
    response_model=MessageResponse,
    summary="Cambiar estado del proyecto",
)
def update_project_status(
    project_id: str,
    cmd: UpdateProjectStatusCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: UpdateProjectStatusUseCase = Depends(get_update_project_status_use_case),
) -> MessageResponse:
    return use_case.execute(project_id=project_id, cmd=cmd, actor=current_user)


@router.patch(
    "/{project_id}/manager",
    response_model=MessageResponse,
    summary="Reasignar gerente responsable",
)
def assign_project_manager(
    project_id: str,
    cmd: AssignProjectManagerCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: AssignProjectManagerUseCase = Depends(get_assign_project_manager_use_case),
) -> MessageResponse:
    return use_case.execute(project_id=project_id, cmd=cmd, actor=current_user)


@router.delete(
    "/{project_id}",
    response_model=MessageResponse,
    summary="Eliminar proyecto (solo Administrador)",
)
def delete_project(
    project_id: str,
    current_user: CurrentUser = Depends(require_admin),
    use_case: DeleteProjectUseCase = Depends(get_delete_project_use_case),
) -> MessageResponse:
    return use_case.execute(project_id=project_id, actor=current_user)


@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberDTO],
    summary="Listar miembros del proyecto",
)
def list_project_members(
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListProjectMembersUseCase = Depends(get_list_project_members_use_case),
) -> list[ProjectMemberDTO]:
    return use_case.execute(project_id=project_id, actor=current_user)


@router.get(
    "/{project_id}/health",
    response_model=ProjectHealthDTO,
    summary="Indicadores de salud del proyecto",
)
def get_project_health(
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: GetProjectHealthUseCase = Depends(get_project_health_use_case),
) -> ProjectHealthDTO:
    return use_case.execute(project_id=project_id, actor=current_user)


@router.post(
    "/{project_id}/members",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un miembro al proyecto",
)
def add_member(
    project_id: str,
    cmd: AddMemberCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: AddProjectMemberUseCase = Depends(get_add_project_member_use_case),
) -> MessageResponse:
    return use_case.execute(project_id=project_id, cmd=cmd, actor=current_user)


@router.delete(
    "/{project_id}/members/{user_id}",
    response_model=MessageResponse,
    summary="Retirar miembro del proyecto",
)
def remove_member(
    project_id: str,
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: RemoveProjectMemberUseCase = Depends(get_remove_project_member_use_case),
) -> MessageResponse:
    return use_case.execute(project_id=project_id, member_user_id=user_id, actor=current_user)
