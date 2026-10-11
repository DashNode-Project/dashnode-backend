"""
FastAPI router for Tasks module.
Complies strictly with BR-1 (no direct DB/infrastructure imports) and BR-4.
@sad 4.1.3, AD-08, AD-10
@origin [SAD-Propuesto]
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.tasks.application.dtos import (
    AssignTaskCommand,
    CreateTaskCommand,
    TaskDTO,
    UpdateTaskStatusCommand,
)
from app.modules.tasks.application.use_cases import (
    AssignTaskUseCase,
    CreateTaskUseCase,
    GetTaskUseCase,
    ListProjectTasksUseCase,
    UpdateTaskStatusUseCase,
)
from app.orchestration.security import get_current_user
from app.orchestration.tasks_container import (
    get_assign_task_use_case,
    get_create_task_use_case,
    get_list_project_tasks_use_case,
    get_task_use_case,
    get_update_task_status_use_case,
)
from app.shared.application.identity import CurrentUser

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva tarea",
)
def create_task(
    cmd: CreateTaskCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: CreateTaskUseCase = Depends(get_create_task_use_case),
) -> TaskDTO:
    try:
        return use_case.execute(
            cmd=cmd,
            creator_id=current_user.id,
            creator_role=current_user.role,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{task_id}",
    response_model=TaskDTO,
    summary="Obtener detalles de una tarea por ID",
)
def get_task(
    task_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: GetTaskUseCase = Depends(get_task_use_case),
) -> TaskDTO:
    try:
        return use_case.execute(task_id=task_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/project/{project_id}",
    response_model=list[TaskDTO],
    summary="Listar todas las tareas pertenecientes a un proyecto",
)
def list_project_tasks(
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListProjectTasksUseCase = Depends(get_list_project_tasks_use_case),
) -> list[TaskDTO]:
    return use_case.execute(project_id=project_id)


@router.patch(
    "/{task_id}/status",
    response_model=TaskDTO,
    summary="Transición de estado de tarea (AD-10 / RN-TAR-01)",
)
def update_status(
    task_id: str,
    cmd: UpdateTaskStatusCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: UpdateTaskStatusUseCase = Depends(get_update_task_status_use_case),
) -> TaskDTO:
    try:
        return use_case.execute(
            task_id=task_id,
            cmd=cmd,
            actor_id=current_user.id,
            actor_role=current_user.role,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/{task_id}/assign",
    response_model=TaskDTO,
    summary="Asignar o desasignar responsable de tarea",
)
def assign_task(
    task_id: str,
    cmd: AssignTaskCommand,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: AssignTaskUseCase = Depends(get_assign_task_use_case),
) -> TaskDTO:
    try:
        return use_case.execute(
            task_id=task_id,
            cmd=cmd,
            actor_id=current_user.id,
            actor_role=current_user.role,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
