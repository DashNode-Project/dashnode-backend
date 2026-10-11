"""
SQLAlchemy repository implementation for Projects.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.projects.domain.entities import Project, ProjectMember, ProjectRole
from app.modules.projects.domain.ports import ProjectRepository
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel


class SqlAlchemyProjectRepository(ProjectRepository):
    """SQLAlchemy implementation of the ProjectRepository port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            name=model.name,
            description=model.description,
            owner_id=model.owner_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _member_to_domain(self, model: ProjectMemberModel) -> ProjectMember:
        return ProjectMember(
            project_id=model.project_id,
            user_id=model.user_id,
            role=ProjectRole(model.role),
            joined_at=model.joined_at,
        )

    def get_by_id(self, project_id: str) -> Project | None:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = self._session.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return self._to_domain(result)

    def list_by_user(self, user_id: str) -> list[Project]:
        member_subquery = (
            select(ProjectMemberModel.project_id)
            .where(ProjectMemberModel.user_id == user_id)
        )
        stmt = (
            select(ProjectModel)
            .where(
                or_(
                    ProjectModel.owner_id == user_id,
                    ProjectModel.id.in_(member_subquery),
                )
            )
            .order_by(ProjectModel.created_at.desc())
        )
        results = self._session.execute(stmt).scalars().all()
        return [self._to_domain(p) for p in results]

    def save(self, project: Project) -> None:
        model = ProjectModel(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_id=project.owner_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        self._session.add(model)

    def update(self, project: Project) -> None:
        stmt = select(ProjectModel).where(ProjectModel.id == project.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is not None:
            model.name = project.name
            model.description = project.description
            model.owner_id = project.owner_id
            model.updated_at = project.updated_at

    def add_member(self, member: ProjectMember) -> None:
        model = ProjectMemberModel(
            project_id=member.project_id,
            user_id=member.user_id,
            role=member.role.value,
            joined_at=member.joined_at,
        )
        self._session.add(model)

    def get_members(self, project_id: str) -> list[ProjectMember]:
        stmt = select(ProjectMemberModel).where(ProjectMemberModel.project_id == project_id)
        results = self._session.execute(stmt).scalars().all()
        return [self._member_to_domain(m) for m in results]

    def is_member(self, project_id: str, user_id: str) -> bool:
        stmt = select(ProjectMemberModel).where(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.user_id == user_id,
        )
        return self._session.execute(stmt).scalar_one_or_none() is not None
