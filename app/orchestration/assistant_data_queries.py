"""Authorized read-only SQL for the AI assistant (orchestration adapter)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.data_models import ProjectRow, ProjectSummaryData
from app.modules.ai.domain.ports import ProjectAiContext
from app.modules.auth.infrastructure.models import UserModel
from app.modules.backlog.domain.entities import StoryTaskStatus
from app.modules.backlog.infrastructure.models import StoryTaskModel, UserStoryModel
from app.modules.documentation.infrastructure.models import DocumentationEntryModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.sprints.infrastructure.models import SprintModel
from app.orchestration.ai_context import SqlAlchemyProjectContextBuilder
from app.orchestration.backlog_adapters import SqlAlchemyProjectLookup


class AssistantDataService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._projects = SqlAlchemyProjectRepository(session)
        self._lookup = SqlAlchemyProjectLookup(session)

    def accessible_projects(self, user_id: str, role: str) -> list[ProjectRow]:
        rows = self._projects.list_visible_for_user(user_id, role=role)
        return [ProjectRow(id=row.id, name=row.name) for row in rows]

    def ensure_project_access(self, project_id: str, user_id: str, role: str) -> ProjectModel:
        if role != "admin" and not self._lookup.is_member(project_id, user_id):
            raise PermissionError(project_id)
        project = self._session.get(ProjectModel, project_id)
        if project is None or project.deleted_at is not None:
            raise LookupError(project_id)
        return project

    def list_members(self, project_id: str, user_id: str, role: str) -> list[str]:
        project = self.ensure_project_access(project_id, user_id, role)
        member_ids = self._session.scalars(
            select(ProjectMemberModel.user_id).where(ProjectMemberModel.project_id == project_id)
        ).all()
        names: list[str] = []
        for member_id in member_ids:
            user = self._session.get(UserModel, member_id)
            if user and user.is_active:
                names.append(f"{user.name} ({user.role})")
        manager = self._session.get(UserModel, project.manager_id)
        if manager and manager.is_active:
            label = f"{manager.name} ({manager.role}) — responsable"
            if label not in names:
                names.insert(0, label)
        return names

    def list_sprints(self, project_id: str, user_id: str, role: str) -> list[str]:
        self.ensure_project_access(project_id, user_id, role)
        sprints = self._session.scalars(
            select(SprintModel)
            .where(SprintModel.project_id == project_id)
            .order_by(SprintModel.start_date.asc())
        ).all()
        return [
            f"{s.name} [{s.status}] {s.start_date.isoformat()} → {s.end_date.isoformat()}"
            for s in sprints
        ]

    def list_stories(
        self,
        project_id: str,
        user_id: str,
        role: str,
        *,
        sprint_id: str | None = None,
    ) -> list[str]:
        self.ensure_project_access(project_id, user_id, role)
        stmt = select(UserStoryModel).where(UserStoryModel.project_id == project_id)
        if sprint_id:
            stmt = stmt.where(UserStoryModel.sprint_id == sprint_id)
        stories = self._session.scalars(stmt.order_by(UserStoryModel.created_at.asc())).all()
        sprint_names = {
            s.id: s.name
            for s in self._session.scalars(
                select(SprintModel).where(SprintModel.project_id == project_id)
            ).all()
        }
        lines: list[str] = []
        for story in stories:
            if story.sprint_id:
                sprint_label = sprint_names.get(story.sprint_id, "sin sprint")
            else:
                sprint_label = "sin sprint"
            tasks = self._session.scalars(
                select(StoryTaskModel).where(StoryTaskModel.user_story_id == story.id)
            ).all()
            done = all(t.status == StoryTaskStatus.DONE.value for t in tasks) if tasks else False
            status = "completada" if done else "pendiente"
            created = story.created_at.date().isoformat()
            lines.append(f"{story.title} — sprint: {sprint_label}, creada {created}, {status}")
        return lines

    def list_tasks(
        self,
        project_id: str,
        user_id: str,
        role: str,
        *,
        task_filter: str,
    ) -> list[str]:
        self.ensure_project_access(project_id, user_id, role)
        tasks = self._session.scalars(
            select(StoryTaskModel).where(StoryTaskModel.project_id == project_id)
        ).all()
        filtered: list[StoryTaskModel] = []
        for task in tasks:
            if task_filter == "correction" and task.status != StoryTaskStatus.CORRECTION.value:
                continue
            if task_filter == "blocked" and not task.is_blocked:
                continue
            if task_filter == "assigned_to_me" and task.assignee_id != user_id:
                continue
            if task_filter == "unassigned" and task.assignee_id is not None:
                continue
            if task_filter == "pending" and task.status == StoryTaskStatus.DONE.value:
                continue
            filtered.append(task)
        lines: list[str] = []
        for task in filtered[:40]:
            assignee = "sin asignar"
            if task.assignee_id:
                user = self._session.get(UserModel, task.assignee_id)
                assignee = user.name if user else task.assignee_id
            blocked = " (bloqueada)" if task.is_blocked else ""
            lines.append(f"{task.name} — {task.status}, asignada a {assignee}{blocked}")
        return lines

    def list_documentation(self, project_id: str, user_id: str, role: str) -> list[str]:
        self.ensure_project_access(project_id, user_id, role)
        docs = self._session.scalars(
            select(DocumentationEntryModel).where(
                DocumentationEntryModel.project_id == project_id,
                DocumentationEntryModel.is_deleted.is_(False),
            )
        ).all()
        lines: list[str] = []
        for doc in docs:
            if role == "developer" and not doc.is_visible_to_devs and doc.author_id != user_id:
                continue
            lines.append(f"{doc.title} — {doc.approval_status} ({doc.category})")
        return lines

    def sprint_candidates(self, project_id: str) -> list[tuple[str, str]]:
        rows = self._session.scalars(
            select(SprintModel).where(SprintModel.project_id == project_id)
        ).all()
        return [(row.id, row.name) for row in rows]

    def project_name(self, project_id: str) -> str:
        project = self._session.get(ProjectModel, project_id)
        return project.name if project else project_id

    def project_summary(self, project_id: str, user_id: str, role: str) -> ProjectSummaryData:
        project = self.ensure_project_access(project_id, user_id, role)
        hu, tasks, members = self.count_metrics(project_id)
        sprint_count = len(self.sprint_candidates(project_id))
        description = (project.description or "").strip()
        return ProjectSummaryData(
            name=project.name,
            description=description,
            status=project.status,
            hu_count=hu,
            task_count=tasks,
            member_count=members,
            sprint_count=sprint_count,
        )

    def build_project_ai_context(
        self, project_id: str, user_id: str, role: str
    ) -> ProjectAiContext:
        self.ensure_project_access(project_id, user_id, role)
        return SqlAlchemyProjectContextBuilder(self._session).build_context(
            project_id, user_id, role
        )

    def count_metrics(self, project_id: str) -> tuple[int, int, int]:
        hu = self._session.scalar(
            select(func.count())
            .select_from(UserStoryModel)
            .where(UserStoryModel.project_id == project_id)
        )
        tasks = self._session.scalar(
            select(func.count())
            .select_from(StoryTaskModel)
            .where(StoryTaskModel.project_id == project_id)
        )
        members = self._session.scalar(
            select(func.count())
            .select_from(ProjectMemberModel)
            .where(ProjectMemberModel.project_id == project_id)
        )
        return int(hu or 0), int(tasks or 0), int(members or 0)
