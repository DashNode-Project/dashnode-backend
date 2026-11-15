"""Bridges Projects module to Backlog ports (BR-4)."""

from typing import cast

from sqlalchemy.orm import Session

from app.modules.auth.domain.entities import UserRole
from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.backlog.application.access import ProjectContext
from app.modules.backlog.application.ports import ActiveMemberLookupPort, ProjectLookupPort
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository


class SqlAlchemyProjectLookup(ProjectLookupPort):
    def __init__(self, session: Session) -> None:
        self._projects = SqlAlchemyProjectRepository(session)

    def get_project(self, project_id: str) -> ProjectContext | None:
        project = self._projects.get_by_id(project_id)
        if project is None:
            return None
        return cast(ProjectContext, project)

    def is_member(self, project_id: str, user_id: str) -> bool:
        return self._projects.is_member(project_id, user_id)


class SqlAlchemyActiveMemberLookup(ActiveMemberLookupPort):
    def __init__(self, session: Session) -> None:
        self._projects = SqlAlchemyProjectRepository(session)
        self._users = SqlAlchemyUserRepository(session)

    def is_active_project_member(self, project_id: str, user_id: str) -> bool:
        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active or user.role is UserRole.ADMIN:
            return False
        project = self._projects.get_by_id(project_id)
        if project is None:
            return False
        if project.manager_id == user_id:
            return True
        return self._projects.is_member(project_id, user_id)
