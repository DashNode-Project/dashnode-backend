"""
Composition root for Tasks module use cases.
Maintains modular independence under BR-4.
@sad AD-09, HC-08
@origin [SAD-Propuesto]
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.tasks.application.use_cases import (
    AssignTaskUseCase,
    CreateTaskUseCase,
    GetTaskUseCase,
    ListProjectTasksUseCase,
    UpdateTaskStatusUseCase,
)
from app.modules.tasks.infrastructure.repositories import SqlAlchemyTaskRepository
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import (
    SqlAlchemyUnitOfWork,
)
from app.shared.infrastructure.database import (
    get_db_session as get_db,
)
from app.shared.infrastructure.id_generator import UuidGenerator

clock = SystemClock()
id_generator = UuidGenerator()


def get_create_task_use_case(
    db: Session = Depends(get_db),
) -> CreateTaskUseCase:
    task_repo = SqlAlchemyTaskRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return CreateTaskUseCase(
        task_repo=task_repo,
        id_gen=id_generator,
        clock=clock,
        uow=uow,
    )


def get_update_task_status_use_case(
    db: Session = Depends(get_db),
) -> UpdateTaskStatusUseCase:
    task_repo = SqlAlchemyTaskRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return UpdateTaskStatusUseCase(
        task_repo=task_repo,
        clock=clock,
        uow=uow,
    )


def get_assign_task_use_case(
    db: Session = Depends(get_db),
) -> AssignTaskUseCase:
    task_repo = SqlAlchemyTaskRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return AssignTaskUseCase(
        task_repo=task_repo,
        clock=clock,
        uow=uow,
    )


def get_list_project_tasks_use_case(
    db: Session = Depends(get_db),
) -> ListProjectTasksUseCase:
    task_repo = SqlAlchemyTaskRepository(session=db)
    return ListProjectTasksUseCase(task_repo=task_repo)


def get_task_use_case(
    db: Session = Depends(get_db),
) -> GetTaskUseCase:
    task_repo = SqlAlchemyTaskRepository(session=db)
    return GetTaskUseCase(task_repo=task_repo)
