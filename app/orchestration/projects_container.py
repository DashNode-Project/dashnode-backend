"""
Composition root for Projects module use cases (no cross-module imports).
@sad AD-09, HC-08
@origin [SAD-Propuesto]
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.projects.application.use_cases import (
    AddProjectMemberUseCase,
    DeleteProjectUseCase,
    GetProjectHealthUseCase,
    GetProjectUseCase,
    ListProjectMembersUseCase,
    ListProjectsUseCase,
    RemoveProjectMemberUseCase,
    UpdateProjectStatusUseCase,
    UpdateProjectUseCase,
)
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.orchestration.project_active_user_lookup import SqlAlchemyActiveUserLookup
from app.orchestration.project_meeting_cleanup import MeetingCleanupOnProjectDelete
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork
from app.shared.infrastructure.database import get_db_session as get_db
from app.shared.infrastructure.id_generator import UuidGenerator

clock = SystemClock()
id_generator = UuidGenerator()


def _active_users(db: Session) -> SqlAlchemyActiveUserLookup:
    return SqlAlchemyActiveUserLookup(SqlAlchemyUserRepository(session=db))


def get_update_project_use_case(
    db: Session = Depends(get_db),
) -> UpdateProjectUseCase:
    return UpdateProjectUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def get_update_project_status_use_case(
    db: Session = Depends(get_db),
) -> UpdateProjectStatusUseCase:
    return UpdateProjectStatusUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def get_delete_project_use_case(
    db: Session = Depends(get_db),
) -> DeleteProjectUseCase:
    return DeleteProjectUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        id_gen=id_generator,
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
        deletion_collaborator=MeetingCleanupOnProjectDelete(session=db),
    )


def get_add_project_member_use_case(
    db: Session = Depends(get_db),
) -> AddProjectMemberUseCase:
    return AddProjectMemberUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        users=_active_users(db),
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def get_remove_project_member_use_case(
    db: Session = Depends(get_db),
) -> RemoveProjectMemberUseCase:
    return RemoveProjectMemberUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        clock=clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def get_list_project_members_use_case(
    db: Session = Depends(get_db),
) -> ListProjectMembersUseCase:
    return ListProjectMembersUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        users=_active_users(db),
    )


def get_project_health_use_case(
    db: Session = Depends(get_db),
) -> GetProjectHealthUseCase:
    return GetProjectHealthUseCase(project_repo=SqlAlchemyProjectRepository(session=db))


def get_list_projects_use_case(
    db: Session = Depends(get_db),
) -> ListProjectsUseCase:
    return ListProjectsUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        users=_active_users(db),
    )


def get_project_use_case(
    db: Session = Depends(get_db),
) -> GetProjectUseCase:
    return GetProjectUseCase(
        project_repo=SqlAlchemyProjectRepository(session=db),
        users=_active_users(db),
    )
