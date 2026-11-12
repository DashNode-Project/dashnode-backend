"""Adapter for TeamMembersLookup protocol satisfying BR-4."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.availability.domain.ports import TeamMembersLookup, UserBasicInfo
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel


class SqlAlchemyTeamMembersLookup(TeamMembersLookup):
    """Resolves visible team members according to role and project assignments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_visible_users(self, actor_id: str, role: str) -> list[UserBasicInfo]:
        if role == "admin":
            models = self._session.scalars(
                select(UserModel)
                .where(UserModel.is_active.is_(True))
                .order_by(UserModel.name.asc())
            ).all()
            return [UserBasicInfo(id=u.id, name=u.name, email=u.email, role=u.role) for u in models]

        if role == "manager":
            # Projects where the manager is responsible
            project_ids = self._session.scalars(
                select(ProjectModel.id).where(
                    ProjectModel.manager_id == actor_id,
                    ProjectModel.deleted_at.is_(None),
                )
            ).all()

            user_ids: set[str] = {actor_id}
            if project_ids:
                member_ids = self._session.scalars(
                    select(ProjectMemberModel.user_id).where(
                        ProjectMemberModel.project_id.in_(project_ids)
                    )
                ).all()
                user_ids.update(member_ids)

            models = self._session.scalars(
                select(UserModel)
                .where(UserModel.id.in_(user_ids), UserModel.is_active.is_(True))
                .order_by(UserModel.name.asc())
            ).all()
            return [UserBasicInfo(id=u.id, name=u.name, email=u.email, role=u.role) for u in models]

        return []

    def list_all_active_users(self) -> list[UserBasicInfo]:
        models = self._session.scalars(
            select(UserModel).where(UserModel.is_active.is_(True)).order_by(UserModel.name.asc())
        ).all()
        return [UserBasicInfo(id=u.id, name=u.name, email=u.email, role=u.role) for u in models]
