"""
Composition root for Projects module use cases.
@sad AD-09, HC-08
@origin [SAD-Propuesto]
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.projects.application.use_cases import (
    AddProjectMemberUseCase,
    CreateProjectUseCase,
    GetProjectUseCase,
    ListProjectsUseCase,
)
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork
from app.shared.infrastructure.database import get_db_session as get_db
from app.shared.infrastructure.id_generator import UuidGenerator

clock = SystemClock()
id_generator = UuidGenerator()


def get_create_project_use_case(
    db: Session = Depends(get_db),
) -> CreateProjectUseCase:
    project_repo = SqlAlchemyProjectRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return CreateProjectUseCase(
        project_repo=project_repo,
        id_gen=id_generator,
        clock=clock,
        uow=uow,
    )


def get_add_project_member_use_case(
    db: Session = Depends(get_db),
) -> AddProjectMemberUseCase:
    project_repo = SqlAlchemyProjectRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return AddProjectMemberUseCase(
        project_repo=project_repo,
        clock=clock,
        uow=uow,
    )


def get_list_projects_use_case(
    db: Session = Depends(get_db),
) -> ListProjectsUseCase:
    project_repo = SqlAlchemyProjectRepository(session=db)
    return ListProjectsUseCase(project_repo=project_repo)


def get_project_use_case(
    db: Session = Depends(get_db),
) -> GetProjectUseCase:
    project_repo = SqlAlchemyProjectRepository(session=db)
    return GetProjectUseCase(project_repo=project_repo)
