"""Cross-module adapter: project ownership checks for auth administration (BR-4)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.domain.ports import ProjectOwnershipQuery
from app.modules.projects.infrastructure.models import ProjectModel


class SqlAlchemyProjectOwnershipQuery(ProjectOwnershipQuery):
    def __init__(self, session: Session) -> None:
        self._session = session

    def user_owns_projects(self, user_id: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(ProjectModel)
            .where(
                ProjectModel.manager_id == user_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        return int(self._session.execute(stmt).scalar_one()) > 0
