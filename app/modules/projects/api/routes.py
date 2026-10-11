"""
FastAPI router for Projects module.
Complies strictly with BR-1 (no direct DB/infrastructure imports).
@sad 4.1.2, AD-08
@origin [SAD-Propuesto]
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.projects.application.dtos import (
    AddMemberCommand,
    CreateProjectCommand,
    ProjectDTO,
    ProjectMemberDTO,
)
from app.modules.projects.application.use_cases import (
    AddProjectMemberUseCase,
    CreateProjectUseCase,
    GetProjectUseCase,
    ListProjectsUseCase,
)
from app.orchestration.projects_container import (
    get_add_project_member_use_case,
    get_create_project_use_case,
    get_list_projects_use_case,
    get_project_use_case,
)
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo proyecto",
)
def create_project(
    cmd: CreateProjectCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: CreateProjectUseCase = Depends(get_create_project_use_case),
) -> ProjectDTO:
    try:
        return use_case.execute(cmd=cmd, owner_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "",
    response_model=list[ProjectDTO],
    summary="Listar proyectos del usuario autenticado",
)
def list_projects(
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListProjectsUseCase = Depends(get_list_projects_use_case),
) -> list[ProjectDTO]:
    return use_case.execute(user_id=current_user.id)


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
    try:
        return use_case.execute(project_id=project_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un miembro al proyecto",
)
def add_member(
    project_id: str,
    cmd: AddMemberCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: AddProjectMemberUseCase = Depends(get_add_project_member_use_case),
) -> ProjectMemberDTO:
    try:
        return use_case.execute(project_id=project_id, cmd=cmd, actor_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
