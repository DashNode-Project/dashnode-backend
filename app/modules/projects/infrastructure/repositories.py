"""
SQLAlchemy repository implementation for Projects.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

import json
from datetime import datetime

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.orm import Session

from app.modules.projects.domain.entities import (
    Project,
    ProjectMember,
    ProjectPriority,
    ProjectRole,
    ProjectStatus,
)
from app.modules.projects.domain.health import ProjectHealthSnapshot
from app.modules.projects.domain.ports import ProjectRepository
from app.modules.projects.infrastructure.models import (
    AuditLogModel,
    ProjectMemberModel,
    ProjectModel,
)


class SqlAlchemyProjectRepository(ProjectRepository):
    """SQLAlchemy implementation of the ProjectRepository port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, model: ProjectModel) -> Project:
        stack_raw = model.tech_stack or "[]"
        try:
            stack = json.loads(stack_raw)
            tech_stack = stack if isinstance(stack, list) else []
        except json.JSONDecodeError:
            tech_stack = []
        tech_stack = [str(item) for item in tech_stack]
        return Project(
            id=model.id,
            name=model.name,
            description=model.description,
            owner_id=model.owner_id,
            manager_id=model.manager_id,
            priority=ProjectPriority(model.priority),
            tech_stack=tech_stack,
            meeting_link=model.meeting_link,
            status=ProjectStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )

    def _member_to_domain(self, model: ProjectMemberModel) -> ProjectMember:
        return ProjectMember(
            project_id=model.project_id,
            user_id=model.user_id,
            role=ProjectRole(model.role),
            joined_at=model.joined_at,
        )

    def get_by_id(self, project_id: str) -> Project | None:
        stmt = select(ProjectModel).where(
            ProjectModel.id == project_id,
            ProjectModel.deleted_at.is_(None),
        )
        result = self._session.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return self._to_domain(result)

    def list_visible_for_user(self, user_id: str, *, role: str) -> list[Project]:
        member_subquery = select(ProjectMemberModel.project_id).where(
            ProjectMemberModel.user_id == user_id
        )
        if role == "admin":
            stmt = (
                select(ProjectModel)
                .where(ProjectModel.deleted_at.is_(None))
                .order_by(ProjectModel.created_at.desc())
            )
        elif role == "manager":
            stmt = (
                select(ProjectModel)
                .where(
                    ProjectModel.deleted_at.is_(None),
                    or_(
                        ProjectModel.manager_id == user_id,
                        ProjectModel.id.in_(member_subquery),
                    ),
                )
                .order_by(ProjectModel.created_at.desc())
            )
        else:
            stmt = (
                select(ProjectModel)
                .where(
                    ProjectModel.deleted_at.is_(None),
                    ProjectModel.id.in_(member_subquery),
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
            manager_id=project.manager_id,
            priority=project.priority.value,
            tech_stack=json.dumps(project.tech_stack),
            meeting_link=project.meeting_link,
            status=project.status.value,
            deleted_at=project.deleted_at,
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
            model.manager_id = project.manager_id
            model.priority = project.priority.value
            model.tech_stack = json.dumps(project.tech_stack)
            model.meeting_link = project.meeting_link
            model.status = project.status.value
            model.updated_at = project.updated_at

    def add_member(self, member: ProjectMember) -> None:
        if self.is_member(member.project_id, member.user_id):
            return
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

    def user_can_access(self, project_id: str, user_id: str, role: str) -> bool:
        project = self._session.get(ProjectModel, project_id)
        if project is None or project.deleted_at is not None:
            return False
        if role == "admin":
            return True
        return any(
            row.id == project_id for row in self.list_visible_for_user(user_id, role=role)
        )

    def remove_member(self, project_id: str, user_id: str) -> None:
        self._session.execute(
            delete(ProjectMemberModel).where(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id,
            )
        )

    def clear_assignee_tasks(self, project_id: str, user_id: str, *, when: datetime) -> None:
        self._session.execute(
            text(
                "UPDATE tasks SET assignee_id = NULL, updated_at = :now "
                "WHERE project_id = :project_id AND assignee_id = :user_id "
                "AND deleted_at IS NULL AND status != 'completed'"
            ),
            {"now": when, "project_id": project_id, "user_id": user_id},
        )

    def get_health_snapshot(self, project_id: str) -> ProjectHealthSnapshot:
        return ProjectHealthSnapshot(
            completed_story_points=0,
            total_story_points=0,
            velocity_points_per_sprint=0.0,
            open_issues=0,
        )

    def soft_delete_cascade(self, project_id: str, when: object) -> None:
        from datetime import datetime

        assert isinstance(when, datetime)
        self._session.execute(
            update(ProjectModel)
            .where(ProjectModel.id == project_id)
            .values(deleted_at=when, updated_at=when)
        )
        self._session.execute(
            text(
                "UPDATE tasks SET deleted_at = :when, updated_at = :when "
                "WHERE project_id = :project_id AND deleted_at IS NULL"
            ),
            {"when": when, "project_id": project_id},
        )

    def add_audit_entry(
        self,
        *,
        entry_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        when: object,
    ) -> None:
        from datetime import datetime

        assert isinstance(when, datetime)
        self._session.add(
            AuditLogModel(
                id=entry_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=when,
            )
        )
